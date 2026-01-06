# Copyright (C) 2026 for13to1 <for13to1@outlook.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Core Module Tests"""

import tempfile
from pathlib import Path

import pytest

# Import test module
from src.mistode.core import MappingManager, NameGenerator, StringEncryptor


class TestNameGenerator:
    """
    NameGenerator Test Class
    """

    def test_generator_initialization(self):
        """
        Test generator initialization
        """
        # Normal initialization
        gen = NameGenerator(length=16, style="random", seed=42)
        assert gen.length == 16
        assert gen.style == "random"

        # Test boundaries
        with pytest.raises(ValueError):
            NameGenerator(length=7)  # Less than minimum

        with pytest.raises(ValueError):
            NameGenerator(length=33)  # Greater than maximum

        with pytest.raises(ValueError):
            NameGenerator(style="invalid")  # Invalid style

    def test_token_generation(self):
        """
        Test token generation
        """
        gen = NameGenerator(length=8, seed=42)

        # Generate multiple tokens
        tokens = [gen.generate() for _ in range(10)]

        # Verify length
        for token in tokens:
            assert len(token) == 8
            assert token[0].isalpha()  # First character cannot be digit

        # Verify uniqueness
        assert len(set(tokens)) == len(tokens)

    def test_similar_style(self):
        """
        Test similar character style
        """
        gen = NameGenerator(style="similar", seed=42)
        token = gen.generate()

        # Verify first character is letter
        assert token[0].isalpha()

        # Verify characters are from similar groups
        similar_chars = "Oo0iIlL1b6B8Zz2Ss5"
        for char in token[1:]:  # Skip first character
            assert char in similar_chars

    def test_random_style(self):
        """
        Test random character style
        """
        gen = NameGenerator(style="random", seed=42)
        token = gen.generate()

        # Verify first character is letter
        assert token[0].isalpha()

        # Verify characters are from alphanumeric set
        valid_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        for char in token:
            assert char in valid_chars

    def test_length_change(self):
        """
        Test length change
        """
        gen = NameGenerator(length=10)
        token1 = gen.generate()
        assert len(token1) == 10

        gen.set_length(15)
        token2 = gen.generate()
        assert len(token2) == 15

        with pytest.raises(ValueError):
            gen.set_length(7)


class TestMappingManager:
    """
    MappingManager Test Class
    """

    def test_mapping_initialization(self):
        """
        Test mapping manager initialization
        """
        mm = MappingManager()
        assert mm.mapping == {}
        assert mm.reverse_mapping == {}
        assert mm.file_mapping == {}

    def test_file_mapping_operations(self):
        """
        Test file mapping operations
        """
        mm = MappingManager()

        # Register file mapping
        mm.register_file("original.py", "obfuscated.py")
        assert "obfuscated.py" in mm.file_mapping
        assert mm.file_mapping["obfuscated.py"] == "original.py"

        # Test comment and string quote type mapping
        mm.add_comment("original.py", "test comment")
        mm.add_string_quote_type("original.py", "test string", "double")

        comments = mm.get_comments("original.py")
        quote_types = mm.get_string_quote_types("original.py")

        assert "test comment" in comments
        # quote_types is a list, check if it contains expected item
        assert any("test string" in str(item) for item in quote_types)

    def test_file_mapping(self):
        """
        Test file mapping
        """
        mm = MappingManager()

        # Register file mapping
        mm.register_file("original.py", "obfuscated.py")
        assert "obfuscated.py" in mm.file_mapping
        assert mm.file_mapping["obfuscated.py"] == "original.py"

    def test_save_load_mapping(self):
        """
        Test mapping save and load
        """
        mm = MappingManager()

        # Add some file mappings and comments
        mm.register_file("test.py", "test.obf.py")
        mm.add_comment("test.py", "test comment")
        mm.add_string_quote_type("test.py", "test string", "double")

        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            mapping_file = f.name

        try:
            mm.save_mapping(mapping_file)

            # Verify file exists
            assert Path(mapping_file).exists()

            # Create new manager and load mapping
            mm2 = MappingManager()
            mm2.load_mapping(mapping_file)

            # Verify mapping loaded correctly
            assert mm2.file_mapping == {"test.obf.py": "test.py"}

        finally:
            # Clean up temporary file
            if Path(mapping_file).exists():
                Path(mapping_file).unlink()

    def test_load_nonexistent_file(self):
        """
        Test loading nonexistent file
        """
        mm = MappingManager()

        with pytest.raises(FileNotFoundError):
            mm.load_mapping("nonexistent.json")

    def test_get_original_name(self):
        """
        Test getting original name
        """
        mm = MappingManager()

        # Add mapping
        mm.mapping["original_name"] = "obfuscated_name"
        mm.reverse_mapping["obfuscated_name"] = "original_name"

        # Test getting original name
        assert mm.get_original_name("obfuscated_name") == "original_name"
        assert mm.get_original_name("unknown") == "unknown"


class TestStringEncryptor:
    """
    StringEncryptor Test Class
    """

    def test_encryptor_initialization(self):
        """
        Test encryptor initialization
        """
        enc = StringEncryptor()
        assert 1 <= enc.key <= 255

        enc2 = StringEncryptor(key=42)
        assert enc2.key == 42

    def test_encryption_decryption(self):
        """
        Test encryption and decryption
        """
        enc = StringEncryptor(key=42)
        original = "Hello, World! Testing Chinese characters"
        encrypted = enc.encrypt(original)
        decrypted = enc.decrypt(encrypted)

        assert original == decrypted
        assert encrypted != original

    def test_encryptor_get_key(self):
        """
        Test get key
        """
        enc = StringEncryptor(key=123)
        assert enc.get_key() == 123


class TestNameGeneratorEdgeCases:
    """
    NameGenerator Edge Cases Test
    """

    def test_generator_boundaries(self):
        """
        Test generator boundaries
        """
        gen8 = NameGenerator(length=8)
        token = gen8.generate()
        assert len(token) == 8

        gen32 = NameGenerator(length=32)
        token = gen32.generate()
        assert len(token) == 32

    def test_style_change(self):
        """
        Test style change
        """
        gen = NameGenerator(style="similar")
        assert gen.style == "similar"

        gen.set_style("random")
        assert gen.style == "random"

        with pytest.raises(ValueError):
            gen.set_style("invalid")

    def test_statistics(self):
        """
        Test statistics
        """
        gen = NameGenerator(seed=42)
        for _ in range(5):
            gen.generate()

        stats = gen.get_statistics()
        assert stats["total_generated"] == 5
        assert stats["unique_tokens"] == 5
        assert stats["collision_count"] == 0
        assert stats["current_length"] == 16
        assert stats["current_style"] == "similar"

    def test_clear_history(self):
        """
        Test clear history
        """
        gen = NameGenerator(seed=42)
        for _ in range(3):
            gen.generate()

        gen.clear_history()

        stats = gen.get_statistics()
        assert stats["total_generated"] == 0
        assert stats["unique_tokens"] == 0
        assert stats["collision_count"] == 0

    def test_duplicate_detection(self):
        """
        Test duplicate detection
        """
        gen = NameGenerator(seed=42)
        tokens = [gen.generate() for _ in range(20)]

        assert len(tokens) == len(set(tokens))

    def test_seed_reproducibility(self):
        """
        Test seed reproducibility
        """
        gen1 = NameGenerator(seed=12345)
        tokens1 = [gen1.generate() for _ in range(10)]

        gen2 = NameGenerator(seed=12345)
        tokens2 = [gen2.generate() for _ in range(10)]

        assert tokens1 == tokens2


class TestMappingManagerEdgeCases:
    """
    MappingManager Edge Cases Test
    """

    def test_empty_mapping(self):
        """
        Test empty mapping
        """
        mm = MappingManager()
        assert mm.get_original_name("anything") == "anything"
        assert mm.get_comments("anyfile") == []
        assert mm.get_string_quote_types("anyfile") == []

    def test_duplicate_file_registration(self):
        """
        Test duplicate file registration
        """
        mm = MappingManager()
        mm.register_file("orig.py", "obf.py")
        mm.register_file("orig2.py", "obf.py")

        assert mm.file_mapping["obf.py"] == "orig2.py"

    def test_comment_retrieval(self):
        """
        Test comment retrieval
        """
        mm = MappingManager()

        mm.add_comment("test.py", "comment1")
        mm.add_comment("test.py", "comment2")

        comments = mm.get_comments("test.py")
        assert len(comments) == 2
        assert "comment1" in comments
        assert "comment2" in comments

    def test_string_quote_types(self):
        """
        Test string quote types
        """
        mm = MappingManager()

        mm.add_string_quote_type("test.py", "string1", "single")
        mm.add_string_quote_type("test.py", "string2", "double")

        quote_types = mm.get_string_quote_types("test.py")
        assert len(quote_types) == 2

    def test_encryption_key(self):
        """
        Test encryption key
        """
        mm = MappingManager()
        assert mm.get_encryption_key() is None

        mm.set_encryption_key("secret_key")
        assert mm.get_encryption_key() == "secret_key"

    def test_mapping_with_key(self):
        """
        Test save/load mapping with key
        """
        mm = MappingManager()
        mm.register_file("test.py", "test.obf.py")
        mm.set_encryption_key("my_secret_key")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            mapping_file = f.name

        try:
            mm.save_mapping(mapping_file)

            mm2 = MappingManager()
            mm2.load_mapping(mapping_file)

            assert mm2.file_mapping == {"test.obf.py": "test.py"}
            assert mm2.encryption_key == "my_secret_key"
        finally:
            if Path(mapping_file).exists():
                Path(mapping_file).unlink()
