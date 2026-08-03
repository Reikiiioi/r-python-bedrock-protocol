"""Tests for version registry and PacketID enum."""

import unittest
from r_python_bedrock_protocol.protocol.versions import (
    get_protocol, get_version, resolve, VERSIONS, PROTOCOL_TO_VERSION,
    LATEST_VERSION, LATEST_PROTOCOL,
)
from r_python_bedrock_protocol.protocol.packets import PacketID, PACKET_NAMES, PACKET_IDS


class TestVersions(unittest.TestCase):

    def test_known_version_lookup(self):
        self.assertEqual(get_protocol("1.20.80"), 671)
        self.assertEqual(get_protocol("1.21.0"), 685)
        self.assertEqual(get_protocol("1.19.0"), 527)

    def test_protocol_to_version(self):
        # Every protocol in the map must resolve back correctly
        for proto, ver in PROTOCOL_TO_VERSION.items():
            self.assertEqual(VERSIONS[ver], proto)

    def test_get_version(self):
        # Protocol 671 is shared by 1.20.80 and 1.20.81; PROTOCOL_TO_VERSION keeps the last one
        self.assertIn(get_version(671), {"1.20.80", "1.20.81"})
        self.assertIn(get_version(685), {"1.21.0", "1.21.1"})

    def test_resolve_string(self):
        ver, proto = resolve("1.20.80")
        self.assertEqual(ver, "1.20.80")
        self.assertEqual(proto, 671)

    def test_resolve_int(self):
        ver, proto = resolve(685)
        self.assertEqual(proto, 685)
        self.assertIn(ver, VERSIONS)

    def test_unknown_version_raises(self):
        with self.assertRaises(ValueError):
            get_protocol("0.0.0")

    def test_unknown_protocol_raises(self):
        with self.assertRaises(ValueError):
            get_version(9999)

    def test_latest_constants(self):
        self.assertIn(LATEST_VERSION, VERSIONS)
        self.assertEqual(VERSIONS[LATEST_VERSION], LATEST_PROTOCOL)

    def test_all_versions_have_valid_protocols(self):
        for ver, proto in VERSIONS.items():
            self.assertIsInstance(proto, int)
            self.assertGreater(proto, 0)


class TestPacketID(unittest.TestCase):

    def test_is_int_enum(self):
        self.assertEqual(PacketID.LOGIN, 0x01)
        self.assertEqual(PacketID.TEXT, 0x09)

    def test_containment(self):
        self.assertIn(0x01, [p.value for p in PacketID])
        self.assertIn(PacketID.LOGIN, PacketID)

    def test_packet_names_dict(self):
        self.assertEqual(PACKET_NAMES[PacketID.TEXT], "text")
        self.assertEqual(PACKET_NAMES[PacketID.LOGIN], "login")

    def test_packet_ids_reverse(self):
        self.assertEqual(PACKET_IDS["text"], PacketID.TEXT)

    def test_full_coverage(self):
        # Every member of PacketID must appear in PACKET_NAMES
        for pid in PacketID:
            self.assertIn(int(pid), PACKET_NAMES, f"PacketID {pid.name} missing from PACKET_NAMES")


if __name__ == "__main__":
    unittest.main()
