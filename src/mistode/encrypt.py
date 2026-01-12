"""
Encryption Manager for Mistode
Provides secure, key-based encryption for source chunks and metadata.
"""

import base64
import hashlib
from typing import Union


class EncryptionManager:
    """
    Manages encryption and decryption of data using a user-provided key.
    Uses a CTR-mode like stream cipher based on SHA-256 for high entropy.
    """

    def __init__(self, key: str):
        """
        Initialize with a string key.
        The key is hashed to create a 32-byte master key.
        """
        if not key:
            raise ValueError("Key cannot be empty")
        if not isinstance(key, str):
            raise TypeError("Key must be a string")
        if (
            len(key) > 1024
        ):  # Prevent extremely long keys that could cause memory issues
            raise ValueError(
                "Key length exceeds maximum allowed length of 1024 characters"
            )
        # SHA-256 to get a fixed-length key from arbitrary string
        self.key_hash = hashlib.sha256(key.encode("utf-8")).digest()

    def _xor_cipher(self, data: bytes) -> bytes:
        """
        Encodes/Decodes data using a stream cipher.
        Keystream is generated via SHA-256(Key + BlockCounter).
        """
        output = bytearray(len(data))
        block_size = 32  # SHA-256 output size
        num_blocks = (len(data) + block_size - 1) // block_size

        for i in range(num_blocks):
            # Generate keystream block: SHA256(Key + Counter)
            # This ensures each block has a unique mask derived from the key
            counter_bytes = i.to_bytes(8, "big")
            keystream_block = hashlib.sha256(self.key_hash + counter_bytes).digest()

            start = i * block_size
            end = min(start + block_size, len(data))

            for j in range(start, end):
                # keystream_block index is (j - start)
                output[j] = data[j] ^ keystream_block[j - start]

        return bytes(output)

    def encrypt(self, data: Union[str, bytes]) -> str:
        """
        Encrypt data and return base64 string.
        """
        if isinstance(data, str):
            data = data.encode("utf-8")

        encrypted = self._xor_cipher(data)
        return base64.b64encode(encrypted).decode("ascii")

    def decrypt(self, data: str) -> bytes:
        """
        Decrypt base64 string and return bytes.
        """
        try:
            encrypted = base64.b64decode(data)
        except Exception:
            raise ValueError("Invalid base64 input")

        return self._xor_cipher(encrypted)

    def get_seed(self) -> int:
        """
        Derive a deterministic integer seed from the key.
        Used for seeding the random number generator for variable names.
        """
        # Take first 8 bytes of key hash and convert to int
        return int.from_bytes(self.key_hash[:8], "big")
