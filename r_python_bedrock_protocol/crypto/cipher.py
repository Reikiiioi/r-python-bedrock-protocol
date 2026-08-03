from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
try:
    from cryptography.hazmat.decrepit.ciphers.modes import CFB8
except ImportError:
    from cryptography.hazmat.primitives.ciphers.modes import CFB8
from cryptography.hazmat.backends import default_backend

class BedrockCipher:

    def __init__(self, key: bytes, iv: bytes | None=None):
        if len(key) != 32:
            raise ValueError('Key must be 32 bytes for AES-256')
        self.key = key
        self.iv = iv if iv is not None else key[:16]
        self._encryptor = Cipher(algorithms.AES(self.key), CFB8(self.iv), backend=default_backend()).encryptor()
        self._decryptor = Cipher(algorithms.AES(self.key), CFB8(self.iv), backend=default_backend()).decryptor()

    def encrypt(self, data: bytes) -> bytes:
        return self._encryptor.update(data)

    def decrypt(self, data: bytes) -> bytes:
        return self._decryptor.update(data)
