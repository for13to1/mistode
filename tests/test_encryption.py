import base64

import pytest

from mistode.core import MappingManager, NameGenerator
from mistode.encrypt import EncryptionManager
from mistode.python import PythonObfuscator


class TestEncryption:
    def test_encryption_manager(self):
        key = "secure_password"
        data = "Secret Data"

        manager = EncryptionManager(key)
        encrypted = manager.encrypt(data)
        decrypted = manager.decrypt(encrypted).decode("utf-8")

        assert data == decrypted
        assert data != encrypted

    def test_deterministic_obfuscation(self):
        source = "def hello():\n    print('world')"
        password = "my_password"

        # Run 1
        mm1 = MappingManager()
        gen1 = NameGenerator(seed=EncryptionManager(password).get_seed())
        obfuscator1 = PythonObfuscator(mm1, gen1, "test.py")
        res1 = obfuscator1.obfuscate(source, encryption_key=password)

        # Run 2
        mm2 = MappingManager()
        gen2 = NameGenerator(seed=EncryptionManager(password).get_seed())
        obfuscator2 = PythonObfuscator(mm2, gen2, "test.py")
        res2 = obfuscator2.obfuscate(source, encryption_key=password)

        assert res1 == res2

        # Run 3 with different password
        mm3 = MappingManager()
        gen3 = NameGenerator(seed=EncryptionManager("other").get_seed())
        obfuscator3 = PythonObfuscator(mm3, gen3, "test.py")
        res3 = obfuscator3.obfuscate(source, encryption_key="other")

        assert res1 != res3

    def test_secure_restoration(self):
        source = "def secure_func():\n    pass"
        password = "restore_pass"

        mm = MappingManager()
        gen = NameGenerator(seed=EncryptionManager(password).get_seed())
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        obfuscated = obfuscator.obfuscate(source, encryption_key=password)

        # assert "#@mistode:secure_chunk:" in obfuscated # No longer used
        assert "#@mistode:secure_metadata:" in obfuscated
        assert "#@mistode:chunk:" not in obfuscated

        # Correct restoration
        restored = obfuscator.restore(None, obfuscated, encryption_key=password)
        assert restored.strip() == source.strip()

        # Incorrect password
        with pytest.raises(Exception):
            obfuscator.restore(None, obfuscated, encryption_key="wrong")

        # No password
        with pytest.raises(Exception):
            obfuscator.restore(None, obfuscated)

    def test_structure_restoration_order(self):
        """
        Test that structural preservation maintains correct identifier mapping order.
        AST traversal (obfuscation) vs Token traversal (structure extraction) might differ.
        """
        # A case where token order might matter: usage before definition (unlikely in valid python execution, but parsing wise)
        # or multiple args, nested functions
        source = """
import os
def complex_logic(x, y):
    z = x + y
    def inner():
        return z * 2
    return inner()
"""
        password = "order_check"
        mm = MappingManager()
        gen = NameGenerator(seed=123)
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        obfuscated = obfuscator.obfuscate(source, encryption_key=password)
        restored = obfuscator.restore(None, obfuscated, encryption_key=password)

        print(f"Original:\n{source}")
        print(f"Restored:\n{restored}")

        # Normalize whitespace for comparison
        assert restored.strip() == source.strip()

    def test_formatting_preservation(self):
        """Test that original formatting (spaces, blank lines) is preserved via structure info"""
        source = """
def      spaced(   arg1   ):

    # A comment
    return arg1   +   1
"""
        password = "format_check"
        mm = MappingManager()
        gen = NameGenerator()
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        obfuscated = obfuscator.obfuscate(source, encryption_key=password)
        restored = obfuscator.restore(None, obfuscated, encryption_key=password)

        assert "def      spaced(   arg1   ):" in restored
        assert "   +   1" in restored


class TestEncryptionValidation:
    """Input validation and error paths for EncryptionManager."""

    def test_empty_key_rejected(self):
        with pytest.raises(ValueError):
            EncryptionManager("")

    def test_non_string_key_rejected(self):
        with pytest.raises(TypeError):
            EncryptionManager(123)  # type: ignore[arg-type]

    def test_overlong_key_rejected(self):
        with pytest.raises(ValueError):
            EncryptionManager("a" * 1025)

    def test_invalid_base64_rejected(self):
        manager = EncryptionManager("key")
        with pytest.raises(ValueError):
            manager.decrypt("not-valid-base64!!!")

    def test_bytes_input_encrypt(self):
        manager = EncryptionManager("key")
        encrypted = manager.encrypt(b"raw bytes")
        assert manager.decrypt(encrypted) == b"raw bytes"


class TestStreamCipher:
    """Properties the `stream` cipher must guarantee."""

    def _cipher(self, password: str = "correct horse"):
        from mistode.encrypt import make_cipher

        return make_cipher("stream", password)

    def test_roundtrip(self):
        cipher = self._cipher()
        payload = b"payload with binary \x00\xff bytes"
        assert cipher.decrypt(cipher.encrypt(payload)) == payload

    def test_deterministic_for_reproducible_builds(self):
        cipher = self._cipher()
        # Identical input must produce identical output; --seed builds rely
        # on the whole artifact being byte-reproducible.
        assert cipher.encrypt(b"same") == cipher.encrypt(b"same")

    def test_distinct_payloads_do_not_share_a_keystream(self):
        cipher = self._cipher()
        a = cipher.encrypt(b"A" * 64)
        b = cipher.encrypt(b"B" * 64)
        assert a != b

        raw_a = base64.b64decode(a)
        raw_b = base64.b64decode(b)
        # Nonces differ, so the Xor of the ciphertexts must not be all zero.
        assert raw_a[:16] != raw_b[:16]
        assert raw_a[16:64] != raw_b[16:64]

    def test_known_plaintext_does_not_unlock_other_payloads(self):
        cipher = self._cipher()
        known = b"import os"
        known_ct = base64.b64decode(cipher.encrypt(known))
        keystream = bytes(c ^ p for c, p in zip(known_ct[16:], known))

        other_ct = base64.b64decode(cipher.encrypt(b"def secret(): pass"))
        # Applying the first payload's keystream must not yield the second
        # payload's plaintext.
        derived = bytes(c ^ k for c, k in zip(other_ct[16:], keystream))
        assert not derived.startswith(b"def secret")

    def test_tampering_is_detected(self):
        cipher = self._cipher()
        raw = bytearray(base64.b64decode(cipher.encrypt(b"important data")))
        raw[20] ^= 0x01
        with pytest.raises(ValueError, match="Integrity check failed"):
            cipher.decrypt(base64.b64encode(bytes(raw)).decode("ascii"))

    def test_wrong_password_is_rejected(self):
        payload = self._cipher("right").encrypt(b"data")
        with pytest.raises(ValueError, match="Integrity check failed"):
            self._cipher("wrong").decrypt(payload)

    def test_short_payload_is_reported_as_legacy(self):
        # Payloads shorter than nonce+tag can only come from Mistode <=0.1.3.
        with pytest.raises(ValueError, match="older Mistode version"):
            self._cipher().decrypt(base64.b64encode(b"tiny").decode("ascii"))


class TestCipherFactory:
    def test_none_ignores_password(self):
        from mistode.encrypt import NullCipher, make_cipher

        cipher = make_cipher("none", "irrelevant")
        assert isinstance(cipher, NullCipher)
        assert cipher.decrypt(cipher.encrypt("plain")) == b"plain"

    def test_stream_requires_password(self):
        from mistode.encrypt import make_cipher

        with pytest.raises(ValueError, match="requires a password"):
            make_cipher("stream", None)

    def test_unknown_cipher_rejected(self):
        from mistode.encrypt import make_cipher

        with pytest.raises(ValueError, match="Unsupported cipher"):
            make_cipher("rot13", "pw")

    def test_unknown_cipher_can_fall_back(self):
        from mistode.encrypt import NullCipher, make_cipher

        assert isinstance(make_cipher("future", None, strict=False), NullCipher)


class TestCipherErrorsSurface:
    """Cipher failures must not be reported as unrelated errors."""

    def test_layout_wrong_password_reports_integrity_failure(self):
        from mistode.encrypt import StreamCipher
        from mistode.layout import LayoutEngine

        engine = LayoutEngine()
        obfuscated = engine.obfuscate_token_stream(
            "a = 1\n", {}, StreamCipher("correct")
        )
        with pytest.raises(ValueError, match="Integrity check failed"):
            engine.restore_token_stream(obfuscated, {}, StreamCipher("wrong"))

    def test_layout_missing_password_reports_it(self):
        from mistode.encrypt import StreamCipher
        from mistode.layout import LayoutEngine

        engine = LayoutEngine()
        obfuscated = engine.obfuscate_token_stream(
            "a = 1\n", {}, StreamCipher("correct")
        )
        with pytest.raises(ValueError, match="Encrypted payload"):
            engine.restore_token_stream(obfuscated, {}, None)
