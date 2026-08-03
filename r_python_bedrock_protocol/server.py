import asyncio
import os
import socket
import struct
import logging
from .event_emitter import EventEmitter
from .protocol.packets import PROTOCOL_VERSION, GAME_VERSION
from .raknet.protocol import RAKNET_MAGIC, ID_UNCONNECTED_PING, ID_OPEN_CONNECTION_REQUEST_1, ID_OPEN_CONNECTION_REPLY_1, ID_OPEN_CONNECTION_REQUEST_2, ID_OPEN_CONNECTION_REPLY_2
logger = logging.getLogger(__name__)

def _pack_address(host: str, port: int) -> bytes:
    try:
        raw = socket.inet_aton(host)
        return b'\x04' + raw + struct.pack('>H', port)
    except OSError:
        try:
            raw6 = socket.inet_pton(socket.AF_INET6, host)
            return b'\x06' + struct.pack('>H', socket.AF_INET6) + struct.pack('>H', port) + struct.pack('>I', 0) + raw6 + struct.pack('>I', 0)
        except OSError:
            return b'\x04\x7f\x00\x00\x01' + struct.pack('>H', port)

class ServerClientConnection(EventEmitter):
    __slots__ = ('address', 'transport', 'username', '_listeners')

    def __init__(self, address: tuple[str, int], transport: asyncio.DatagramTransport):
        super().__init__()
        self.address = address
        self.transport = transport
        self.username = 'Player'

    def disconnect(self, reason: str='Disconnected by server'):
        self.emit('disconnect', reason)

    def send_raw(self, data: bytes):
        self.transport.sendto(data, self.address)

    def __repr__(self) -> str:
        return f'<ServerClientConnection {self.address[0]}:{self.address[1]}>'

class _ServerDatagramProtocol(asyncio.DatagramProtocol):

    def __init__(self, server: 'BedrockServer'):
        self.server = server
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        self.server._transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]):
        if not data:
            return
        try:
            self._dispatch(data, addr)
        except Exception as exc:
            logger.debug('Server datagram error from %s: %s', addr, exc)

    def error_received(self, exc: Exception):
        logger.warning('Server UDP error: %s', exc)

    def _dispatch(self, data: bytes, addr: tuple[str, int]):
        pid = data[0]
        if pid == ID_UNCONNECTED_PING:
            self._handle_ping(data, addr)
        elif pid == ID_OPEN_CONNECTION_REQUEST_1:
            self._handle_ocr1(data, addr)
        elif pid == ID_OPEN_CONNECTION_REQUEST_2:
            self._handle_ocr2(data, addr)

    def _handle_ping(self, data: bytes, addr: tuple[str, int]):
        if len(data) < 9:
            return
        ping_time = struct.unpack_from('>q', data, 1)[0]
        srv = self.server
        online = len(srv.clients)
        adv = f'MCPE;{srv.motd};{PROTOCOL_VERSION};{GAME_VERSION};{online};{srv.max_players};{srv._guid};Bedrock level;Survival;1;{srv.port};{srv.port};'
        adv_bytes = adv.encode('utf-8')
        pong = bytearray()
        pong.append(28)
        pong.extend(struct.pack('>q', ping_time))
        pong.extend(struct.pack('>Q', srv._guid))
        pong.extend(RAKNET_MAGIC)
        pong.extend(struct.pack('>H', len(adv_bytes)))
        pong.extend(adv_bytes)
        if self.transport:
            self.transport.sendto(bytes(pong), addr)

    def _handle_ocr1(self, data: bytes, addr: tuple[str, int]):
        reply = bytearray()
        reply.append(ID_OPEN_CONNECTION_REPLY_1)
        reply.extend(RAKNET_MAGIC)
        reply.extend(struct.pack('>Q', self.server._guid))
        reply.append(0)
        reply.extend(struct.pack('>H', 1400))
        if self.transport:
            self.transport.sendto(bytes(reply), addr)

    def _handle_ocr2(self, data: bytes, addr: tuple[str, int]):
        reply = bytearray()
        reply.append(ID_OPEN_CONNECTION_REPLY_2)
        reply.extend(RAKNET_MAGIC)
        reply.extend(struct.pack('>Q', self.server._guid))
        reply.extend(_pack_address(addr[0], addr[1]))
        reply.extend(struct.pack('>H', 1400))
        reply.append(0)
        if self.transport:
            self.transport.sendto(bytes(reply), addr)
        if addr not in self.server.clients:
            conn = ServerClientConnection(addr, self.transport)
            self.server.clients[addr] = conn
            self.server.emit('connect', conn)

class BedrockServer(EventEmitter):

    def __init__(self, host: str='0.0.0.0', port: int=19132, motd: str='Bedrock Server', max_players: int=20):
        super().__init__()
        self.host = host
        self.port = port
        self.motd = motd
        self.max_players = max_players
        self.clients: dict[tuple[str, int], ServerClientConnection] = {}
        self._transport: asyncio.DatagramTransport | None = None
        self._guid: int = int.from_bytes(os.urandom(8), 'little')

    async def __aenter__(self):
        await self.listen()
        return self

    async def __aexit__(self, *_):
        self.close()

    async def listen(self):
        loop = asyncio.get_running_loop()
        protocol = _ServerDatagramProtocol(self)
        await loop.create_datagram_endpoint(lambda: protocol, local_addr=(self.host, self.port))
        self.emit('listening')

    def close(self):
        for client in list(self.clients.values()):
            client.disconnect('Server closed')
        self.clients.clear()
        if self._transport:
            self._transport.close()
            self._transport = None
        self.emit('close')

def create_server(host: str='0.0.0.0', port: int=19132, motd: str='Bedrock Server', max_players: int=20) -> BedrockServer:
    return BedrockServer(host=host, port=port, motd=motd, max_players=max_players)
