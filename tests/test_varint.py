"""Tests for VarInt and UVarInt encode/decode."""

import unittest
from r_python_bedrock_protocol.protocol.varint import (
    encode_varint, decode_varint,
    encode_uvarint, decode_uvarint,
)


class TestVarInt(unittest.TestCase):

    def test_varint_roundtrip(self):
        values = [0, 1, -1, 127, -128, 255, -256, 123456, -123456, 2147483647, -2147483648]
        for val in values:
            with self.subTest(val=val):
                encoded = encode_varint(val)
                decoded, offset = decode_varint(encoded, 0)
                self.assertEqual(val, decoded)
                self.assertEqual(offset, len(encoded))

    def test_uvarint_roundtrip(self):
        values = [0, 1, 127, 128, 255, 65535, 123456, 4294967295]
        for val in values:
            with self.subTest(val=val):
                encoded = encode_uvarint(val)
                decoded, offset = decode_uvarint(encoded, 0)
                self.assertEqual(val, decoded)
                self.assertEqual(offset, len(encoded))

    def test_varint_negative_zigzag(self):
        # ZigZag: -1 maps to 1, -2 maps to 3, etc.
        self.assertEqual(encode_varint(-1), encode_uvarint(1))
        self.assertEqual(encode_varint(-2), encode_uvarint(3))
        self.assertEqual(encode_varint(1), encode_uvarint(2))

    def test_varint_max_bounds(self):
        # Both extremes must survive a roundtrip
        for val in (2147483647, -2147483648):
            decoded, _ = decode_varint(encode_varint(val))
            self.assertEqual(val, decoded)

    def test_varint_overflow_raises(self):
        # 6 continuation bytes — more than 5 bytes allowed
        bad = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00])
        with self.assertRaises(ValueError):
            decode_varint(bad)

    def test_uvarint_underflow_raises(self):
        # Continuation byte but no data following
        with self.assertRaises(IndexError):
            decode_uvarint(bytes([0x80]))

    def test_memoryview_input(self):
        data = bytearray([0x05, 0x00])
        view = memoryview(data)
        val, off = decode_uvarint(view, 0)
        self.assertEqual(val, 5)
        self.assertEqual(off, 1)


if __name__ == "__main__":
    unittest.main()
