"""
Payload ciphers.

``none``
    Plain base64: anyone holding the file can restore it.

``stream``
    Authenticated stream cipher from stdlib primitives: scrypt-derived key,
    SHA-256 CTR keystream, HMAC-SHA256 tag. The nonce is derived from the
    payload (SIV-style), so distinct payloads never share a keystream while
    identical inputs stay byte-reproducible. Wire format::

        nonce (16 bytes) || ciphertext || tag (32 bytes)
"""

import base64
import hashlib
import hmac

NONCE_SIZE = 16
TAG_SIZE = 32
KEY_SIZE = 32
BLOCK_SIZE = 32

# ~20ms per derivation: slows offline guessing without slowing the CLI.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 64 * 1024 * 1024
_SCRYPT_SALT = b"mistode-kdf-v1"

_SUPPORTED = ("none", "stream")

# Cache so repeated use of one password pays the scrypt cost once.
_derived_keys: dict[str, bytes] = {}


def _derive_master_key(password: str) -> bytes:
    cached = _derived_keys.get(password)
    if cached is not None:
        return cached
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=_SCRYPT_SALT,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_SIZE,
        maxmem=SCRYPT_MAXMEM,
    )
    if len(_derived_keys) > 8:
        _derived_keys.clear()
    _derived_keys[password] = derived
    return derived


def derive_seed(password: str) -> int:
    """Seed for identifier generation, shared with the cipher's KDF."""
    return int.from_bytes(_derive_master_key(password)[:8], "big")


class NullCipher:
    """No encryption: plain base64 (still compressed by the caller)."""

    name = "none"

    def encrypt(self, data: str | bytes) -> str:
        if isinstance(data, str):
            data = data.encode("utf-8")
        return base64.b64encode(data).decode("ascii")

    def decrypt(self, data: str) -> bytes:
        try:
            return base64.b64decode(data)
        except Exception:
            raise ValueError("Invalid base64 input")

    def get_seed(self) -> int:
        return 0


class StreamCipher:
    """Authenticated stream cipher with a per-payload nonce."""

    name = "stream"

    def __init__(self, password: str):
        if not password:
            raise ValueError("Password cannot be empty")
        if not isinstance(password, str):
            raise TypeError("Password must be a string")
        if len(password) > 1024:
            raise ValueError(
                "Password length exceeds maximum allowed length of 1024 characters"
            )
        self._master = _derive_master_key(password)

    def _payload_keys(self, nonce: bytes) -> tuple[bytes, bytes]:
        enc_key = hmac.new(self._master, nonce + b"enc", hashlib.sha256).digest()
        mac_key = hmac.new(self._master, nonce + b"mac", hashlib.sha256).digest()
        return enc_key, mac_key

    def _nonce_for(self, data: bytes) -> bytes:
        """Per-payload nonce derived from the plaintext (SIV-style).

        Equal payloads stay byte-reproducible; different payloads get
        unrelated keystreams, so one known plaintext cannot unlock the rest.
        """
        return hmac.new(self._master, b"nonce" + data, hashlib.sha256).digest()[
            :NONCE_SIZE
        ]

    @staticmethod
    def _keystream(enc_key: bytes, length: int) -> bytes:
        blocks = []
        for i in range((length + BLOCK_SIZE - 1) // BLOCK_SIZE):
            blocks.append(hashlib.sha256(enc_key + i.to_bytes(8, "big")).digest())
        return b"".join(blocks)[:length]

    def encrypt(self, data: str | bytes) -> str:
        if isinstance(data, str):
            data = data.encode("utf-8")
        nonce = self._nonce_for(data)
        enc_key, mac_key = self._payload_keys(nonce)
        stream = self._keystream(enc_key, len(data))
        ciphertext = bytes(a ^ b for a, b in zip(data, stream))
        tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        return base64.b64encode(nonce + ciphertext + tag).decode("ascii")

    def decrypt(self, data: str) -> bytes:
        try:
            raw = base64.b64decode(data)
        except Exception:
            raise ValueError("Invalid base64 input")
        if len(raw) < NONCE_SIZE + TAG_SIZE:
            # Mistode <= 0.1.3 encrypted payloads without a nonce or tag.
            # They cannot be authenticated, so restoration is refused with
            # an explicit message instead of a misleading integrity error.
            raise ValueError(
                "This payload was written by an older Mistode version and "
                "cannot be authenticated. Re-obfuscate the source, or restore "
                "it with the Mistode version that produced it."
            )
        nonce = raw[:NONCE_SIZE]
        ciphertext = raw[NONCE_SIZE:-TAG_SIZE]
        tag = raw[-TAG_SIZE:]
        enc_key, mac_key = self._payload_keys(nonce)
        expected = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            raise ValueError(
                "Integrity check failed: wrong password or tampered payload "
                "(identifier mapping could not be recovered)"
            )
        stream = self._keystream(enc_key, len(ciphertext))
        return bytes(a ^ b for a, b in zip(ciphertext, stream))

    def get_seed(self) -> int:
        return int.from_bytes(self._master[:8], "big")


def make_cipher(kind: str, password: str | None, *, strict: bool = True):
    """Build a cipher for ``kind``.

    Anything but ``none`` needs a password. ``strict=False`` falls back to
    ``none`` for unknown kinds, so restore stays forward-compatible.
    """
    if kind not in _SUPPORTED:
        if strict:
            raise ValueError(
                f"Unsupported cipher: {kind}, choose from {', '.join(_SUPPORTED)}"
            )
        return NullCipher()
    if kind == "none":
        return NullCipher()
    if not password:
        raise ValueError(f"Cipher '{kind}' requires a password")
    return StreamCipher(password)


# Backwards-compatible name: the default cipher when a password is given.
EncryptionManager = StreamCipher
