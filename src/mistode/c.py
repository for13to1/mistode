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
from typing import Any, Dict, Iterator, List, Match, Optional, Set, Tuple

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
    # 4. Comments
    # 5. Other (separators, operators, whitespace)
    # Note: Whitespace is explicitly captured in Group 5 so we can distinguish it in the loop
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
        Acts as a fallback when compiler tools are unavailable.
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

            # Check for Definition Patterns (Simplified)

            # Pattern 1: Function Definition "Identifier (...) {"
            if i + 1 < n:
                next_match = tokens[i + 1]
                # Skip whitespace in lookahead if current logic allows (simplified here)
                # But tokenize regex yields whitespace. We need to skip it.

                # Manual lookahead skipping whitespace
                next_relevant = None
                pck_idx = i + 1
                while pck_idx < n:
                    m = tokens[pck_idx]
                    s = m.group(0)  # Full match
                    if not s.strip():  # is whitespace
                        pck_idx += 1
                        continue
                    next_relevant = m
                    break

                if next_relevant and "(" in next_relevant.group(0):
                    # Found '(', verify closing ')' and '{'
                    # Simplified balance check would go here (omitted for brevity as per existing logic,
                    # assuming heuristic is acceptable as per previous design)
                    is_func_def = False

                    # Basic check for { after )
                    # ... (Logic from previous verify is complex to reimplement compact,
                    # reusing the idea: if we see () {, it's a def)

                    # We will trust the previous implementation's heuristic 'idea'
                    # but implementing robustly requires scanning.
                    # Since this is a refactor of the *obfuscation mechanism*,
                    # we keep the symbol discovery lightweight.
                    pass

        # For this refactor, we retain the robust external symbol logic if available,
        # but the main focus is Layout Engine.
        # Re-implementing the exact previous scanner to ensure no regression.

        # Resetting to simple implementation for this function to ensure reliability
        # based on regex scan.
        return self._simple_scanner(source_code)

    def _simple_scanner(self, source_code: str) -> Set[str]:
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
        sig_tokens = [m for m in matches if m.group(0).strip() and not m.group(4)]

        n = len(sig_tokens)

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

                # If the previous token is a known C type keyword, this is likely a definition.
                # Note: This misses user-defined types (structs aliases),
                # but is safe enough for a heuristic (false negatives just mean less obfuscation).
                if prev_ident in self.TYPE_KEYWORDS:
                    is_type_def = True

            if is_type_def:
                # 2. Forward Lookahead: Distinguish Function vs Variable
                # If followed by `(`, it's a function.
                if idx + 1 < n:
                    next_txt = sig_tokens[idx + 1].group(0)
                    if next_txt == "(":
                        # Function Definition Case: Must have a body `{ ... }`
                        # If it ends with `;` instead of `{`, it's just a declaration (not defined here).
                        if self._has_function_body(sig_tokens, idx + 1):
                            defined.add(name)
                    else:
                        # Variable / Parameter definition (e.g. `int a`, `char* b`)
                        defined.add(name)

        # External symbols = All Used - All Defined - Reserved
        return all_ids - defined - self.reserved_identifiers

    def _has_function_body(self, tokens: List[Match[str]], start_idx: int) -> bool:
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

    def _identify_external_symbols(self, source_code: str) -> Set[str]:
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
                    except:
                        pass
                if "temp_o" in locals() and os.path.exists(temp_o):
                    try:
                        os.unlink(temp_o)
                    except:
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

    def obfuscate(self, source_code: str) -> str:
        """
        Obfuscates C source code using layout engine approach.
        """
        # Clear previous comments
        if self.filename in self.mm.comments:
            self.mm.comments[self.filename] = []

        external_symbols = self._identify_external_symbols(source_code)
        whitelisted = self.reserved_identifiers | external_symbols

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
            if match.group(4):  # Comment
                # We store comments in layout to preserve them
                is_layout = True
            elif match.group(5):  # Whitespace or Other
                if not match.group(5).strip():  # Pure whitespace
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

        return "\n".join(output_lines)

    def _flush_line(self, output: List[str], tokens: List[str], layouts: List[Dict]):
        # Encode layout
        json_bytes = json.dumps(layouts).encode("utf-8")
        compressed = zlib.compress(json_bytes)
        encoded = base64.b64encode(compressed).decode("ascii")

        output.append(f"// @mistode:chunk:{encoded}")
        if tokens:
            output.append("".join(tokens))
        # We don't append \n to output list items, join will do it

    def restore(self, source_code: str) -> str:
        """
        Restores C source code using layout chunks.
        """
        # Extract external metadata for mapping if present
        metadata_match = re.search(
            r"/\* @mistode:metadata:(.*?) \*/", source_code, re.DOTALL
        )
        if metadata_match:
            try:
                encoded_metadata = metadata_match.group(1).strip()
                decoded = base64.b64decode(encoded_metadata).decode("utf-8")
                data = json.loads(decoded)
                if not self.mm.mapping:
                    self.mm.mapping = data.get("identifier_mapping", {})
                    self.mm.reverse_mapping = {v: k for k, v in self.mm.mapping.items()}
            except Exception:
                pass

        lines = source_code.splitlines()

        # 1. Parse Layouts
        # Map: line_index -> [layouts]
        # Since we have interleaved comments, we process sequentially.

        # We will iterate lines, consume chunks into a queue, and consume code lines to match the queue.

        restored_parts = []

        pending_layouts = []

        # We need to tokenize the code lines to match with layouts
        # Tokenizing line-by-line is safe because our obfuscator respects line boundaries relative to tokens.

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
                except:
                    pass
                continue

            # It's a code line (or empty)
            # Remove the @mistode:metadata block if it exists on this line (unlikely given format)
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
                    l = pending_layouts.pop(0)
                    restored_parts.append(l.get("p", ""))
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
                if m.group(4):
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
        for l in pending_layouts:
            restored_parts.append(l.get("p", ""))

        return "".join(restored_parts)
