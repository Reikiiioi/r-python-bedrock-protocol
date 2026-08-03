import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

class BedrockCryptoContext:

    def __init__(self):
        self.private_key = ec.generate_private_key(ec.SECP384R1())
        self.public_key = self.private_key.public_key()
        self.shared_secret = None
        self.aes_key = None

    def export_public_key_der(self) -> bytes:
        return self.public_key.public_bytes(encoding=serialization.Encoding.DER, format=serialization.PublicFormat.SubjectPublicKeyInfo)

    def export_public_key_b64(self) -> str:
        return base64.b64encode(self.export_public_key_der()).decode('ascii')

    def compute_shared_secret(self, remote_pub_der: bytes) -> bytes:
        remote_key = serialization.load_der_public_key(remote_pub_der)
        if not isinstance(remote_key, ec.EllipticCurvePublicKey):
            raise ValueError('Remote key must be an EC public key')
        self.shared_secret = self.private_key.exchange(ec.ECDH(), remote_key)
        digest = hashlib.sha256()
        digest.update(b'\x00\x00\x00\x01')
        digest.update(self.shared_secret)
        self.aes_key = digest.digest()
        return self.aes_key
