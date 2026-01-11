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
