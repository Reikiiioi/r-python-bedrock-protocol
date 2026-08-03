"""Tests for datatypes and JWT chain generation."""

import unittest
import uuid
import jwt as pyjwt
from r_python_bedrock_protocol.protocol.serializer import PacketWriter, PacketReader
from r_python_bedrock_protocol.protocol.datatypes import (
    write_uuid, read_uuid, Vec3f, write_vec3f, read_vec3f,
    BlockPos, write_block_pos, read_block_pos,
)
from r_python_bedrock_protocol.crypto.jwt import create_client_chain_jwt, create_client_skin_jwt
from r_python_bedrock_protocol.crypto.ecdh import BedrockCryptoContext


class TestDatatypes(unittest.TestCase):

    def test_uuid_roundtrip(self):
        original = uuid.uuid4()
        w = PacketWriter()
        write_uuid(w, original)
        r = PacketReader(w.get_bytes())
        self.assertEqual(read_uuid(r), original)

    def test_uuid_from_str(self):
        s = str(uuid.uuid4())
        w = PacketWriter()
        write_uuid(w, s)
        r = PacketReader(w.get_bytes())
        self.assertEqual(str(read_uuid(r)), s)

    def test_vec3f_roundtrip(self):
        vec = Vec3f(1.5, -30.25, 100.875)
        w = PacketWriter()
        write_vec3f(w, vec)
        r = PacketReader(w.get_bytes())
        decoded = read_vec3f(r)
        self.assertAlmostEqual(vec.x, decoded.x, places=4)
        self.assertAlmostEqual(vec.y, decoded.y, places=4)
        self.assertAlmostEqual(vec.z, decoded.z, places=4)

    def test_block_pos_roundtrip(self):
        pos = BlockPos(-100, 64, 200)
        w = PacketWriter()
        write_block_pos(w, pos)
        r = PacketReader(w.get_bytes())
        decoded = read_block_pos(r)
        self.assertEqual(decoded.x, pos.x)
        self.assertEqual(decoded.y, pos.y)
        self.assertEqual(decoded.z, pos.z)

    def test_jwt_structure(self):
        ctx = BedrockCryptoContext()
        chain = create_client_chain_jwt("TestUser", crypto_ctx=ctx)
        skin = create_client_skin_jwt("TestUser", crypto_ctx=ctx)

        # Decode without verification to inspect structure
        chain_payload = pyjwt.decode(chain, options={"verify_signature": False})
        skin_payload = pyjwt.decode(skin, options={"verify_signature": False})

        self.assertEqual(chain_payload["extraData"]["displayName"], "TestUser")
        self.assertIn("identityPublicKey", chain_payload)
        self.assertIn("exp", chain_payload)
        self.assertIn("nbf", chain_payload)

        self.assertEqual(skin_payload["ThirdPartyName"], "TestUser")
        self.assertIn("ClientRandomId", skin_payload)
        self.assertIn("SkinData", skin_payload)

    def test_jwt_random_client_id(self):
        # Two skin JWTs from different calls must have different ClientRandomId
        ctx = BedrockCryptoContext()
        s1 = pyjwt.decode(
            create_client_skin_jwt("A", crypto_ctx=ctx),
            options={"verify_signature": False},
        )
        s2 = pyjwt.decode(
            create_client_skin_jwt("A", crypto_ctx=ctx),
            options={"verify_signature": False},
        )
        self.assertNotEqual(s1["ClientRandomId"], s2["ClientRandomId"])


if __name__ == "__main__":
    unittest.main()
