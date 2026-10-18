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
from src.mistode.core import MappingManager, NameGenerator


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
        assert mm.source_encoding is None

    def test_save_load_mapping(self):
        """
        Test mapping save and load
        """
        mm = MappingManager()
        mm.mapping = {"original_name": "obfuscated_name"}
        mm.reverse_mapping = {"obfuscated_name": "original_name"}
        mm.source_encoding = "utf-8"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            mapping_file = f.name

        try:
            mm.save_mapping(mapping_file)
            assert Path(mapping_file).exists()

            mm2 = MappingManager()
            mm2.load_mapping(mapping_file)

            assert mm2.mapping == {"original_name": "obfuscated_name"}
            assert mm2.reverse_mapping == {"obfuscated_name": "original_name"}
            assert mm2.source_encoding == "utf-8"
        finally:
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

    def test_mapping_roundtrip_preserves_encoding(self):
        """
        Test save/load keeps the mapping and the source encoding
        """
        mm = MappingManager()
        mm.mapping = {"api": "x1"}
        mm.source_encoding = "gb18030"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            mapping_file = f.name

        try:
            mm.save_mapping(mapping_file)
            mm2 = MappingManager()
            mm2.load_mapping(mapping_file)
            assert mm2.get_original_name("x1") == "api"
            assert mm2.source_encoding == "gb18030"
        finally:
            if Path(mapping_file).exists():
                Path(mapping_file).unlink()
