import struct
import zlib
from .varint import decode_varint, encode_varint, decode_uvarint, encode_uvarint
_MAX_DECOMPRESS = 10 * 1024 * 1024

class PacketReader:
    __slots__ = ('view', 'offset')

    def __init__(self, data: bytes | memoryview):
        self.view = memoryview(data) if isinstance(data, (bytes, bytearray)) else data
        self.offset = 0

    def remaining(self) -> int:
        return len(self.view) - self.offset

    def read_bytes(self, length: int) -> memoryview:
        end = self.offset + length
        if end > len(self.view):
            raise IndexError(f'Buffer underflow: need {length}, have {self.remaining()}')
        chunk = self.view[self.offset:end]
        self.offset = end
        return chunk

    def read_byte(self) -> int:
        if self.offset >= len(self.view):
            raise IndexError('Buffer underflow reading byte')
        val = self.view[self.offset]
        self.offset += 1
        return val

    def read_bool(self) -> bool:
        return self.read_byte() != 0

    def read_short_be(self) -> int:
        val = struct.unpack_from('>h', self.view, self.offset)[0]
        self.offset += 2
        return val

    def read_ushort_be(self) -> int:
        val = struct.unpack_from('>H', self.view, self.offset)[0]
        self.offset += 2
        return val

    def read_int_le(self) -> int:
        val = struct.unpack_from('<i', self.view, self.offset)[0]
        self.offset += 4
        return val

    def read_uint_le(self) -> int:
        val = struct.unpack_from('<I', self.view, self.offset)[0]
        self.offset += 4
        return val

    def read_long_le(self) -> int:
        val = struct.unpack_from('<q', self.view, self.offset)[0]
        self.offset += 8
        return val

    def read_ulong_le(self) -> int:
        val = struct.unpack_from('<Q', self.view, self.offset)[0]
        self.offset += 8
        return val

    def read_float_le(self) -> float:
        val = struct.unpack_from('<f', self.view, self.offset)[0]
        self.offset += 4
        return val

    def read_double_le(self) -> float:
        val = struct.unpack_from('<d', self.view, self.offset)[0]
        self.offset += 8
        return val

    def read_varint(self) -> int:
        val, self.offset = decode_varint(self.view, self.offset)
        return val

    def read_uvarint(self) -> int:
        val, self.offset = decode_uvarint(self.view, self.offset)
        return val

    def read_string(self) -> str:
        length = self.read_uvarint()
        return bytes(self.read_bytes(length)).decode('utf-8', errors='replace')

    def skip(self, n: int):
        if self.offset + n > len(self.view):
            raise IndexError(f'Cannot skip {n} bytes past end of buffer')
        self.offset += n

class PacketWriter:
    __slots__ = ('buffer',)

    def __init__(self, capacity: int=64):
        self.buffer = bytearray(capacity)
        self.buffer.clear()

    def write_bytes(self, data: bytes | bytearray | memoryview) -> 'PacketWriter':
        self.buffer.extend(data)
        return self

    def write_byte(self, value: int) -> 'PacketWriter':
        self.buffer.append(value & 255)
        return self

    def write_bool(self, value: bool) -> 'PacketWriter':
        self.buffer.append(1 if value else 0)
        return self

    def write_short_be(self, value: int) -> 'PacketWriter':
        self.buffer.extend(struct.pack('>h', value))
        return self

    def write_ushort_be(self, value: int) -> 'PacketWriter':
        self.buffer.extend(struct.pack('>H', value))
        return self

    def write_int_le(self, value: int) -> 'PacketWriter':
        self.buffer.extend(struct.pack('<i', value))
        return self

    def write_uint_le(self, value: int) -> 'PacketWriter':
        self.buffer.extend(struct.pack('<I', value))
        return self

    def write_long_le(self, value: int) -> 'PacketWriter':
        self.buffer.extend(struct.pack('<q', value))
        return self

    def write_ulong_le(self, value: int) -> 'PacketWriter':
        self.buffer.extend(struct.pack('<Q', value))
        return self

    def write_float_le(self, value: float) -> 'PacketWriter':
        self.buffer.extend(struct.pack('<f', value))
        return self

    def write_double_le(self, value: float) -> 'PacketWriter':
        self.buffer.extend(struct.pack('<d', value))
        return self

    def write_varint(self, value: int) -> 'PacketWriter':
        self.buffer.extend(encode_varint(value))
        return self

    def write_uvarint(self, value: int) -> 'PacketWriter':
        self.buffer.extend(encode_uvarint(value))
        return self

    def write_string(self, value: str) -> 'PacketWriter':
        encoded = value.encode('utf-8')
        self.write_uvarint(len(encoded))
        self.buffer.extend(encoded)
        return self

    def get_bytes(self) -> bytes:
        return bytes(self.buffer)

    def __len__(self) -> int:
        return len(self.buffer)

def decompress_batch(data: bytes | memoryview, max_size: int=_MAX_DECOMPRESS) -> bytes:
    if isinstance(data, memoryview):
        start = 1 if data[0] == 254 else 0
        raw = bytes(data[start:])
    else:
        start = 1 if data and data[0] == 254 else 0
        raw = data[start:]
    if not raw:
        return b''
    wbits = 15 if raw[0] == 120 else -15
    return zlib.decompress(raw, wbits, max_size)

def compress_batch(data: bytes, level: int=7) -> bytes:
    return b'\xfe' + zlib.compress(data, level)
