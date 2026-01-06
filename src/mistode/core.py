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

import base64
import json
import random


class NameGenerator:
    def __init__(self, length: int = 16, style: str = "similar", seed=None):
        """
        Encrypted token generator

        Args:
            length: token length, range [8,32]
            length: token length, range [8,32]
            style: naming style - "similar" (visually similar characters),
                   "random" (purely random)
            seed: random seed
        """
        if length < 8 or length > 32:
            raise ValueError(f"Length must be between 8 and 32, current: {length}")

        if style not in ["similar", "random"]:
            raise ValueError(
                f"Unsupported style: {style}, only 'similar' and 'random' are supported"
            )

        self.length = length
        self.style = style
        self.counter = 0
        self.collision_count = 0
        self.generated_tokens: set[str] = set()

        # Create independent random number generator
        self.rng = random.Random(seed)

        # Similar character groups (each group contains visually confused characters)
        self.similar_groups = {
            "Oo0": ["O", "o", "0"],
            "iIlL1": ["i", "I", "l", "L", "1"],
            "b6B8": ["b", "6", "B", "8"],
            "Zz2": ["Z", "z", "2"],
            "Ss5": ["S", "s", "5"],
        }

        self.random_chars = (
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )
        self.random_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def generate(self) -> str:
        """
        Generate unique encrypted token
        """
        max_attempts = 100
        for attempt in range(max_attempts):
            token = self._generate_single()

            # Check for duplicates
            if token not in self.generated_tokens:
                self.generated_tokens.add(token)
                self.counter += 1
                return token

            self.collision_count += 1

        raise RuntimeError(
            f"Unable to generate unique token, collision persists after "
            f"{max_attempts} attempts"
        )

    def _generate_single(self) -> str:
        """
        Generate single token (no duplicate check)
        """
        if self.style == "similar":
            return self._generate_similar()
        else:
            return self._generate_random()

    def _generate_similar(self) -> str:
        """
        Generate similar character style token
        """
        first_char = self.rng.choice(self.random_letters)

        remaining_chars = []
        for _ in range(self.length - 1):
            group = self.rng.choice(list(self.similar_groups.values()))
            remaining_chars.append(self.rng.choice(group))

        return first_char + "".join(remaining_chars)

    def _generate_random(self) -> str:
        """
        Generate pure random style token
        """
        first_char = self.rng.choice(self.random_letters)

        remaining_chars = [
            self.rng.choice(self.random_chars) for _ in range(self.length - 1)
        ]

        return first_char + "".join(remaining_chars)

    def set_length(self, length: int):
        """
        Set token length
        """
        if length < 8 or length > 32:
            raise ValueError(f"Length must be between 8 and 32, current: {length}")
        self.length = length

    def set_style(self, style: str):
        """
        Set naming style
        """
        if style not in ["similar", "random"]:
            raise ValueError(
                f"Unsupported style: {style}, only 'similar' and 'random' "
                "are supported"
            )
        self.style = style

    def get_statistics(self) -> dict:
        """
        Get generation statistics
        """
        return {
            "total_generated": self.counter,
            "collision_count": self.collision_count,
            "unique_tokens": len(self.generated_tokens),
            "current_length": self.length,
            "current_style": self.style,
        }

    def clear_history(self):
        """
        Clear generation history
        """
        self.generated_tokens.clear()
        self.counter = 0
        self.collision_count = 0


class MappingManager:
    def __init__(self):
        self.mapping = {}
        self.reverse_mapping = {}
        self.comments = {}
        self.file_mapping = {}
        self.encryption_key = None
        self.string_quote_types = {}

    def get_obfuscated_name(self, original, generator):
        if original in self.mapping:
            return self.mapping[original]

        new_name = generator.generate()
        self.mapping[original] = new_name
        self.reverse_mapping[new_name] = original
        return new_name

    def add_comment(self, filename, comment):
        if filename not in self.comments:
            self.comments[filename] = []
        self.comments[filename].append(comment)

    def get_comments(self, filename):
        # Check if filename is an obfuscated name
        if filename in self.file_mapping:
            filename = self.file_mapping[filename]
        return self.comments.get(filename, [])

    def add_string_quote_type(self, filename, string_value, quote_type):
        if filename not in self.string_quote_types:
            self.string_quote_types[filename] = []
        self.string_quote_types[filename].append((string_value, quote_type))

    def get_string_quote_types(self, filename):
        # Check if filename is an obfuscated name
        if filename in self.file_mapping:
            filename = self.file_mapping[filename]
        return self.string_quote_types.get(filename, [])

    def register_file(self, original, obfuscated):
        self.file_mapping[obfuscated] = original

    def load_mapping(self, filepath):
        with open(filepath, "r") as f:
            data = json.load(f)
            self.mapping = data.get("twd", {})  # forward
            self.reverse_mapping = {v: k for k, v in self.mapping.items()}
            self.comments = data.get("comments", {})
            self.file_mapping = data.get("files", {})
            self.encryption_key = data.get("encryption_key", None)
            self.string_quote_types = data.get("string_quote_types", {})

    def save_mapping(self, filepath):
        with open(filepath, "w") as f:
            json.dump(
                {
                    "twd": self.mapping,
                    "comments": self.comments,
                    "files": self.file_mapping,
                    "encryption_key": self.encryption_key,
                    "string_quote_types": self.string_quote_types,
                },
                f,
                indent=2,
            )

    def set_encryption_key(self, key):
        self.encryption_key = key

    def get_encryption_key(self):
        return self.encryption_key

    def get_original_name(self, obfuscated):
        return self.reverse_mapping.get(obfuscated, obfuscated)


class StringEncryptor:
    def __init__(self, key=None):
        if key is None:
            # Generate random key between 1-255
            self.key = random.randint(1, 255)
        else:
            self.key = key

    def encrypt(self, text):
        return base64.b64encode(
            bytes(c ^ self.key for c in text.encode("utf-8"))
        ).decode("utf-8")

    def decrypt(self, encrypted_text):
        decoded = base64.b64decode(encrypted_text)
        return bytes(c ^ self.key for c in decoded).decode("utf-8")

    def get_key(self):
        return self.key
