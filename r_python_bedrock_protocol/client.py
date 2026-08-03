import asyncio
import logging
import zlib
import base64
from .config import BotConfig, SkinConfig
from .event_emitter import EventEmitter
from .raknet.connection import RakNetClientProtocol
from .protocol.packets import PacketID, PROTOCOL_VERSION
from .protocol.versions import get_protocol, LATEST_VERSION, VERSIONS
from .protocol.devices import get_preset, DevicePreset
from .protocol.serializer import decompress_batch, compress_batch, PacketReader, PacketWriter
from .crypto.ecdh import BedrockCryptoContext
from .crypto.cipher import BedrockCipher
from .crypto.jwt import create_client_chain_jwt, create_client_skin_jwt, DeviceInfo, _get_default_skin_b64
logger = logging.getLogger(__name__)
try:
    import snappy as _snappy
    _SNAPPY_AVAILABLE = True
except ImportError:
    _SNAPPY_AVAILABLE = False
_PACK_STATUS_HAVE_ALL = 3
_PACK_STATUS_COMPLETED = 4

class BedrockClient(EventEmitter):

    def __init__(self, host: str='127.0.0.1', port: int=19132, *, config: BotConfig | None=None, username: str='Steve', offline: bool=True, version: str | int=LATEST_VERSION, device: str='android'):
        super().__init__()
        self.host = host
        self.port = port
        if config is None:
            config = BotConfig(username=username, offline=offline, version=version, device=device)
        self.config = config
        v = config.version
        if isinstance(v, int):
            self.protocol_version = v
            self.version = next((s for s, p in VERSIONS.items() if p == v), str(v))
        else:
            self.version = v
            self.protocol_version = get_protocol(v)
        try:
            self._device_preset: DevicePreset = get_preset(config.device)
        except ValueError:
            logger.warning('Unknown device preset %r, falling back to android.', config.device)
            self._device_preset = get_preset('android')
        self._raknet: RakNetClientProtocol | None = None
        self._crypto_ctx = BedrockCryptoContext()
        self._cipher: BedrockCipher | None = None
        self._compress_threshold: int = 1
        self._compress_algo: int = 0

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *_):
        await self.disconnect()

    async def connect(self, timeout: float | None=None):
        t = timeout if timeout is not None else self.config.connect_timeout
        loop = asyncio.get_running_loop()
        try:
            addr_info = await loop.getaddrinfo(self.host, self.port, family=socket.AF_INET)
            if addr_info:
                ip_host = addr_info[0][4][0]
            else:
                ip_host = self.host
        except Exception:
            ip_host = self.host
        self._raknet = RakNetClientProtocol(host=ip_host, port=self.port, mtu=self.config.mtu, on_game_packet=self._handle_game_packet)
        await loop.create_datagram_endpoint(lambda: self._raknet, remote_addr=(ip_host, self.port))
        await self._raknet.wait_connected(timeout=t)
        self.emit('connect')
        self._send_login()


    async def disconnect(self):
        if self._raknet and self._raknet.transport:
            self._raknet.transport.close()
        self.emit('close')

    def _build_device_info(self) -> DeviceInfo:
        cfg = self.config
        preset = self._device_preset
        return DeviceInfo(device_model=cfg.device_model or preset.model, device_os=int(preset.os), device_id=cfg.resolve_device_id(), client_random_id=cfg.resolve_client_random_id(), game_version=self.version if isinstance(self.version, str) else f'1.{self.version}', language_code=cfg.language_code, input_mode=int(preset.input_mode), ui_profile=int(preset.ui_profile), gui_scale=cfg.gui_scale, server_address=f'{self.host}:{self.port}', title_id=cfg.title_id)

    def _send_login(self):
        cfg = self.config
        client_uuid = cfg.resolve_player_uuid()
        device_info = self._build_device_info()
        chain_jwt = create_client_chain_jwt(cfg.username, client_uuid=client_uuid, crypto_ctx=self._crypto_ctx, xuid=cfg.xuid, title_id=cfg.title_id)
        skin_cfg: SkinConfig = cfg.skin
        skin_b64 = base64.b64encode(skin_cfg.data).decode('ascii') if skin_cfg.data else _get_default_skin_b64()
        skin_jwt = create_client_skin_jwt(cfg.username, client_uuid=client_uuid, crypto_ctx=self._crypto_ctx, device_info=device_info, skin_data_b64=skin_b64, skin_id=skin_cfg.skin_id, skin_width=skin_cfg.width, skin_height=skin_cfg.height, arm_size=skin_cfg.arm_size, cape_data=skin_cfg.cape_data, cape_id=skin_cfg.cape_id, cape_on_classic=skin_cfg.cape_on_classic, is_persona=skin_cfg.is_persona, persona_pieces=skin_cfg.persona_pieces, resource_patch_b64=skin_cfg.resource_patch)
        chain_bytes = f'{{"chain":["{chain_jwt}"]}}'.encode('utf-8')
        skin_bytes = skin_jwt.encode('utf-8')
        body = PacketWriter()
        body.write_varint(PacketID.LOGIN)
        body.write_int_le(self.protocol_version)
        body.write_uint_le(len(chain_bytes))
        body.write_bytes(chain_bytes)
        body.write_uint_le(len(skin_bytes))
        body.write_bytes(skin_bytes)
        self._send_raw_batch(body.get_bytes())

    def _handle_game_packet(self, batch_data: bytes):
        try:
            if self._cipher:
                batch_data = self._cipher.decrypt(batch_data)
            decompressed = self._decompress(batch_data)
            reader = PacketReader(decompressed)
            while reader.remaining() > 0:
                pkt_len = reader.read_uvarint()
                if pkt_len == 0 or pkt_len > reader.remaining():
                    break
                pkt_bytes = bytes(reader.read_bytes(pkt_len))
                pkt_reader = PacketReader(pkt_bytes)
                pkt_id = pkt_reader.read_uvarint() & 1023
                if self.config.log_packets:
                    try:
                        name = PacketID(pkt_id).name
                    except ValueError:
                        name = f'0x{pkt_id:02X}'
                    logger.debug('← %s (%d)', name, pkt_id)
                self._route_packet(pkt_id, pkt_reader, pkt_bytes)
        except Exception as exc:
            logger.error('Error handling game packet: %s', exc, exc_info=True)
            self.emit('error', exc)

    def _route_packet(self, pkt_id: int, reader: PacketReader, raw: bytes):
        if pkt_id == PacketID.NETWORK_SETTINGS:
            self._handle_network_settings(reader)
        elif pkt_id == PacketID.SERVER_TO_CLIENT_HANDSHAKE:
            self._handle_server_handshake(reader)
        elif pkt_id == PacketID.PLAY_STATUS:
            self._handle_play_status(reader)
        elif pkt_id == PacketID.RESOURCE_PACKS_INFO:
            if self.config.auto_resource_packs:
                self._send_resource_pack_response(_PACK_STATUS_HAVE_ALL)
        elif pkt_id == PacketID.RESOURCE_PACK_STACK:
            if self.config.auto_resource_packs:
                self._send_resource_pack_response(_PACK_STATUS_COMPLETED)
        elif pkt_id == PacketID.START_GAME:
            self._handle_start_game(reader)
        elif pkt_id == PacketID.CHUNK_RADIUS_UPDATE:
            pass
        elif pkt_id == PacketID.TICK_SYNC:
            if self.config.respond_tick_sync:
                self._handle_tick_sync(reader)
        elif pkt_id == PacketID.TEXT:
            self._handle_text(reader)
        elif pkt_id == PacketID.DISCONNECT:
            hide = reader.read_bool()
            reason = reader.read_string() if not hide and reader.remaining() > 0 else ''
            logger.info('Disconnected: %s', reason or '(no reason)')
            self.emit('disconnect', reason)
        elif pkt_id == PacketID.TRANSFER:
            if reader.remaining() > 0:
                host = reader.read_string()
                port = reader.read_ushort_be()
                logger.info('Transfer request → %s:%d', host, port)
                self.emit('transfer', {'host': host, 'port': port})
        self.emit('packet', {'id': pkt_id, 'data': raw})

    def _handle_network_settings(self, reader: PacketReader):
        if reader.remaining() < 4:
            return
        threshold = reader.read_ushort_be()
        algo = reader.read_ushort_be()
        self._compress_threshold = threshold
        self._compress_algo = algo
        algo_name = 'snappy' if algo == 1 else 'zlib'
        if algo == 1 and (not _SNAPPY_AVAILABLE):
            logger.warning('Server wants snappy; python-snappy not installed — may fail.')
        logger.debug('NetworkSettings: threshold=%d algo=%s', threshold, algo_name)
        self.emit('network_settings', {'threshold': threshold, 'algorithm': algo_name})

    def _handle_server_handshake(self, reader: PacketReader):
        try:
            import jwt as _jwt
            token_str = reader.read_string()
            hdr = _jwt.get_unverified_header(token_str)
            pub_key_b64 = hdr.get('x5u', '')
            remote_der = base64.b64decode(pub_key_b64)
            aes_key = self._crypto_ctx.compute_shared_secret(remote_der)
            self._cipher = BedrockCipher(aes_key)
            reply = PacketWriter()
            reply.write_varint(PacketID.CLIENT_TO_SERVER_HANDSHAKE)
            self._send_raw_batch(reply.get_bytes())
            logger.debug('Encryption enabled (AES-256-CFB8)')
        except Exception as exc:
            logger.error('Handshake error: %s', exc, exc_info=True)

    def _handle_play_status(self, reader: PacketReader):
        status = reader.read_int_le()
        STATUS = {0: 'login_success', 1: 'failed_client', 2: 'failed_server', 3: 'player_spawn', 4: 'failed_invalid_tenant', 5: 'failed_vanilla_edu', 6: 'failed_edu_vanilla', 7: 'failed_server_full'}
        name = STATUS.get(status, f'unknown({status})')
        logger.debug('PlayStatus: %s', name)
        if status == 0:
            self.emit('spawn')
        elif status == 3:
            self.emit('join')
        elif status in (1, 2, 4, 5, 6, 7):
            self.emit('error', ConnectionError(f'Rejected: {name}'))
        self.emit('play_status', status)

    def _handle_start_game(self, reader: PacketReader):
        data: dict = {}
        try:
            data['entity_id'] = reader.read_varint()
            data['runtime_entity_id'] = reader.read_uvarint()
            data['player_gamemode'] = reader.read_varint()
            data['spawn'] = (reader.read_float_le(), reader.read_float_le(), reader.read_float_le())
            data['rotation'] = (reader.read_float_le(), reader.read_float_le())
        except Exception:
            pass
        self.emit('start_game', data)
        self._send_request_chunk_radius(self.config.chunk_radius)

    def _handle_tick_sync(self, reader: PacketReader):
        if reader.remaining() < 16:
            return
        req_time = reader.read_ulong_le()
        reader.read_ulong_le()
        import time
        w = PacketWriter()
        w.write_uvarint(PacketID.TICK_SYNC)
        w.write_ulong_le(req_time)
        w.write_ulong_le(int(time.time() * 1000))
        self._send_raw_batch(w.get_bytes())

    def _handle_text(self, reader: PacketReader):
        try:
            pkt_type = reader.read_byte()
            _needs_tr = reader.read_bool()
            source = reader.read_string() if pkt_type in (1, 2, 7, 8, 9) else ''
            msg = reader.read_string()
            self.emit('text', {'type': pkt_type, 'source_name': source, 'message': msg})
        except Exception as exc:
            logger.debug('Text parse error: %s', exc)

    def _send_resource_pack_response(self, status: int):
        w = PacketWriter()
        w.write_uvarint(PacketID.RESOURCE_PACK_CLIENT_RESPONSE)
        w.write_byte(status)
        w.write_ushort_be(0)
        self._send_raw_batch(w.get_bytes())

    def _send_request_chunk_radius(self, radius: int=8):
        w = PacketWriter()
        w.write_uvarint(PacketID.REQUEST_CHUNK_RADIUS)
        w.write_varint(radius)
        w.write_byte(radius)
        self._send_raw_batch(w.get_bytes())

    def send(self, packet_name: str, payload: dict):
        w = PacketWriter()
        if packet_name == 'text':
            w.write_uvarint(PacketID.TEXT)
            w.write_byte(payload.get('type', 1))
            w.write_bool(payload.get('needs_translation', False))
            w.write_string(self.config.username)
            w.write_string(payload.get('message', ''))
            w.write_string('')
            w.write_string('')
            w.write_bool(False)
        elif packet_name == 'command':
            w.write_uvarint(PacketID.COMMAND_REQUEST)
            w.write_string(payload.get('command', ''))
            w.write_byte(0)
            w.write_ulong_le(0)
            w.write_uint_le(0)
            w.write_bool(False)
        else:
            logger.warning('send: unknown packet name %r', packet_name)
            return
        raw = w.get_bytes()
        frame = PacketWriter()
        frame.write_uvarint(len(raw))
        frame.write_bytes(raw)
        self._send_raw_batch(frame.get_bytes())

    def send_raw(self, packet_id: int, writer: PacketWriter):
        body = PacketWriter()
        body.write_uvarint(packet_id)
        body.write_bytes(writer.get_bytes())
        raw = body.get_bytes()
        frame = PacketWriter()
        frame.write_uvarint(len(raw))
        frame.write_bytes(raw)
        self._send_raw_batch(frame.get_bytes())

    def _compress(self, data: bytes) -> bytes:
        if len(data) < self._compress_threshold:
            return b'\xfe' + data
        if self._compress_algo == 1 and _SNAPPY_AVAILABLE:
            return b'\xfe' + _snappy.compress(data)
        return compress_batch(data)

    def _decompress(self, data: bytes | memoryview) -> bytes:
        raw = bytes(data)
        if not raw or raw[0] != 254:
            return raw
        body = raw[1:]
        if not body:
            return b''
        if self._compress_algo == 1 and _SNAPPY_AVAILABLE:
            try:
                return _snappy.decompress(body)
            except Exception:
                pass
        if body[0] == 120:
            return zlib.decompress(body, 15, 10 * 1024 * 1024)
        try:
            return zlib.decompress(body, -15, 10 * 1024 * 1024)
        except zlib.error:
            return body

    def _send_raw_batch(self, data: bytes):
        batch = self._compress(data)
        if self._cipher:
            batch = self._cipher.encrypt(batch)
        if self._raknet:
            self._raknet.send_frame(batch)

def create_client(host: str='127.0.0.1', port: int=19132, *, config: BotConfig | None=None, username: str='Steve', offline: bool=True, version: str | int=LATEST_VERSION, device: str='android') -> BedrockClient:
    return BedrockClient(host, port, config=config, username=username, offline=offline, version=version, device=device)
