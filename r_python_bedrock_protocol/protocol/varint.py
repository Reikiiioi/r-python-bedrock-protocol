def encode_varint(value: int) -> bytes:
    n = (value << 1 ^ value >> 31) & 4294967295
    out = bytearray()
    while True:
        chunk = n & 127
        n >>= 7
        if n:
            out.append(chunk | 128)
        else:
            out.append(chunk)
            break
    return bytes(out)

def decode_varint(stream: bytes | memoryview, offset: int=0) -> tuple[int, int]:
    result = 0
    shift = 0
    pos = offset
    length = len(stream)
    while True:
        if pos >= length:
            raise IndexError('Buffer underflow reading VarInt')
        byte = stream[pos]
        pos += 1
        result |= (byte & 127) << shift
        if not byte & 128:
            break
        shift += 7
        if shift >= 35:
            raise ValueError('VarInt too large (>5 bytes)')
    decoded = result >> 1 ^ -(result & 1)
    return (decoded, pos)

def encode_uvarint(value: int) -> bytes:
    n = value & 4294967295
    out = bytearray()
    while True:
        chunk = n & 127
        n >>= 7
        if n:
            out.append(chunk | 128)
        else:
            out.append(chunk)
            break
    return bytes(out)

def decode_uvarint(stream: bytes | memoryview, offset: int=0) -> tuple[int, int]:
    result = 0
    shift = 0
    pos = offset
    length = len(stream)
    while True:
        if pos >= length:
            raise IndexError('Buffer underflow reading UVarInt')
        byte = stream[pos]
        pos += 1
        result |= (byte & 127) << shift
        if not byte & 128:
            break
        shift += 7
        if shift >= 35:
            raise ValueError('UVarInt too large (>5 bytes)')
    return (result, pos)
