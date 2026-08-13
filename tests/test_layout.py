import pytest

from mistode.core import MappingManager, NameGenerator
from mistode.python import PythonObfuscator


class TestLayoutEngine:
    def test_no_source_chunks_in_obfuscated_file(self):
        """Verify that NO source chunks (neither plain nor encrypted) are injected."""
        source = "def secret_logic():\n    pass"
        password = "secure_password"

        mm = MappingManager()
        gen = NameGenerator()
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        obfuscated = obfuscator.obfuscate(source, encryption_key=password)

        # Check absence of PLAIN chunk tags if encrypted
        assert "#@mistode:chunk:" not in obfuscated

        # Check presence of SECURE chunk tags (layout is now interleaved)
        assert "#@mistode:secure_chunk:" in obfuscated

        # Check presence of metadata (where OTHER mappings are stored)
        assert "#@mistode:secure_metadata:" in obfuscated

    def test_layout_restoration_comments_and_whitespace(self):
        """Verify that comments and whitespace are restored via LayoutEngine."""
        source = """
# Header Comment
def    spaced   (  args  ):
    # Inner Comment
    return args + 1
"""
        password = "layout_test"
        mm = MappingManager()
        gen = NameGenerator(style="random")
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        obfuscated = obfuscator.obfuscate(source, encryption_key=password)
        restored = obfuscator.restore(None, obfuscated, encryption_key=password)

        # Exact restoration check
        assert restored.strip() == source.strip()
        assert "# Header Comment" in restored
        assert "# Inner Comment" in restored
        assert "def    spaced" in restored

    def test_string_style_preservation(self):
        """Verify that string styles (f-strings, raw strings) are preserved."""
        # Note: current LayoutEngine implementation might only preserve surrounding context,
        # let's seeing if it handles f-strings correctly via ast.unparse knowing it's joinedstr vs str
        source = '''
def string_test():
    x = f"value: {1+1}"
    y = r"raw\\path"
    z = """Docstring
    Multiline"""
'''
        password = "string_test"
        mm = MappingManager()
        gen = NameGenerator()
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        obfuscated = obfuscator.obfuscate(source, encryption_key=password)
        restored = obfuscator.restore(None, obfuscated, encryption_key=password)

        # Check if styles preserved
        # Note: ast.unparse might change f"..." to f'...' or vice versa, but structure should match.
        # Strict equality might fail if unparse normalizes quotes differently and LayoutEngine doesn't force it back.
        # But we aim for functional equivalence + layout preservation.

        print(f"Original:\n{source}")
        print(f"Restored:\n{restored}")

        assert 'f"value: {1+1}"' in restored or "f'value: {1+1}'" in restored
        assert 'r"raw\\path"' in restored or "r'raw\\path'" in restored
        assert '"""Docstring' in restored

    def test_secure_restoration_requires_key(self):
        source = "def secure(): pass"
        password = "password123"

        mm = MappingManager()
        gen = NameGenerator()
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        obfuscated = obfuscator.obfuscate(source, encryption_key=password)

        # Fail without key
        with pytest.raises(Exception):
            obfuscator.restore(None, obfuscated)

        # Fail with wrong key
        with pytest.raises(Exception):
            obfuscator.restore(None, obfuscated, encryption_key="wrong")

        # Succeed with correct key
        restored = obfuscator.restore(None, obfuscated, encryption_key=password)
        assert restored.strip() == source.strip()
