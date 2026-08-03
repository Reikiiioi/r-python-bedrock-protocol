"""Tests for PacketReader, PacketWriter, compress/decompress."""

import unittest
from r_python_bedrock_protocol.protocol.serializer import (
    PacketWriter, PacketReader, compress_batch, decompress_batch,
)


class TestSerializer(unittest.TestCase):

    def test_writer_reader_roundtrip(self):
        writer = PacketWriter()
        (
            writer
            .write_byte(0x42)
            .write_bool(True)
            .write_bool(False)
            .write_short_be(1337)
            .write_int_le(-987654)
            .write_uint_le(4294967295)
            .write_long_le(-9999999999)
            .write_float_le(3.14)
            .write_string("Hello Bedrock!")
        )

        reader = PacketReader(writer.get_bytes())
        self.assertEqual(reader.read_byte(), 0x42)
        self.assertTrue(reader.read_bool())
        self.assertFalse(reader.read_bool())
        self.assertEqual(reader.read_short_be(), 1337)
        self.assertEqual(reader.read_int_le(), -987654)
        self.assertEqual(reader.read_uint_le(), 4294967295)
        self.assertEqual(reader.read_long_le(), -9999999999)
        self.assertAlmostEqual(reader.read_float_le(), 3.14, places=5)
        self.assertEqual(reader.read_string(), "Hello Bedrock!")
        self.assertEqual(reader.remaining(), 0)

    def test_memoryview_input(self):
        data = bytearray([0x01, 0x00])
        reader = PacketReader(memoryview(data))
        self.assertEqual(reader.read_byte(), 1)

    def test_buffer_underflow_raises(self):
        reader = PacketReader(b"\x01")
        reader.read_byte()
        with self.assertRaises(IndexError):
            reader.read_byte()

    def test_compress_decompress_roundtrip(self):
        original = b"Minecraft Bedrock packet " * 100
        compressed = compress_batch(original)
        self.assertTrue(compressed[0] == 0xFE)
        self.assertLess(len(compressed), len(original))

        decompressed = decompress_batch(compressed)
        self.assertEqual(decompressed, original)

    def test_decompress_without_header(self):
        import zlib
        raw = zlib.compress(b"no header data")
        result = decompress_batch(raw)
        self.assertEqual(result, b"no header data")

    def test_varint_in_writer_reader(self):
        writer = PacketWriter()
        writer.write_varint(-100).write_uvarint(300)
        reader = PacketReader(writer.get_bytes())
        self.assertEqual(reader.read_varint(), -100)
        self.assertEqual(reader.read_uvarint(), 300)

    def test_writer_len(self):
        w = PacketWriter()
        w.write_byte(1).write_byte(2)
        self.assertEqual(len(w), 2)


if __name__ == "__main__":
    unittest.main()
