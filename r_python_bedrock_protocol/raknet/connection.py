import asyncio
import time
import struct
import logging
import os
from collections import OrderedDict
from typing import Callable, Optional
from .protocol import RAKNET_MAGIC, ID_OPEN_CONNECTION_REQUEST_1, ID_OPEN_CONNECTION_REPLY_1, ID_OPEN_CONNECTION_REQUEST_2, ID_OPEN_CONNECTION_REPLY_2, ID_CONNECTION_REQUEST, ID_CONNECTION_REQUEST_ACCEPTED, ID_CONNECTED_PING, ID_CONNECTED_PONG, ID_ACK, ID_NACK, ID_NEW_INCOMING_CONNECTION, ID_DISCONNECT_NOTIFICATION

logger = logging.getLogger(__name__)
_SPLIT_TTL = 30.0
_SENT_CACHE_MAX = 512
_SENT_CACHE_TRIM = 128

class SplitPacketBuffer:
    __slots__ = ('split_count', 'max_fragments', 'fragments', 'timestamp')

    def __init__(self, split_count: int, max_fragments: int=256):
        self.split_count = split_count
        self.max_fragments = max_fragments
        self.fragments: dict[int, bytes] = {}
        self.timestamp = time.monotonic()

    def add_fragment(self, index: int, data: bytes) -> Optional[bytes]:
        if not 0 <= index < self.split_count or self.split_count > self.max_fragments:
            return None
        self.fragments[index] = data
        self.timestamp = time.monotonic()
        if len(self.fragments) == self.split_count:
            return b''.join((self.fragments[i] for i in range(self.split_count)))
        return None

def _pack_address(host: str, port: int) -> bytes:
    try:
        import socket
        raw = socket.inet_aton(host)
        inverted = bytes((b ^ 255 for b in raw))
        return b'\x04' + inverted + struct.pack('>H', port)
    except OSError:
        return b'\x04\x00\x00\x00\x00' + struct.pack('>H', port)

class RakNetClientProtocol(asyncio.DatagramProtocol):

    def __init__(self, host: str, port: int, mtu: int=1400, on_game_packet: Optional[Callable[[bytes], None]]=None):
        self.host = host
        self.port = port
        self.mtu = mtu
        self.on_game_packet = on_game_packet
        self.connected = False
        self.client_guid: int = int.from_bytes(os.urandom(8), 'little')
        self.sequence_number = 0
        self.reliable_index = 0
        self.order_index = 0
        self.transport: Optional[asyncio.DatagramTransport] = None
        self._split_buffers: dict[int, SplitPacketBuffer] = {}
        self._sent_packets: OrderedDict[int, bytes] = OrderedDict()
        self._connected_event = asyncio.Event()

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        self._send_ocr1()

    def datagram_received(self, data: bytes, addr: tuple[str, int]):
        if not data:
            return
        try:
            self._dispatch(data)
        except (struct.error, IndexError) as exc:
            logger.debug('Malformed RakNet datagram: %s', exc)

    def error_received(self, exc: Exception):
        logger.warning('RakNet UDP error: %s', exc)

    def connection_lost(self, exc: Exception | None):
        if exc:
            logger.warning('RakNet connection lost: %s', exc)
        self._connected_event.set()

    def _dispatch(self, data: bytes):
        pid = data[0]
        if pid == ID_OPEN_CONNECTION_REPLY_1:
            self._handle_ocr1_reply(data)
        elif pid == ID_OPEN_CONNECTION_REPLY_2:
            self._handle_ocr2_reply(data)
        elif pid == ID_CONNECTION_REQUEST_ACCEPTED:
            self._handle_connection_accepted(data)
        elif pid == ID_CONNECTED_PING:
            self._handle_ping(data)
        elif pid == ID_ACK:
            self._handle_ack(data, retransmit=False)
        elif pid == ID_NACK:
            self._handle_ack(data, retransmit=True)
        elif 128 <= pid <= 143:
            self._handle_frame_set(data)

    def _send_ocr1(self):
        packet = bytearray()
        packet.append(ID_OPEN_CONNECTION_REQUEST_1)
        packet.extend(RAKNET_MAGIC)
        packet.append(11)
        pad_len = max(0, self.mtu - len(packet) - 28)
        packet.extend(b'\x00' * pad_len)
        self._sendto(bytes(packet))

    def _handle_ocr1_reply(self, data: bytes):
        min_len = 1 + len(RAKNET_MAGIC) + 8 + 1 + 2
        if len(data) < min_len:
            return
        mtu_off = 1 + len(RAKNET_MAGIC) + 8 + 1
        negotiated_mtu = struct.unpack_from('>H', data, mtu_off)[0]
        self.mtu = min(negotiated_mtu, self.mtu)
        server_addr = _pack_address(self.host, self.port)
        packet = bytearray()
        packet.append(ID_OPEN_CONNECTION_REQUEST_2)
        packet.extend(RAKNET_MAGIC)
        packet.extend(server_addr)
        packet.extend(struct.pack('>H', self.mtu))
        packet.extend(struct.pack('>Q', self.client_guid))
        self._sendto(bytes(packet))

    def _handle_ocr2_reply(self, data: bytes):
        packet = bytearray()
        packet.append(ID_CONNECTION_REQUEST)
        packet.extend(struct.pack('>Q', self.client_guid))
        packet.extend(struct.pack('>Q', int(time.time() * 1000)))
        packet.append(0)
        self.send_frame(bytes(packet))

    def _handle_connection_accepted(self, data: bytes):
        self.connected = True
        self._connected_event.set()
        now_ms = int(time.time() * 1000)
        server_addr = _pack_address(self.host, self.port)
        empty_addr = b'\x04\x00\x00\x00\x00\x00\x00'
        packet = bytearray()
        packet.append(ID_NEW_INCOMING_CONNECTION)
        packet.extend(server_addr)
        for _ in range(9):
            packet.extend(empty_addr)
        packet.extend(struct.pack('>QQ', now_ms, now_ms))
        self.send_frame(bytes(packet))

    def _handle_ping(self, data: bytes):
        if len(data) < 9:
            return
        ping_time = struct.unpack_from('>Q', data, 1)[0]
        pong = bytearray()
        pong.append(ID_CONNECTED_PONG)
        pong.extend(struct.pack('>QQ', ping_time, int(time.time() * 1000)))
        self.send_frame(bytes(pong))

    def _handle_ack(self, data: bytes, retransmit: bool):
        if len(data) < 3:
            return
        record_count = struct.unpack_from('>H', data, 1)[0]
        offset = 3
        for _ in range(record_count):
            if offset >= len(data):
                break
            is_range = data[offset] == 0
            offset += 1
            if is_range:
                if offset + 6 > len(data):
                    break
                start_seq = struct.unpack_from('>I', b'\x00' + data[offset:offset + 3])[0]
                end_seq = struct.unpack_from('>I', b'\x00' + data[offset + 3:offset + 6])[0]
                offset += 6
                for seq in range(start_seq, end_seq + 1):
                    self._ack_seq(seq, retransmit)
            else:
                if offset + 3 > len(data):
                    break
                seq = struct.unpack_from('>I', b'\x00' + data[offset:offset + 3])[0]
                offset += 3
                self._ack_seq(seq, retransmit)

    def _ack_seq(self, seq: int, retransmit: bool):
        if retransmit:
            frame = self._sent_packets.get(seq)
            if frame and self.transport:
                self.transport.sendto(frame, (self.host, self.port))
        else:
            self._sent_packets.pop(seq, None)

    def _handle_frame_set(self, data: bytes):
        if len(data) < 4:
            return
        seq_num = struct.unpack_from('<I', data, 1)[0] & 16777215
        ack = bytes([ID_ACK, 0, 1, 1]) + struct.pack('>I', seq_num)[1:]
        self._sendto(ack)
        self._purge_old_split_buffers()
        offset = 4
        n = len(data)
        while offset < n:
            if offset + 3 > n:
                break
            flags = data[offset]
            bit_len = struct.unpack_from('>H', data, offset + 1)[0]
            byte_len = (bit_len + 7) // 8
            offset += 3
            reliability = (flags & 224) >> 5
            is_split = bool(flags & 16)
            if reliability >= 2:
                if offset + 3 > n:
                    break
                offset += 3
            if reliability in (3, 4, 7):
                if offset + 4 > n:
                    break
                offset += 4
            split_count = split_id = split_index = 0
            if is_split:
                if offset + 10 > n:
                    break
                split_count = struct.unpack_from('>i', data, offset)[0]
                split_id = struct.unpack_from('>H', data, offset + 4)[0]
                split_index = struct.unpack_from('>i', data, offset + 6)[0]
                offset += 10
            if offset + byte_len > n:
                break
            body = data[offset:offset + byte_len]
            offset += byte_len
            if is_split:
                buf = self._split_buffers.setdefault(split_id, SplitPacketBuffer(split_count))
                complete = buf.add_fragment(split_index, body)
                if complete is None:
                    continue
                del self._split_buffers[split_id]
                body = complete
            if body:
                pid = body[0]
                if pid == ID_CONNECTION_REQUEST_ACCEPTED:
                    self._handle_connection_accepted(body)
                elif pid == ID_DISCONNECT_NOTIFICATION:
                    self.connected = False
                elif pid == 254 and self.on_game_packet:
                    self.on_game_packet(body)


    def send_frame(self, payload: bytes, reliable: bool=True):
        max_payload = self.mtu - 60
        if len(payload) > max_payload and reliable:
            self._send_split(payload, max_payload)
            return
        self._send_single_frame(payload, reliable=reliable)

    def _send_single_frame(self, payload: bytes, reliable: bool=True):
        reliability = 96 if reliable else 0
        frame = bytearray()
        frame.append(132)
        seq = self.sequence_number
        frame.extend(struct.pack('<I', seq)[:3])
        frame.append(reliability)
        frame.extend(struct.pack('>H', len(payload) * 8))
        if reliable:
            frame.extend(struct.pack('>I', self.reliable_index)[1:])
            self.reliable_index = self.reliable_index + 1 & 16777215
            frame.extend(struct.pack('>I', self.order_index)[1:])
            frame.append(0)
            self.order_index = self.order_index + 1 & 16777215
        frame.extend(payload)
        raw = bytes(frame)
        self._sent_packets[seq] = raw
        self.sequence_number = self.sequence_number + 1 & 16777215
        while len(self._sent_packets) > _SENT_CACHE_MAX:
            self._sent_packets.popitem(last=False)
        self._sendto(raw)

    def _send_split(self, payload: bytes, max_chunk: int):
        chunks = [payload[i:i + max_chunk] for i in range(0, len(payload), max_chunk)]
        split_id = self.reliable_index & 65535
        split_count = len(chunks)
        for split_index, chunk in enumerate(chunks):
            frame = bytearray()
            frame.append(132)
            seq = self.sequence_number
            frame.extend(struct.pack('<I', seq)[:3])
            frame.append(112)
            frame.extend(struct.pack('>H', len(chunk) * 8))
            frame.extend(struct.pack('>I', self.reliable_index)[1:])
            self.reliable_index = self.reliable_index + 1 & 16777215
            frame.extend(struct.pack('>I', self.order_index)[1:])
            frame.append(0)
            frame.extend(struct.pack('>i', split_count))
            frame.extend(struct.pack('>H', split_id))
            frame.extend(struct.pack('>i', split_index))
            frame.extend(chunk)
            raw = bytes(frame)
            self._sent_packets[seq] = raw
            self.sequence_number = self.sequence_number + 1 & 16777215
            self._sendto(raw)
        self.order_index = self.order_index + 1 & 16777215

    def _sendto(self, data: bytes):
        if self.transport:
            try:
                self.transport.sendto(data)
            except TypeError:
                self.transport.sendto(data, (self.host, self.port))


    def _purge_old_split_buffers(self):
        now = time.monotonic()
        expired = [sid for sid, buf in self._split_buffers.items() if now - buf.timestamp > _SPLIT_TTL]
        for sid in expired:
            del self._split_buffers[sid]

    async def wait_connected(self, timeout: float=10.0):
        await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)
