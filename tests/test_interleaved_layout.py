from mistode.core import MappingManager, NameGenerator
from mistode.layout import LayoutEngine
from mistode.python import PythonObfuscator


class TestInterleavedLayout:
    def test_interleaved_comments_generation(self):
        """Verify that layout comments are generated interleaving with code."""
        source = """
def foo():
    x = 1
    return x
"""
        mm = MappingManager()
        gen = NameGenerator()
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        # Test with NO encryption first to see clear text chunks if base64
        obfuscated = obfuscator.obfuscate(
            source, encryption_key=None, embed_metadata=True
        )

        # Should have multiple chunks
        # One for 'def foo():', one for 'x=1', one for 'return x'
        lines = obfuscated.splitlines()
        chunk_lines = [line for line in lines if line.startswith("#@mistode:chunk:")]

        assert len(chunk_lines) >= 3, (
            f"Expected at least 3 layout chunks, found {len(chunk_lines)}"
        )

        # Restoration check
        restored = obfuscator.restore(None, obfuscated)
        assert restored.strip() == source.strip()

    def test_interleaved_comments_restoration_encrypted(self):
        """Verify restoration works with encrypted interleaved comments."""
        source = """
# A comment
x = "string with spaces"
"""
        password = "secure_interleave"
        mm = MappingManager()
        gen = NameGenerator()
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        obfuscated = obfuscator.obfuscate(source, encryption_key=password)

        assert "#@mistode:secure_chunk:" in obfuscated
        assert "#@mistode:chunk:" not in obfuscated  # Should use secure variant

        restored = obfuscator.restore(None, obfuscated, encryption_key=password)
        assert restored.strip() == source.strip()
        assert "# A comment" in restored

    def test_layout_engine_logic_newlines(self):
        """Test LayoutEngine specific logic for newlines"""
        layout_engine = LayoutEngine()
        source = "a = 1\nb = 2"
        # Dummy replacements
        replacements = {}

        obfuscated = layout_engine.obfuscate_token_stream(
            source, replacements, encryption_manager=None
        )

        assert "#@mistode:chunk:" in obfuscated
        assert "a=1" in obfuscated.replace(" ", "")
        assert "b=2" in obfuscated.replace(" ", "")

    def test_trailing_newline_preservation(self):
        """Verify that trailing newlines are preserved exactly."""
        mm = MappingManager()
        gen = NameGenerator()
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        # Case 1: With trailing newline
        source_with_nl = "x = 1\n"
        obfuscated_with = obfuscator.obfuscate(source_with_nl)
        restored_with = obfuscator.restore(None, obfuscated_with)
        assert restored_with == source_with_nl
        assert restored_with.endswith("\n")

        # Case 2: Without trailing newline
        source_no_nl = "x = 1"
        obfuscated_no = obfuscator.obfuscate(source_no_nl)
        restored_no = obfuscator.restore(None, obfuscated_no)
        assert restored_no == source_no_nl
        assert not restored_no.endswith("\n")
