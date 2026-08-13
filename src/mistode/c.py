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
import os
import re
import shutil
import subprocess
import tempfile
import zlib
from collections.abc import Iterator

from .core import MappingManager, NameGenerator


class CObfuscator:
    """
    Obfuscator for C programming language code.

    Features:
    - Identifier renaming (variables, functions, structs).
    - String literal preservation.
    - Preprocessor directive preservation.
    - Comment preservation (in layout).
    - Layout-based lossless restoration (similar to Python implementation).
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
        "_Bool",
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
    # 2. Include Directives (to treat as single unit)
    # 3. Identifiers
    # 4. Numeric Literals (decimal, hex, octal, float, with optional suffixes)
    # 5. Comments
    # 6. Other (separators, operators, whitespace)
    # Note: Whitespace is explicitly captured in Group 6 so we can
    # distinguish it in the loop
    TOKEN_PATTERN = re.compile(
        r'("(?:\\.|[^"\\])*")|'
        r"(#\s*include\s*<[^>]+>)|"
        r"([a-zA-Z_]\w*)|"
        r"(0[xX][0-9a-fA-F]+[uUlLfF]*|"
        r"0[bB][01]+[uUlLfF]*|"
        r"[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?[uUlLfF]*)"
        r"|(/\*[^*]*\*+(?:[^/*][^*]*\*+)*/|//[^\n]*)"
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

    def _tokenize(self, text: str) -> Iterator[re.Match[str]]:
        """Yields regex matches for tokens in the C source code."""
        return self.TOKEN_PATTERN.finditer(text)

    def _scan_for_external_symbols(self, source_code: str) -> set[str]:
        """
        Heuristic scanner to identify external symbols (used but not defined
        in file). Acts as a fallback when compiler tools are unavailable.
        """
        return self._simple_scanner(source_code)

    def _simple_scanner(self, source_code: str) -> set[str]:  # noqa: C901
        """
        A minimalist external symbol scanner used as a fallback.

        It attempts to identify which identifiers are **defined** within this file.
        Any identifier used but not defined is assumed to be **external**.
        """
        defined = set()
        all_ids = set()

        # We process manually to skip whitespace
        matches = list(self._tokenize(source_code))

        # Filter only significant tokens (ignore comments/whitespace)
        # We need a clean stream of "Code Tokens" to analyze grammar patterns.
        sig_tokens = [m for m in matches if m.group(0).strip() and not m.group(5)]

        n = len(sig_tokens)

        # Collect user-defined type names so that declarations using them
        # (e.g. `Point q;` or `my_int count;`) count as definitions instead
        # of being mistaken for external symbols.
        user_types = self._collect_user_types(sig_tokens)

        for idx, m in enumerate(sig_tokens):
            name = m.group(3)
            if not name:
                continue

            all_ids.add(name)

            if name in self.reserved_identifiers:
                continue

            # --- Definition Detection Heuristic ---
            # We look for the pattern: `Type [*...] Name [ ( | = | ; | [ ]`
            # This indicates 'Name' is being declared or defined.

            # 1. Backwards Lookahead: Check for a Type
            is_type_def = False
            prev_idx = idx - 1

            # Skip pointer asterisks `*` backwards (e.g. `int * ptr`)
            while prev_idx >= 0 and sig_tokens[prev_idx].group(0) == "*":
                prev_idx -= 1

            if prev_idx >= 0:
                prev_token_match = sig_tokens[prev_idx]
                prev_ident = prev_token_match.group(3)

                # If the previous token is a known C type keyword or a
                # user-defined type (struct/union/enum/typedef alias), this
                # is likely a definition.
                if prev_ident in self.TYPE_KEYWORDS or prev_ident in user_types:
                    is_type_def = True

            if is_type_def:
                # 2. Forward Lookahead: Distinguish Function vs Variable
                # If followed by `(`, it's a function.
                if idx + 1 < n:
                    next_txt = sig_tokens[idx + 1].group(0)
                    if next_txt == "(":
                        # Function Definition Case: Must have a body `{ ... }`
                        # If it ends with `;` instead of `{`, it's just a
                        # declaration (not defined here).
                        if self._has_function_body(sig_tokens, idx + 1):
                            defined.add(name)
                    else:
                        # Variable / Parameter definition (e.g. `int a`, `char* b`)
                        defined.add(name)

        # External symbols = All Used - All Defined - Reserved
        return all_ids - defined - self.reserved_identifiers

    def _collect_user_types(self, sig_tokens: list[re.Match[str]]) -> set[str]:
        """
        Collect user-defined type names declared in this file:

        - `struct Foo`, `union Bar`, `enum Baz` -> Foo/Bar/Baz
        - `typedef ... Name;` -> Name (the last identifier before `;`)

        These are treated like type keywords so declarations such as
        `Foo x;` count as definitions during symbol discovery.
        """
        user_types = set()
        n = len(sig_tokens)

        for i, m in enumerate(sig_tokens):
            txt = m.group(0)

            if txt in ("struct", "union", "enum"):
                if i + 1 < n and sig_tokens[i + 1].group(3):
                    user_types.add(sig_tokens[i + 1].group(3))
            elif txt == "typedef":
                alias = None
                for k in range(i + 1, n):
                    t = sig_tokens[k].group(0)
                    if t == ";":
                        break
                    if sig_tokens[k].group(3):
                        alias = sig_tokens[k].group(3)
                if alias:
                    user_types.add(alias)

        return user_types

    def _has_function_body(self, tokens: list[re.Match[str]], start_idx: int) -> bool:
        """
        Scans ahead from an opening parenthesis `(` to check if the function
        has a body `{ ... }` or is just a declaration `;`.

        Handles nested parentheses (function arguments).
        """
        balance = 0
        n = len(tokens)

        for k in range(start_idx, n):
            tk = tokens[k].group(0)
            if tk == "(":
                balance += 1
            elif tk == ")":
                balance -= 1
                if balance == 0:
                    # Found closing parenthesis of argument list `)`
                    # Check next significant token:
                    # `)` -> `{`  == Definition
                    # `)` -> `;`  == Declaration
                    if k + 1 < n and tokens[k + 1].group(0) == "{":
                        return True
                    return False  # Likely a declaration
        return False

    def _identify_external_symbols(self, source_code: str) -> set[str]:  # noqa: C901
        """
        Identifies external symbols. Uses gcc/nm if available, else heuristic.
        (Retained logic from previous version)
        """
        if shutil.which("gcc") and shutil.which("nm"):
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".c", mode="w", delete=False
                ) as tf:
                    tf.write(source_code)
                    temp_c = tf.name

                temp_o = temp_c + ".o"
                symbols = set()

                subprocess.run(
                    ["gcc", "-c", temp_c, "-o", temp_o, "-fno-builtin"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                result = subprocess.run(
                    ["nm", "-u", temp_o], capture_output=True, text=True, check=True
                )

                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    sym = parts[-1]
                    if sym.startswith("_") and len(sym) > 1:
                        sym = sym[1:]
                    symbols.add(sym)

                if os.path.exists(temp_c):
                    os.unlink(temp_c)
                if os.path.exists(temp_o):
                    os.unlink(temp_o)
                return symbols
            except Exception:
                pass
            finally:
                if "temp_c" in locals() and os.path.exists(temp_c):
                    try:
                        os.unlink(temp_c)
                    except OSError:
                        pass
                if "temp_o" in locals() and os.path.exists(temp_o):
                    try:
                        os.unlink(temp_o)
                    except OSError:
                        pass

        return self._simple_scanner(source_code)

    def _needs_space(self, prev: str, curr: str) -> bool:
        """Determines if space is needed between two C tokens."""
        if not prev or not curr:
            return False

        # Alphanumeric + Alphanumeric (including _) -> Space
        # e.g. "int" + "main", "return" + "0"
        if (prev[-1].isalnum() or prev[-1] == "_") and (
            curr[0].isalnum() or curr[0] == "_"
        ):
            return True

        return False

    def _generate_metadata(self) -> str:
        """
        Generate the embedded metadata comment containing the identifier
        mapping, so restoration works without a key file.
        """
        mapping_info = {
            "identifier_mapping": self.mm.mapping,
            "source_encoding": self.mm.source_encoding,
        }
        json_bytes = json.dumps(mapping_info).encode("utf-8")
        compressed = zlib.compress(json_bytes)
        encoded = base64.b64encode(compressed).decode("ascii")
        return f"/* @mistode:metadata:{encoded} */"

    def obfuscate(  # noqa: C901
        self,
        source_code: str,
        embed_metadata: bool = True,
        source_encoding: str | None = None,
    ) -> str:
        """
        Obfuscates C source code using layout engine approach.

        Args:
            source_code: Original C source code.
            embed_metadata: Whether to append the identifier mapping as an
                embedded comment (enables key-file-free restoration).
            source_encoding: Encoding of the original source file, stored
                in the metadata so restoration is byte-identical.
        """
        self.mm.source_encoding = source_encoding
        # Clear previous comments
        if self.filename in self.mm.comments:
            self.mm.comments[self.filename] = []

        external_symbols = self._identify_external_symbols(source_code)
        whitelisted = self.reserved_identifiers | external_symbols

        # Preserve macro names (the identifier following `#define`).
        # Macro bodies keep normal obfuscation, which is safe because both
        # the definition and all use sites go through the same mapping.
        for define_match in re.finditer(
            r"^[ \t]*#[ \t]*define[ \t]+([a-zA-Z_]\w*)",
            source_code,
            re.MULTILINE,
        ):
            whitelisted.add(define_match.group(1))

        # Stream Processing
        # We collect "Logical Lines"
        # A logical line ends when the 'layout' contains a newline.

        output_lines = []

        current_line_tokens = []  # (token_str)
        current_line_layouts = []  # (layout_dict)

        pending_layout = ""

        matches = list(self._tokenize(source_code))

        for match in matches:
            txt = match.group(0)

            # Identify if it is purely layout (comment or whitespace)
            is_layout = False
            if match.group(5):  # Comment
                # We store comments in layout to preserve them
                is_layout = True
            elif match.group(6):  # Whitespace or Other
                if not match.group(6).strip():  # Pure whitespace
                    is_layout = True
                else:
                    # "Other" non-whitespace (operators like +, -, ;)
                    is_layout = False
            else:
                is_layout = False

            if is_layout:
                pending_layout += txt
                # Check for newlines to flush lines?
                # To maintain roughly the same line count/structure,
                # we can flush when we trace newlines in layout.
                # However, complex comments might have internal newlines.
                # Simplified approach: We treat the file as a stream.
                # We only flush when we are about to emit a token AND
                # the pending layout implies we moved to a new line.
                continue

            # It is a code token
            token_str = txt

            # Handle Obfuscation
            if match.group(3):  # Identifier
                ident = match.group(3)
                should_keep = (
                    ident in whitelisted
                    or ident.startswith("__")
                    or ident in self.PREPROCESSOR_DIRECTIVES
                )
                if not should_keep:
                    token_str = self.mm.get_obfuscated_name(ident, self.gen)

            # Check if pending layout has newlines
            # If so, we flush the PREVIOUS accumulated tokens as a line
            if "\n" in pending_layout:
                # Flush previous
                if current_line_tokens or current_line_layouts:
                    self._flush_line(
                        output_lines, current_line_tokens, current_line_layouts
                    )
                    current_line_tokens = []
                    current_line_layouts = []

            # Add current token
            current_line_layouts.append({"p": pending_layout})
            pending_layout = ""

            # minimal formatting for current line append
            prefix = ""
            if current_line_tokens:
                if self._needs_space(current_line_tokens[-1], token_str):
                    prefix = " "

            current_line_tokens.append(prefix + token_str)

        # Handle remaining
        if current_line_tokens or current_line_layouts:
            self._flush_line(output_lines, current_line_tokens, current_line_layouts)

        # Handle trailing layout
        if pending_layout:
            # Just append a chunk for trailing layout
            self._flush_line(output_lines, [], [{"p": pending_layout}])

        result = "\n".join(output_lines)

        if embed_metadata:
            result += "\n" + self._generate_metadata()

        return result

    def _flush_line(self, output: list[str], tokens: list[str], layouts: list[dict]):
        # Encode layout
        json_bytes = json.dumps(layouts).encode("utf-8")
        compressed = zlib.compress(json_bytes)
        encoded = base64.b64encode(compressed).decode("ascii")

        output.append(f"// @mistode:chunk:{encoded}")
        if tokens:
            output.append("".join(tokens))
        # We don't append \n to output list items, join will do it

    def restore(self, source_code: str) -> str:  # noqa: C901
        """
        Restores C source code using layout chunks.
        """
        # Extract external metadata for mapping if present
        metadata_found = False
        metadata_match = re.search(
            r"/\* @mistode:metadata:(.*?) \*/", source_code, re.DOTALL
        )
        if metadata_match:
            try:
                encoded_metadata = metadata_match.group(1).strip()
                decoded = base64.b64decode(encoded_metadata)
                decompressed = zlib.decompress(decoded)
                data = json.loads(decompressed.decode("utf-8"))
                if not self.mm.mapping:
                    self.mm.mapping = data.get("identifier_mapping", {})
                    self.mm.reverse_mapping = {v: k for k, v in self.mm.mapping.items()}
                if data.get("source_encoding"):
                    self.mm.source_encoding = data["source_encoding"]
                metadata_found = True
            except Exception:
                pass

        lines = source_code.splitlines()

        # 1. Parse Layouts
        # Map: line_index -> [layouts]
        # Since we have interleaved comments, we process sequentially.

        # We will iterate lines, consume chunks into a queue, and consume
        # code lines to match the queue.

        restored_parts = []

        pending_layouts = []

        # Fail loudly only when there is genuinely no mapping source:
        # a valid (possibly empty) mapping from embedded metadata is fine,
        # since a file with no obfuscatable identifiers has nothing to map.
        if not metadata_found and not self.mm.mapping and not self.mm.reverse_mapping:
            raise ValueError(
                "No identifier mapping available for restoration. "
                "The obfuscated file has no embedded metadata and no key file "
                "was provided."
            )

        # We need to tokenize the code lines to match with layouts
        # Tokenizing line-by-line is safe because our obfuscator respects
        # line boundaries relative to tokens.

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("// @mistode:chunk:"):
                # Decode chunk
                payload = stripped.split(":", 2)[2]
                try:
                    decoded = base64.b64decode(payload)
                    decompressed = zlib.decompress(decoded)
                    chunk_layouts = json.loads(decompressed.decode("utf-8"))
                    pending_layouts.extend(chunk_layouts)
                except Exception:
                    pass
                continue

            # It's a code line (or empty)
            # Remove the @mistode:metadata block if it exists on this line
            # (unlikely given format)
            if "/* @mistode:metadata:" in line:
                continue  # Skip legacy/metadata line entirely?
                # Ideally we strip it. If it was distinct line, continue.
                # If embedded? The regex at top handled loading.
                # We should just ignore it in output.

            if not line and not pending_layouts:
                # Just an empty line in obfuscated file that has no layout?
                continue

            # Layout-only chunk (trailing)
            if not line and pending_layouts:
                # Flush layouts that have no tokens? e.g. trailing comments
                # Iterate remaining layouts
                while pending_layouts:
                    layout = pending_layouts.pop(0)
                    restored_parts.append(layout.get("p", ""))
                continue

            # Tokenize this line to match code tokens
            # We must be careful: the obfuscated line has formatting (added spaces).
            # We want to ignore that formatting and use 'p' from layout.

            line_matches = list(self._tokenize(line))

            # Filter for meaningful tokens
            code_tokens = []
            for m in line_matches:
                txt = m.group(0)
                # Ignore whitespace/comments in the OBFUSCATED file
                # because they are artifacts of obfuscation or user mod.
                # We heavily rely on layout 'p' for restoration.
                if not txt.strip():
                    continue
                if m.group(5):
                    continue  # comments in obfuscated file?
                # Only chunk comments exist, handled above.
                code_tokens.append(txt)

            # Restore
            for token in code_tokens:
                if not pending_layouts:
                    # Ran out of layout? Just append token
                    restored_parts.append(token)
                    continue

                layout = pending_layouts.pop(0)
                prefix = layout.get("p", "")

                restored_parts.append(prefix)

                # Restore Identifier Name
                orig = self.mm.get_original_name(token)
                restored_parts.append(orig if orig else token)

        # Flush any remaining layouts (trailing)
        for layout in pending_layouts:
            restored_parts.append(layout.get("p", ""))

        return "".join(restored_parts)
