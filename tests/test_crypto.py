"""Unit tests for ECDH key exchange and AES-256-CFB8 cipher."""

import unittest
from r_python_bedrock_protocol.crypto.ecdh import BedrockCryptoContext
from r_python_bedrock_protocol.crypto.cipher import BedrockCipher


class TestCrypto(unittest.TestCase):

    def test_ecdh_shared_secret(self):
        ctx1 = BedrockCryptoContext()
        ctx2 = BedrockCryptoContext()

        key1 = ctx1.compute_shared_secret(ctx2.export_public_key_der())
        key2 = ctx2.compute_shared_secret(ctx1.export_public_key_der())

        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 32)

    def test_cipher_encrypt_decrypt(self):
        key = b"\x01" * 32
        cipher1 = BedrockCipher(key)
        cipher2 = BedrockCipher(key)

        original_data = b"Minecraft Bedrock encrypted packet payload test"
        encrypted = cipher1.encrypt(original_data)
        decrypted = cipher2.decrypt(encrypted)

        self.assertEqual(original_data, decrypted)


if __name__ == "__main__":
    unittest.main()
