import uuid
import struct
from dataclasses import dataclass
from .serializer import PacketReader, PacketWriter

@dataclass(slots=True)
class Vec3f:
    x: float
    y: float
    z: float

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

@dataclass(slots=True)
class Vec2f:
    x: float
    y: float

@dataclass(slots=True)
class BlockPos:
    x: int
    y: int
    z: int

def read_uuid(reader: PacketReader) -> uuid.UUID:
    most = reader.read_long_le()
    least = reader.read_long_le()
    raw = struct.pack('<qq', most, least)
    return uuid.UUID(bytes=raw)

def write_uuid(writer: PacketWriter, val: uuid.UUID | str) -> PacketWriter:
    if isinstance(val, str):
        val = uuid.UUID(val)
    most, least = struct.unpack('<qq', val.bytes)
    writer.write_long_le(most)
    writer.write_long_le(least)
    return writer

def read_vec3f(reader: PacketReader) -> Vec3f:
    return Vec3f(x=reader.read_float_le(), y=reader.read_float_le(), z=reader.read_float_le())

def write_vec3f(writer: PacketWriter, vec: Vec3f) -> PacketWriter:
    writer.write_float_le(vec.x)
    writer.write_float_le(vec.y)
    writer.write_float_le(vec.z)
    return writer

def read_block_pos(reader: PacketReader) -> BlockPos:
    return BlockPos(x=reader.read_varint(), y=reader.read_uvarint(), z=reader.read_varint())

def write_block_pos(writer: PacketWriter, pos: BlockPos) -> PacketWriter:
    writer.write_varint(pos.x)
    writer.write_uvarint(pos.y)
    writer.write_varint(pos.z)
    return writer
