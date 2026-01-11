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
import math
import os
import re
import shutil
import subprocess
import tempfile
import zlib
from typing import Iterator, Match, Optional, Set

from .core import MappingManager, NameGenerator


class CObfuscator:
    """
    Obfuscator for C programming language code.

    Features:
    - Identifier renaming (variables, functions, structs).
    - String literal preservation.
    - Preprocessor directive preservation.
    - Comment scrambling.
    - Embedded metadata for restoration (Keys).
    - Embedded compressed source for lossless restoration.
    - Dynamic discovery of external symbols (using gcc/nm or heuristic fallback).
    """

    # Basic C Types
    TYPE_KEYWORDS = {
        "void",
        "char",
        "short",
        "int",
        "long",
        "float",
        "double",
        "signed",
        "unsigned",
        "bool",
        "struct",
        "union",
        "enum",
    }

    # C Control Flow and Storage Class Keywords
    KEYWORDS = {
        "auto",
        "break",
        "case",
        "const",
        "continue",
        "default",
        "do",
        "else",
        "extern",
        "for",
        "goto",
        "if",
        "register",
        "return",
        "sizeof",
        "static",
        "switch",
        "typedef",
        "volatile",
        "while",
        "true",
        "false",  # C99/stdbool macros often treated as keywords
    } | TYPE_KEYWORDS

    # Preprocessor Directives to avoid obfuscating
    PREPROCESSOR_DIRECTIVES = {
        "include",
        "define",
        "ifdef",
        "ifndef",
        "endif",
        "error",
        "pragma",
        "undef",
        "line",
        "elif",
        "else",
    }

    # Tokenizer Regex Matching Groups
    # 1. String Literals
    # 2. Include Directives
    # 3. Identifiers
    # 4. Comments
    # 5. Other (operators, punctuation, whitespace)
    TOKEN_PATTERN = re.compile(
        r'("(?:\\.|[^"\\])*")|'
        r"(#\s*include\s*<[^>]+>)|"
        r"([a-zA-Z_]\w*)|"
        r"(/\*[^*]*\*+(?:[^/*][^*]*\*+)*/|//[^\n]*)"
        r"|(\s+|.)",
        re.DOTALL,
    )

    def __init__(
        self,
        mapping_manager: MappingManager,
        generator: NameGenerator,
        filename: str = "unknown",
    ):
        self.mm = mapping_manager
        self.gen = generator
        self.filename = filename

        # Reserved words include keywords and "main"
        self.reserved_identifiers = self.KEYWORDS.copy()
        self.reserved_identifiers.add("main")

    def _tokenize(self, text: str) -> Iterator[Match[str]]:
        """Yields regex matches for tokens in the C source code."""
        return self.TOKEN_PATTERN.finditer(text)

    def _scan_for_external_symbols(self, source_code: str) -> Set[str]:
        """
        Heuristic scanner to identify external symbols (used but not defined in file).
        Acts as a fallback when compiler tools are unavailable, or as a primary
        analysis for simple cases.
        """
        defined_symbols = set()
        all_identifiers = set()

        tokens = list(self._tokenize(source_code))
        n = len(tokens)

        for i, match in enumerate(tokens):
            identifier = match.group(3)
            # Only process Identifiers
            if not identifier:
                continue

            all_identifiers.add(identifier)
            if identifier in self.reserved_identifiers:
                continue

            # Check for Definition Patterns

            # Pattern 1: Function Definition "Identifier (...) {"
            # We look ahead for matched parens (...) followed by {
            if i + 1 < n:
                next_token = tokens[i + 1]  # Next token Match object
                next_str = next_token.group(
                    5
                )  # "Other" group usually matches operators

                if next_str and next_str.strip() == "(":
                    is_func_def = False
                    balance = 1
                    # Scan forward to find closing ')'
                    for j in range(i + 2, n):
                        sub_str = tokens[j].group(5)
                        if sub_str:
                            s = sub_str.strip()
                            if s == "(":
                                balance += 1
                            elif s == ")":
                                balance -= 1
                                if balance == 0:
                                    # Found closing ')'. Check next
                                    # non-whitespace char for '{'
                                    for k in range(j + 1, n):
                                        k_str = tokens[k].group(5)
                                        # Skip whitespace
                                        if k_str and not k_str.strip():
                                            continue
                                        if k_str and k_str.strip() == "{":
                                            is_func_def = True
                                        break
                                    break

                    if is_func_def:
                        defined_symbols.add(identifier)
                        continue

            # Pattern 2: Variable/Type Definition "Type Identifier ..."
            # If the previous token was a Type (keyword or user-type),
            # this is likely a definition.
            # We must verify it's NOT a function declaration
            # (which ends in ; without body).
            if i > 0:
                # Find previous non-whitespace token
                prev_identifier = None
                for j in range(i - 1, -1, -1):
                    pm = tokens[j]
                    if pm.group(5) and not pm.group(5).strip():  # whitespace
                        continue
                    prev_identifier = pm.group(3)
                    break

                if prev_identifier:
                    # Determine if previous token acts as a Type
                    is_type_indicator = False

                    if prev_identifier in self.reserved_identifiers:
                        if prev_identifier in self.TYPE_KEYWORDS:
                            is_type_indicator = True
                    else:
                        # Assumed User-Defined Type (e.g. "bbox_t")
                        is_type_indicator = True

                    if is_type_indicator:
                        # Distinguish Variable Definition vs Function Decl
                        # Function Decl: Type Func(...);
                        # Variable Def: Type Var ...; or Type Var = ...

                        is_func_start = False
                        if i + 1 < n:
                            nxt = tokens[i + 1].group(5)
                            if nxt and nxt.strip() == "(":
                                is_func_start = True

                        if not is_func_start:
                            defined_symbols.add(identifier)

        # External Symbols = All Used - Locally Defined - Keywords
        all_identifiers -= self.reserved_identifiers
        external_candidates = all_identifiers - defined_symbols
        return external_candidates

    def _identify_external_symbols(self, source_code: str) -> Set[str]:
        """
        Identifies external symbols (functions/variables not defined in this file).
        Tries to use `gcc` and `nm` for precision; falls back to heuristic scanning.
        """
        # Method 1: Robust nm-based detection (requires gcc and nm)
        if shutil.which("gcc") and shutil.which("nm"):
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".c", mode="w", delete=False
                ) as tf:
                    tf.write(source_code)
                    temp_c = tf.name

                temp_o = temp_c + ".o"
                symbols = set()

                # Compile with -fno-builtin to expose intrinsics like fmax, printf
                subprocess.run(
                    ["gcc", "-c", temp_c, "-o", temp_o, "-fno-builtin"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                # Extract undefined symbols ("U")
                result = subprocess.run(
                    ["nm", "-u", temp_o], capture_output=True, text=True, check=True
                )

                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # nm output: "                 U _printf"
                    parts = line.split()
                    sym = parts[-1]
                    # Strip leading underscore (common in macOS/BSD)
                    if sym.startswith("_") and len(sym) > 1:
                        sym = sym[1:]
                    symbols.add(sym)

                # Cleanup
                if os.path.exists(temp_c):
                    os.unlink(temp_c)
                if os.path.exists(temp_o):
                    os.unlink(temp_o)

                return symbols

            except Exception:
                # Fallback to heuristic if compilation/nm fails
                pass
            finally:
                if "temp_c" in locals() and os.path.exists(temp_c):
                    try:
                        os.unlink(temp_c)
                    except Exception:
                        pass
                if "temp_o" in locals() and os.path.exists(temp_o):
                    try:
                        os.unlink(temp_o)
                    except Exception:
                        pass

        # Method 2: Heuristic Fallback
        return self._scan_for_external_symbols(source_code)

    def _inject_source_as_comments(self, source_code: str, obfuscated_code: str) -> str:
        """
        Compresses and encodes the original source code, then injects
        it as distributed comments into the obfuscated code. Identical to
        Python implementation but with C comments.
        """
        compressed = zlib.compress(source_code.encode("utf-8"))
        # Use ascii for safe embedding
        encoded = base64.b64encode(compressed).decode("ascii")

        lines = obfuscated_code.splitlines()
        if not lines:
            return obfuscated_code

        total_length = len(encoded)
        num_lines = len(lines)
        chunk_size = math.ceil(total_length / num_lines)

        new_lines = []
        for i, line in enumerate(lines):
            start = i * chunk_size
            end = min((i + 1) * chunk_size, total_length)

            if start >= total_length:
                new_lines.append(line)
                continue

            chunk = encoded[start:end]
            # Use // comments for chunks
            new_lines.append(f"// @mistode:chunk:{chunk}")
            new_lines.append(line)

        return "\n".join(new_lines)

    def _extract_source_from_comments(self, obfuscated_code: str) -> Optional[str]:
        """
        Extracts and decodes the original source code from distributed comments.
        """
        chunks = []
        lines = obfuscated_code.splitlines()
        found_any = False

        prefix = "// @mistode:chunk:"
        # Also support legacy /* */ if we ever used it, but for now // is standard
        # Regex might be safer

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(prefix):
                chunk = stripped[len(prefix) :].strip()
                chunks.append(chunk)
                found_any = True

        if not found_any:
            return None

        try:
            encoded = "".join(chunks)
            compressed = base64.b64decode(encoded)
            source_code = zlib.decompress(compressed).decode("utf-8")
            return source_code
        except Exception:
            return None

    def obfuscate(self, source_code: str) -> str:
        """
        Obfuscates C source code.

        - Discovery: Identifies external symbols to whitelist.
        - Tokenization: Splits code into tokens.
        - Replacement: Replaces internal identifiers with obfuscated names.
        - Metadata: Embeds mapping info for restoration (legacy/debug use).
        - Injection: Embeds original source for perfect restoration.
        """
        # Clear previous comments for this file if re-running
        if self.filename in self.mm.comments:
            self.mm.comments[self.filename] = []

        # 1. Identify External Symbols (Whitelist)
        external_symbols = self._identify_external_symbols(source_code)
        whitelisted_words = self.reserved_identifiers | external_symbols

        # 2. Tokenize and Process
        output = []
        for match in self._tokenize(source_code):
            string_lit = match.group(1)
            include_path = match.group(2)
            identifier = match.group(3)
            comment = match.group(4)
            other = match.group(5)

            if string_lit:
                output.append(string_lit)
            elif include_path:
                output.append(include_path)
            elif identifier:
                # Check if identifier should be obfuscated
                is_preprocessor_kw = identifier in self.PREPROCESSOR_DIRECTIVES

                should_keep = (
                    identifier in whitelisted_words
                    or identifier.startswith("__")
                    or is_preprocessor_kw
                )

                if not should_keep:
                    new_name = self.mm.get_obfuscated_name(identifier, self.gen)
                    output.append(new_name)
                else:
                    output.append(identifier)

            elif comment:
                # Save original comment, replace with scrambled placeholder
                self.mm.add_comment(self.filename, comment)
                if comment.startswith("//"):
                    content = comment[2:]
                    scrambled = "".join(["x" if c.isalnum() else c for c in content])
                    output.append(f"//{scrambled}")
                elif comment.startswith("/*"):
                    content = comment[2:-2]
                    scrambled = "".join(["x" if c.isalnum() else c for c in content])
                    output.append(f"/*{scrambled}*/")
            elif other:
                output.append(other)

        # 3. Embed Metadata (Keys) - Kept for legacy compatibility
        # or if lossless restoration fails
        mapping_info = {
            "identifier_mapping": self.mm.mapping,
            "comments": self.mm.comments,
            "files": self.mm.file_mapping,
            "encryption_key": self.mm.encryption_key,
            "string_quote_types": self.mm.string_quote_types,
        }
        json_bytes = json.dumps(mapping_info).encode("utf-8")
        encoded = base64.b64encode(json_bytes).decode("utf-8")

        # 4. Inject Original Source (Lossless restoration)
        obfuscated_text = "".join(output)

        # Append metadata comment first
        obfuscated_text += f"\n/* @mistode:metadata:{encoded} */\n"

        # Then inject source chunks
        final_output = self._inject_source_as_comments(source_code, obfuscated_text)

        return final_output

    def restore(self, source_code: str) -> str:
        """
        Restores C source code.

        Priority 1: Extract embedded original source (Lossless).
        Priority 2: Reconstruct using embedded metadata mappings (Token).
        """

        # 1. Attempt Lossless Restoration
        source_restored = self._extract_source_from_comments(source_code)
        if source_restored:
            return source_restored

        # 2. Fallback to Token-Level Restoration

        # Attempt to extract metadata
        metadata_match = re.search(
            r"/\* @mistode:metadata:(.*?) \*/", source_code, re.DOTALL
        )
        if metadata_match:
            try:
                encoded_metadata = metadata_match.group(1).strip()
                decoded = base64.b64decode(encoded_metadata).decode("utf-8")
                data = json.loads(decoded)

                # Load metadata if not already loaded (or merge)
                if not self.mm.mapping:
                    self.mm.mapping = data.get("identifier_mapping", {})
                    self.mm.reverse_mapping = {v: k for k, v in self.mm.mapping.items()}
                    self.mm.comments = data.get("comments", {})
                    self.mm.file_mapping = data.get("files", {})
                    self.mm.encryption_key = data.get("encryption_key", None)
                    self.mm.string_quote_types = data.get("string_quote_types", {})

                # Handle potential filename mismatch
                if self.filename not in self.mm.comments and len(self.mm.comments) == 1:
                    # Assume the single key in comments map corresponds to this file
                    self.filename = list(self.mm.comments.keys())[0]
            except Exception:
                pass

        available_comments = self.mm.get_comments(self.filename)
        comment_iter = iter(available_comments)

        output = []
        for match in self._tokenize(source_code):
            string_lit = match.group(1)
            include_path = match.group(2)
            identifier = match.group(3)
            comment = match.group(4)
            other = match.group(5)

            # Skip restoration artifacts (chunks)
            if comment and "@mistode:chunk:" in comment:
                continue

            if string_lit:
                output.append(string_lit)
            elif include_path:
                output.append(include_path)
            elif identifier:
                # Restore usage
                orig = self.mm.get_original_name(identifier)
                output.append(orig if orig else identifier)
            elif comment:
                # Restore original comment
                try:
                    original = next(comment_iter)
                    output.append(original)
                except StopIteration:
                    output.append(comment)
            elif other:
                output.append(other)

        # Clean up Metadata from Output
        restored_text = "".join(output)
        restored_text = re.sub(
            r"\n/\* @mistode:metadata:.*? \*/\n", "", restored_text, flags=re.DOTALL
        )
        # Clean up any lingering chunk comments if they weren't caught by tokenizer loop
        # (Though tokenizer should catch them as comments and we skip them above)

        return restored_text
