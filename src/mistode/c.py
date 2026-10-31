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
import bisect
import json
import os
import re
import shutil
import subprocess
import tempfile
import zlib
from collections.abc import Iterator
from pathlib import Path

from .core import MappingManager, NameGenerator
from .encrypt import make_cipher
from .payload import (
    build_marker,
    classify_marker,
    decode_layouts,
    decode_metadata,
    inconsistent,
)


class CObfuscator:
    """Renames C identifiers while keeping the file compilable.

    Layout (whitespace, comments) is stored in interleaved chunk comments so
    restoration is byte-identical. External symbols are discovered with
    `gcc`/`nm` when available, otherwise with a conservative heuristic.
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

    # Named groups, so adding an alternative cannot shift the indices the
    # rest of the class reads. Whitespace stays in `other` so layout can be
    # captured verbatim.
    TOKEN_PATTERN = re.compile(
        # Raw string literals (C++11 `R"(...)"`, `R"delim(...)delim"`) come
        # first so their contents are never scanned as code.
        r'(?P<raw>(?:u8|[LuU])?R"(?P<delim>[^()\\ ]{0,16})\(.*?\)(?P=delim)")|'
        # String literals and character constants share one group: `'a'`
        # must never be split into quote + identifier, or the inner name
        # would be renamed and the constant corrupted.
        r'(?P<literal>(?:u8|[LuU])?(?:"(?:\\.|[^"\\\\])*"|\'(?:\\.|[^\'\\\\])*\'))|'
        r'(?P<directive>#\s*include\s*(?:<[^>]+>|"[^"]+"))|'
        r"(?P<ident>[a-zA-Z_]\w*)|"
        # Hex floats need the `.`/`p` exponent parts; without them `p3` in
        # `0x1.8p3` would be read as an identifier and renamed.
        r"(?P<number>0[xX](?:[0-9a-fA-F]+(?:\.[0-9a-fA-F]*)?|\.[0-9a-fA-F]+)"
        r"(?:[pP][+-]?[0-9]+)?[uUlLfF]*|"
        r"0[bB][01]+[uUlLfF]*|"
        r"[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?[uUlLfF]*)"
        r"|(?P<comment>/\*[^*]*\*+(?:[^/*][^*]*\*+)*/|//[^\n]*)"
        # Multi-character operators must be matched as one token; splitting
        # `a++` into `a` `+` `+` and re-emitting them with a separating
        # space produces invalid C.
        r"|(?P<op>\+\+|--|->|<<=|>>=|<<|>>|<=|>=|==|!=|&&|\|\||\+=|-=|\*=|/=|%=|"
        r"&=|\|=|\^=|::|\.\.\.)"
        r"|(?P<other>\s+|.)",
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

        # Payload cipher; set per call by obfuscate()/restore().
        self._cipher = None

        # Layout records emitted by obfuscate(); embedded in the metadata so
        # restoration can detect inserted or removed chunk markers.
        self._layout_count = 0

    def _tokenize(self, text: str) -> Iterator[re.Match[str]]:
        """Yields regex matches for tokens in the C source code."""
        return self.TOKEN_PATTERN.finditer(text)

    def _simple_scanner(self, source_code: str) -> set[str]:  # noqa: C901
        """Return names used but not defined here, using grammar heuristics."""
        defined = set()
        all_ids = set()

        matches = list(self._tokenize(source_code))
        # Comments and whitespace carry no grammar information.
        sig_tokens = [
            m for m in matches if m.group(0).strip() and not m.group("comment")
        ]

        n = len(sig_tokens)

        # Collect user-defined type names so that declarations using them
        # (e.g. `Point q;` or `my_int count;`) count as definitions instead
        # of being mistaken for external symbols.
        user_types = self._collect_user_types(sig_tokens)
        # A typedef alias is a definition in this translation unit; struct
        # tags are not, because a bare `struct Foo *p;` is a forward use.
        for i, m in enumerate(sig_tokens):
            if m.group(0) == "typedef":
                alias = self._typedef_alias(sig_tokens, i)
                if alias:
                    defined.add(alias)

        for idx, m in enumerate(sig_tokens):
            name = m.group("ident")
            if not name:
                continue

            all_ids.add(name)

            if name in self.reserved_identifiers:
                continue

            # Definition shape: `Type [*...] Name [ ( | = | ; | [ ]`.

            # 1. Backwards Lookahead: Check for a Type
            is_type_def = False
            prev_idx = idx - 1

            # Skip pointer asterisks `*` backwards (e.g. `int * ptr`)
            while prev_idx >= 0 and sig_tokens[prev_idx].group(0) == "*":
                prev_idx -= 1

            if prev_idx >= 0:
                prev_token_match = sig_tokens[prev_idx]
                prev_ident = prev_token_match.group("ident")

                # A known type keyword or typedef alias marks a definition.
                if prev_ident in self.TYPE_KEYWORDS or prev_ident in user_types:
                    is_type_def = True

            if is_type_def:
                # Function if followed by `(`, else a variable.
                if idx + 1 < n:
                    next_txt = sig_tokens[idx + 1].group(0)
                    if next_txt == "(":
                        # A body (`{`) means defined here; `;` is only a
                        # declaration.
                        if self._has_function_body(sig_tokens, idx + 1):
                            defined.add(name)
                    else:
                        # Variable / Parameter definition (e.g. `int a`, `char* b`)
                        defined.add(name)

        # External symbols = All Used - All Defined - Reserved
        return all_ids - defined - self.reserved_identifiers

    def _scan_defined_symbols(self, source_code: str) -> set[str]:
        """
        Return identifiers *defined* in this file (functions, variables,
        parameters). Used by directory mode to preserve symbols that are
        shared across files.
        """
        external = self._simple_scanner(source_code)
        all_ids = {
            m.group("ident") for m in self._tokenize(source_code) if m.group("ident")
        }
        return all_ids - external - self.reserved_identifiers

    def _collect_user_types(self, sig_tokens: list[re.Match[str]]) -> set[str]:
        """Type names declared here (`struct Foo`, `typedef ... Name`),
        so `Foo x;` counts as a definition during symbol discovery."""
        user_types = set()
        n = len(sig_tokens)

        for i, m in enumerate(sig_tokens):
            txt = m.group(0)

            if txt in ("struct", "union", "enum"):
                if i + 1 < n and sig_tokens[i + 1].group("ident"):
                    user_types.add(sig_tokens[i + 1].group("ident"))
            elif txt == "typedef":
                alias = self._typedef_alias(sig_tokens, i)
                if alias:
                    user_types.add(alias)

        return user_types

    @staticmethod
    def _typedef_alias(sig_tokens: list[re.Match[str]], start: int) -> str | None:
        """Last identifier at depth 0 before `;`, so `typedef struct {...} P;`
        yields `P` instead of stopping at a member declaration."""
        alias = None
        depth = 0
        for k in range(start + 1, len(sig_tokens)):
            txt = sig_tokens[k].group(0)
            if txt in ("{", "("):
                depth += 1
            elif txt in ("}", ")"):
                depth = max(depth - 1, 0)
            elif txt == ";" and depth == 0:
                break
            elif depth == 0 and sig_tokens[k].group("ident"):
                alias = sig_tokens[k].group("ident")
        return alias

    def _has_function_body(self, tokens: list[re.Match[str]], start_idx: int) -> bool:
        """True if the `(` at `start_idx` opens a definition, not a declaration.

        Nested parentheses (arguments) are balanced.
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
                    # `)` followed by `{` is a definition; by `;` is not.
                    if k + 1 < n and tokens[k + 1].group(0) == "{":
                        return True
                    return False  # Declaration
        return False

    def _identify_external_symbols(  # noqa: C901
        self, source_code: str, source_dir: Path | None = None
    ) -> set[str]:
        """Names used but defined elsewhere: compiler probe, else heuristic."""
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
                    [
                        "gcc",
                        "-c",
                        temp_c,
                        *(["-I", str(source_dir)] if source_dir else []),
                        "-o",
                        temp_o,
                        "-fno-builtin",
                    ],
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
                # `nm -u` sees only link-time symbols: typedefs and macros
                # are resolved by the preprocessor, so union the heuristic scan.
                return symbols | self._simple_scanner(source_code)
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
        """Whether a space must separate two adjacent output tokens."""
        if not prev or not curr:
            return False

        prev_last = prev[-1]
        curr_first = curr[0]

        # Word-like adjacency: "int" + "main", "return" + "0".
        if (prev_last.isalnum() or prev_last == "_") and (
            curr_first.isalnum() or curr_first == "_"
        ):
            return True

        # A string or character literal must not fuse with a preceding
        # word: `#define MSG"hello"` is not valid C.
        if curr_first in "\"'" and (prev_last.isalnum() or prev_last == "_"):
            return True

        # ... nor with a following word (`"%" PRIu64`).
        if prev_last in "\"'" and (curr_first.isalnum() or curr_first == "_"):
            return True

        # `/` followed by `*` would open a block comment (`a / *b`).
        if prev_last == "/" and curr_first == "*":
            return True

        # A lone `+` before `+`/`++` (or `-` before `-`/`--`) would be
        # re-lexed as `++`/`--`, changing the expression.
        if prev == "+" and curr in ("+", "++"):
            return True
        if prev == "-" and curr in ("-", "--"):
            return True

        return False

    def _generate_metadata(self) -> str:
        """Embed the identifier mapping so restoration needs no key file."""
        mapping_info = {
            "identifier_mapping": self.mm.mapping,
            "source_encoding": self.mm.source_encoding,
            # See _verify_layout_balance for what this protects against.
            "layout_count": self._layout_count,
        }
        json_bytes = json.dumps(mapping_info).encode("utf-8")
        compressed = zlib.compress(json_bytes)
        if self._cipher:
            encoded = self._cipher.encrypt(compressed)
            return build_marker("metadata", "c", encoded, secure=True)
        encoded = base64.b64encode(compressed).decode("ascii")
        return build_marker("metadata", "c", encoded, secure=False)

    def obfuscate(  # noqa: C901
        self,
        source_code: str,
        embed_metadata: bool = True,
        source_encoding: str | None = None,
        extra_whitelisted: set[str] | None = None,
        source_dir: Path | None = None,
        encryption_key: str | None = None,
        cipher: str | None = None,
    ) -> str:
        """Obfuscate C source and return the artifact.

        source_dir is passed to the compiler as `-I` while probing external
        symbols; extra_whitelisted protects names shared with other files.
        """
        self.mm.source_encoding = source_encoding
        # `a##b` can synthesise any identifier, so such a file is left
        # unrenamed. Comments and literals are excluded so `"##"` does not
        # disable obfuscation.
        code_tokens = [
            m.group(0)
            for m in self._tokenize(source_code)
            if not (m.group("comment") or m.group("literal") or m.group("raw"))
        ]
        self._has_token_pasting = "##" in "".join(code_tokens)
        if cipher is None:
            cipher = "stream" if encryption_key is not None else "none"
        self._cipher = make_cipher(cipher, encryption_key) if cipher != "none" else None

        external_symbols = self._identify_external_symbols(
            source_code, source_dir=source_dir
        )
        whitelisted = self.reserved_identifiers | external_symbols
        if extra_whitelisted:
            whitelisted |= extra_whitelisted

        # Preserve macro names (the identifier following `#define`).
        # Macro bodies keep normal obfuscation, which is safe because both
        # the definition and all use sites go through the same mapping.
        for define_match in re.finditer(
            r"^[ \t]*#[ \t]*define[ \t]+([a-zA-Z_]\w*)",
            source_code,
            re.MULTILINE,
        ):
            whitelisted.add(define_match.group(1))

        # Output is assembled one logical line at a time; a newline in the
        # pending layout ends the current line.

        self._layout_count = 0
        output_lines = []

        current_line_tokens = []  # (token_str)
        current_line_layouts = []  # (layout_dict)

        pending_layout = ""
        # True while the current logical line is a preprocessor directive;
        # its identifiers are resolved before compilation.
        in_directive = False

        matches = list(self._tokenize(source_code))

        for match in matches:
            txt = match.group(0)

            # Comments and whitespace are layout; everything else is code.
            if match.group("comment") or (
                match.group("other") and not match.group("other").strip()
            ):
                # Layout is buffered and flushed with the next code token,
                # so comments are preserved without splitting output lines.
                pending_layout += txt
                continue

            # A newline in the pending layout closes the previous line.
            if "\n" in pending_layout:
                if current_line_tokens or current_line_layouts:
                    self._flush_line(
                        output_lines, current_line_tokens, current_line_layouts
                    )
                    continued = bool(
                        current_line_tokens and current_line_tokens[-1].endswith("\\")
                    )
                    if not continued:
                        in_directive = False
                    current_line_tokens = []
                    current_line_layouts = []

            token_str = txt

            if not current_line_tokens:
                # At the start of a logical line, a leading `#` marks a
                # preprocessor directive.
                if token_str == "#" or match.group("directive"):
                    in_directive = True

            if match.group("ident"):  # identifier
                ident = match.group("ident")
                # Preprocessor identifiers are contracts: renaming them
                # silently changes which branches compile.
                should_keep = (
                    ident in whitelisted
                    or ident.startswith("__")
                    or ident in self.PREPROCESSOR_DIRECTIVES
                    or in_directive
                    or self._has_token_pasting
                )
                if not should_keep:
                    token_str = self.mm.get_obfuscated_name(ident, self.gen)

            current_line_layouts.append({"p": pending_layout})
            pending_layout = ""

            # Separate tokens only where C would otherwise re-lex them.
            prefix = ""
            if current_line_tokens:
                if self._needs_space(current_line_tokens[-1], token_str):
                    prefix = " "

            current_line_tokens.append(prefix + token_str)

        if current_line_tokens or current_line_layouts:
            self._flush_line(output_lines, current_line_tokens, current_line_layouts)

        if pending_layout:
            self._flush_line(output_lines, [], [{"p": pending_layout}])

        result = "\n".join(output_lines)
        self._verify_token_stream(source_code, result)

        if embed_metadata:
            result += "\n" + self._generate_metadata()

        return result

    # Groups that carry meaning and must survive obfuscation unchanged,
    # apart from identifiers (which are renamed).
    _SIGNIFICANT_GROUPS = ("ident", "literal", "raw", "directive", "number", "op")

    def _significant_tokens(self, text: str) -> list[tuple[str, str]]:
        tokens: list[tuple[str, str]] = []
        for match in self._tokenize(text):
            if match.group("comment"):
                continue
            token = match.group(0)
            if not token.strip() or token == "\\":
                continue
            kind = next(
                (g for g in self._SIGNIFICANT_GROUPS if match.group(g)), "other"
            )
            tokens.append((kind, token))
        return tokens

    def _verify_token_stream(self, source: str, output: str) -> None:
        """Ensure the emitted code tokenises to the same stream as the input.

        Spacing is emitted heuristically; a missing space can merge or split
        tokens (`a + ++b` -> `a+++b`), changing the program. Comparing token
        sequences turns that class of bug into an explicit error.
        """
        expected = self._significant_tokens(source)
        actual = self._significant_tokens(output)
        if len(expected) != len(actual):
            raise ValueError(
                "Refusing to emit C output: token stream changed "
                f"({len(expected)} -> {len(actual)} tokens). "
                "This is a Mistode bug; please report the input."
            )
        for (kind, token), (out_kind, out_token) in zip(expected, actual, strict=True):
            if kind == "ident":
                if out_kind != "ident":
                    raise ValueError(
                        "Refusing to emit C output: identifier became "
                        f"{out_kind} ({token!r} -> {out_token!r})."
                    )
            elif token != out_token:
                raise ValueError(
                    "Refusing to emit C output: token changed "
                    f"({kind} {token!r} -> {out_kind} {out_token!r})."
                )

    def _flush_line(self, output: list[str], tokens: list[str], layouts: list[dict]):
        # Encode layout
        json_bytes = json.dumps(layouts).encode("utf-8")
        compressed = zlib.compress(json_bytes)
        self._layout_count += len(layouts)
        secure = self._cipher is not None
        if secure:
            encoded = self._cipher.encrypt(compressed)
        else:
            encoded = base64.b64encode(compressed).decode("ascii")

        # After a continuation backslash the next line joins the same logical
        # line, so `//` would swallow the macro body. Block comments are safe,
        # but the comment line must re-emit the backslash.
        continued = bool(output and output[-1].rstrip().endswith("\\"))
        suffix = " \\" if continued else ""
        output.append(build_marker("chunk", "c", encoded, secure) + suffix)
        if tokens:
            output.append("".join(tokens))

    def _locate_markers(
        self, source_code: str, lines: list[str]
    ) -> tuple[dict[int, str], list[str], set[int]]:
        """Find the comments that are chunk and metadata markers.

        A marker is layout data only when the lexer reports it as a comment:
        the same text inside a string literal is program data. Chunks are
        returned keyed by line so the caller can drop those lines, and the
        comment text is kept so a marker sharing a line with code is parsed
        without re-finding it in the line.
        """
        chunks: dict[int, str] = {}
        metadata_comments: list[str] = []
        metadata_lines: set[int] = set()

        line_starts: list[int] = []
        offset = 0
        for line in lines:
            line_starts.append(offset)
            offset += len(line) + 1

        for match in self._tokenize(source_code):
            if not match.group("comment"):
                continue
            marker = classify_marker(match.group(0), "c")
            if marker is None:
                continue
            kind, _, _ = marker
            lineno = bisect.bisect_right(line_starts, match.start())
            if kind == "chunk":
                chunks[lineno] = match.group(0)
            else:
                metadata_comments.append(match.group(0))
                metadata_lines.add(lineno)
        return chunks, metadata_comments, metadata_lines

    def _read_metadata(self, metadata_comments: list[str]) -> int | None:
        """Load the identifier mapping from the footer, if there is one.

        Returns the layout count the artifact declares. A footer written before
        that field existed yields None, which is also what "no footer" returns;
        callers that need to tell the two apart must look at
        `metadata_comments`.
        """
        if not metadata_comments:
            return None
        # Emitted last, so the final metadata comment is the footer.
        _, encoded, secure = classify_marker(metadata_comments[-1], "c")
        data = decode_metadata(encoded, secure=secure, cipher=self._cipher)
        if not self.mm.mapping:
            self.mm.mapping = data.get("identifier_mapping", {})
            self.mm.reverse_mapping = {v: k for k, v in self.mm.mapping.items()}
        if data.get("source_encoding"):
            self.mm.source_encoding = data["source_encoding"]
        return data.get("layout_count")

    def _split_lines_and_layouts(
        self,
        lines: list[str],
        chunks: dict[int, str],
        metadata_lines: set[int],
    ) -> tuple[str, list[dict]]:
        """Split the artifact into clean code and its flattened layouts.

        Chunk lines are dropped; the layouts they carry are decoded and
        associated with the code line that follows them, then flattened in
        emission order.
        """
        chunk_payloads: dict[int, tuple[str, bool]] = {}
        for lineno, comment in chunks.items():
            _, payload, secure = classify_marker(comment, "c")
            chunk_payloads[lineno] = (payload, secure)

        clean_lines: list[str] = []
        pending: list[dict] = []
        all_layouts: list[dict] = []

        for lineno, line in enumerate(lines, start=1):
            if lineno in chunk_payloads:
                payload, secure = chunk_payloads[lineno]
                pending.extend(
                    decode_layouts(payload, secure=secure, cipher=self._cipher)
                )
                continue
            if lineno in metadata_lines:
                continue
            clean_lines.append(line)
            if pending:
                all_layouts.extend(pending)
                pending = []
        all_layouts.extend(pending)

        return "\n".join(clean_lines), all_layouts

    def _replay_token_stream(
        self, clean_code: str, all_layouts: list[dict]
    ) -> tuple[str, int, int]:
        """Rebuild the original text by replaying layouts onto each token.

        Returns the restored text, the number of layouts consumed, and the
        number of tokens left without one. Records after the last token are
        appended; the caller derives how many are left over.
        """
        restored_parts: list[str] = []
        unpaired_tokens = 0
        next_layout = 0

        for match in self._tokenize(clean_code):
            token = match.group(0)
            if not token.strip() or match.group("comment"):
                continue
            if next_layout >= len(all_layouts):
                # A token with no layout record means a chunk went missing:
                # its original whitespace and comments are gone.
                unpaired_tokens += 1
                restored_parts.append(token)
                continue

            layout = all_layouts[next_layout]
            next_layout += 1
            restored_parts.append(layout.get("p", ""))

            ident = match.group("ident")
            if ident:
                orig = self.mm.get_original_name(ident)
                restored_parts.append(orig if orig else ident)
            else:
                restored_parts.append(token)

        for layout in all_layouts[next_layout:]:
            restored_parts.append(layout.get("p", ""))

        return "".join(restored_parts), next_layout, unpaired_tokens

    def restore(
        self,
        source_code: str,
        encryption_key: str | None = None,
        cipher: str | None = None,
    ) -> str:
        """Restore C source code using layout chunks."""
        if cipher is None:
            cipher = "stream" if encryption_key is not None else "none"
        self._cipher = make_cipher(cipher, encryption_key) if cipher != "none" else None

        lines = source_code.splitlines()
        chunks, metadata_comments, metadata_lines = self._locate_markers(
            source_code, lines
        )
        expected_layout_count = self._read_metadata(metadata_comments)

        # A valid (possibly empty) mapping from embedded metadata is enough;
        # fail only when there is genuinely no mapping source at all. A footer
        # is authoritative even when it carries no mapping.
        if (
            not metadata_comments
            and not self.mm.mapping
            and not self.mm.reverse_mapping
        ):
            raise ValueError(
                "No identifier mapping available for restoration. "
                "The obfuscated file has no embedded metadata and no key file "
                "was provided."
            )

        clean_code, all_layouts = self._split_lines_and_layouts(
            lines, chunks, metadata_lines
        )
        restored, consumed, unpaired = self._replay_token_stream(
            clean_code, all_layouts
        )
        self._verify_layout_balance(
            consumed, unpaired, len(all_layouts) - consumed, expected_layout_count
        )
        return restored

    @staticmethod
    def _verify_layout_balance(
        consumed: int,
        unpaired: int,
        leftover: int,
        expected_total: int | None = None,
    ) -> None:
        """Refuse to emit output when layout records and code tokens disagree.

        `expected_total` comes from the embedded metadata and is the only
        check that catches a *single* inserted or deleted record: such a
        change leaves a record count that a legitimate artifact can also
        have (0 or 1 leftover records), so the pairing checks alone cannot
        see it.
        """
        if unpaired:
            raise inconsistent(f"{unpaired} code token(s) have no layout record")
        if leftover > 1:
            raise inconsistent(
                f"it carries {consumed + leftover} layout record(s) for "
                f"{consumed} code token(s)"
            )
        total = consumed + leftover
        if expected_total is not None and total != expected_total:
            raise inconsistent(
                f"it carries {total} layout record(s) but its metadata "
                f"declares {expected_total}"
            )
