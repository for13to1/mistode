import base64
import json
import tokenize
import zlib
from io import StringIO
from typing import Any

from .payload import (
    build_marker,
    classify_marker,
    decode_layouts,
    inconsistent,
    not_an_artifact,
    untokenisable,
)


class LayoutEngine:
    """
    Handles token-stream based obfuscation and restoration.
    Separates the code logic (Keywords, Ops, Renamed Identifiers) from
    Layout (Whitespace, Comments, String Styles).
    """

    # Number of layout records the last obfuscation run emitted. Embedded in
    # the metadata; see CObfuscator._verify_layout_balance for why.
    layout_count: int = 0

    def obfuscate_token_stream(  # noqa: C901
        self,
        source_code: str,
        replacements: dict[tuple[int, int], str],
        encryption_manager: Any | None = None,
    ) -> str:
        """Obfuscate `source_code` and interleave one layout chunk per line.

        `replacements` maps (line, character column) to the new identifier.
        Afterwards ``self.layout_count`` holds the number of layout records
        emitted; the caller embeds it in the metadata.
        """
        self.layout_count = 0
        source_io = StringIO(source_code)

        # (token_type, token_string, layout_metadata) for every kept token.
        # Layout entries accumulate until a newline is emitted, then get
        # compressed (and optionally encrypted) into one chunk comment.
        kept_tokens: list[tuple[int, str, dict[str, Any]]] = []

        # Buffer for 'skipped' content (whitespace, comments) that precedes
        # the next kept token
        pending_prefix = ""
        prev_end_pos = (1, 0)

        logical_line_start = True
        last_newline_empty = False

        # Split once: the gap calculation runs for every token and must not
        # re-scan the whole source each time.
        lines = source_code.splitlines(keepends=True)

        for tok in tokenize.generate_tokens(source_io.readline):
            token_type = tok.type
            token_string = tok.string
            start_line, start_col = tok.start
            end_line, end_col = tok.end

            if token_type == tokenize.NEWLINE:
                last_newline_empty = token_string == ""
                logical_line_start = True

            # 1. Gap since the previous token (whitespace, comments, ...)
            gap = ""
            if start_line > prev_end_pos[0]:
                # Part of prev line
                if prev_end_pos[0] <= len(lines):
                    gap += lines[prev_end_pos[0] - 1][prev_end_pos[1] :]
                # Intermediate lines
                for i in range(prev_end_pos[0], start_line - 1):
                    if i < len(lines):
                        gap += lines[i]
                # Indent of current line
                if start_line <= len(lines):
                    gap += lines[start_line - 1][:start_col]
            else:
                if start_line <= len(lines):
                    gap += lines[start_line - 1][prev_end_pos[1] : start_col]

            pending_prefix += gap
            prev_end_pos = (end_line, end_col)

            # 2. Filter / Transform Token

            # Skip Comments and Non-Structural Newlines (NL)
            if token_type == tokenize.COMMENT or token_type == tokenize.NL:
                pending_prefix += token_string
                continue

            # Update logical line start state
            if token_type in (
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.ENCODING,
            ):
                logical_line_start = True

            # A string at the start of a logical line is a docstring.
            # Emit `""` and keep the original text in the layout.
            if logical_line_start and token_type == tokenize.STRING:
                layout_meta = {"p": pending_prefix, "c": token_string}
                pending_prefix = ""
                kept_tokens.append((token_type, '""', layout_meta))
                logical_line_start = False
                continue

            if token_type not in (
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.ENCODING,
            ):
                logical_line_start = False

            # Handle Replacement (Identifiers)
            if token_type == tokenize.NAME and (start_line, start_col) in replacements:
                new_name = replacements[(start_line, start_col)]
                layout_meta = {"p": pending_prefix}
                pending_prefix = ""
                kept_tokens.append((token_type, new_name, layout_meta))
                continue

            # Keep Structural Tokens
            layout_meta = {"p": pending_prefix}
            pending_prefix = ""
            # Preserve the original newline text (e.g. `\r\n` on Windows)
            # so restoration is bit-perfect even for CRLF files.
            if token_type in (tokenize.NL, tokenize.NEWLINE):
                layout_meta["nl"] = token_string
            kept_tokens.append((token_type, token_string, layout_meta))

        # Trailing layout and the "no final newline" flag ride on a
        # synthetic ENDMARKER so restoration can reproduce them.
        if pending_prefix or last_newline_empty:
            meta = {"p": pending_prefix}
            if last_newline_empty:
                meta["no_eof_nl"] = True
            kept_tokens.append((tokenize.ENDMARKER, "", meta))

        # 3. Rebuild the obfuscated code, one chunk comment per line
        output_lines = []

        current_line_tokens: list[str] = []
        current_line_layouts: list[dict[str, Any]] = []

        indents = [""]
        at_line_start = True

        fstring_depth = 0
        FSTRING_START = tokenize.FSTRING_START
        FSTRING_END = tokenize.FSTRING_END
        FSTRING_MIDDLE = tokenize.FSTRING_MIDDLE

        for ttype, tstring, layout_meta in kept_tokens:
            if ttype == tokenize.ENDMARKER:
                # Trailing layout: end-of-file comments and newlines.
                if layout_meta:
                    current_line_layouts.append(layout_meta)
                continue

            # Indentation Logic

            if ttype == tokenize.INDENT:
                indents.append(tstring)
                # The next token emits the indent; INDENT only updates state.
                current_line_layouts.append(layout_meta)
                continue

            elif ttype == tokenize.DEDENT:
                if list(indents):
                    indents.pop()
                current_line_layouts.append(layout_meta)
                continue
            elif ttype in (tokenize.NL, tokenize.NEWLINE):
                current_line_layouts.append(layout_meta)
                self._flush_line(
                    output_lines,
                    current_line_tokens,
                    current_line_layouts,
                    encryption_manager,
                )

                current_line_tokens = []
                current_line_layouts = []
                at_line_start = True
                continue

            # Normal Token
            current_line_layouts.append(layout_meta)

            prefix_space = ""

            # f-string braces and text stay compact; expressions inside them
            # use normal spacing.
            in_fstring = fstring_depth > 0
            if ttype == FSTRING_START:
                fstring_depth += 1
            elif ttype == FSTRING_END:
                fstring_depth -= 1

            if at_line_start:
                if indents:
                    prefix_space = indents[-1]
                at_line_start = False
            else:
                if current_line_tokens:
                    prev_str = current_line_tokens[-1]
                    prev_clean = prev_str.strip()
                    if in_fstring:
                        # Inside an f-string: syntax characters and text
                        # segments must stay compact (`{x!r:>10}`), but
                        # expressions need normal spacing (`if last else`).
                        compact = (
                            ttype in (FSTRING_MIDDLE, FSTRING_END)
                            or tstring in ("{", "}")
                            or prev_clean in ("{", "!", ":")
                        )
                        if not compact and self._needs_space(prev_str, tstring, ttype):
                            prefix_space = " "
                    elif self._needs_space(prev_str, tstring, ttype):
                        prefix_space = " "

            current_line_tokens.append(prefix_space + tstring)

        # Flush any remaining
        if current_line_tokens or current_line_layouts:
            self._flush_line(
                output_lines,
                current_line_tokens,
                current_line_layouts,
                encryption_manager,
            )

        return "\n".join(output_lines)

    def _needs_space(self, prev_str: str, curr_str: str, curr_type: int) -> bool:
        """Determines if space is needed between tokens."""
        # Clean prev_str from whitespace added
        prev_clean = prev_str.strip()
        if not prev_clean or not curr_str:
            return False

        # 1. Alphanumeric + Alphanumeric -> Space
        # (Keywords are Names/Alpha)
        if (prev_clean[-1].isalnum() or prev_clean[-1] == "_") and (
            curr_str[0].isalnum() or curr_str[0] == "_"
        ):
            return True

        # 2. specific cases
        if curr_type in (tokenize.NUMBER, tokenize.STRING) and (
            prev_clean[-1].isalnum() or prev_clean[-1] == "_"
        ):
            return True

        if curr_str == "." and prev_clean == "from":
            return True

        if prev_clean == ",":
            return True

        # Heuristic for operators
        if (prev_clean[-1].isalnum() or prev_clean[-1] == "_") and not curr_str[
            0
        ].isalnum():
            # Avoid space before: . ( [ ) ] : ,
            if curr_str not in (".", "(", "[", ")", "]", ":", ","):
                return True

        if not prev_clean[-1].isalnum() and (
            curr_str[0].isalnum() or curr_str[0] == "_"
        ):
            # Avoid space after: . ( [ { @
            if prev_clean not in (".", "(", "[", "{", "@"):
                return True

        return False

    def _flush_line(
        self,
        output_lines: list[str],
        tokens: list[str],
        layouts: list[dict],
        encryption_manager: Any | None,
    ):
        """Generates the layout comment and the code line."""
        if not tokens and not layouts:
            return

        # Compress Layouts
        json_bytes = json.dumps(layouts).encode("utf-8")
        compressed = zlib.compress(json_bytes)
        self.layout_count += len(layouts)

        secure = encryption_manager is not None
        if secure:
            encoded = encryption_manager.encrypt(compressed)
        else:
            encoded = base64.b64encode(compressed).decode("ascii")
        comment = build_marker("chunk", "python", encoded, secure)

        output_lines.append(comment)

        code_line = "".join(tokens)
        output_lines.append(code_line)

    def _collect_chunk_payloads(
        self, obfuscated_code: str
    ) -> dict[int, tuple[str, bool]]:
        """Map the line number of each chunk marker to its payload.

        Chunks are emitted one per obfuscated line. Only a real COMMENT token
        is layout data: identical text inside a multi-line string is string
        content, and treating it as a chunk would drop code or corrupt the
        layout queue.
        """
        chunk_payloads: dict[int, tuple[str, bool]] = {}
        try:
            for tok in tokenize.generate_tokens(StringIO(obfuscated_code).readline):
                if tok.type != tokenize.COMMENT:
                    continue
                marker = classify_marker(tok.string, "python")
                if marker is None or marker[0] != "chunk":
                    continue
                _, payload, secure = marker
                chunk_payloads[tok.start[0]] = (payload, secure)
        except tokenize.TokenError as exc:
            # Without a complete token stream no marker can be trusted, and
            # the file may still contain chunks that were simply not reached.
            # Report the tokenising failure rather than letting the missing
            # markers look like "this is not a Mistode artifact".
            raise untokenisable(exc) from exc
        return chunk_payloads

    def _split_lines_and_layouts(
        self,
        obfuscated_code: str,
        chunk_payloads: dict[int, tuple[str, bool]],
        encryption_manager: Any | None,
    ) -> tuple[list[str], list[dict]]:
        """Split the artifact into clean code lines and flattened layouts.

        Chunk lines are dropped; the layouts they carry are decoded and
        associated with the code line that follows them, then flattened in
        emission order. Layouts after the last code line (end-of-file
        whitespace) are kept.
        """
        lines = obfuscated_code.splitlines()

        clean_lines: list[str] = []
        all_layouts: list[dict] = []
        # Layouts buffered between code lines: they belong to the next one.
        pending: list[dict] = []

        for lineno, line in enumerate(lines, start=1):
            if lineno in chunk_payloads:
                payload, secure = chunk_payloads[lineno]
                pending.extend(
                    decode_layouts(payload, secure=secure, cipher=encryption_manager)
                )
                continue

            # This is a code line (or empty)
            clean_lines.append(line)
            if pending:
                all_layouts.extend(pending)
                pending = []

        # Layouts after the last code line are end-of-file whitespace.
        all_layouts.extend(pending)

        return clean_lines, all_layouts

    def _replay_token_stream(
        self,
        clean_code: str,
        all_layouts: list[dict],
        reverse_mapping: dict[str, str],
    ) -> str:
        """Rebuild the original text by replaying layouts onto each token.

        Flattened in emission order, the layouts line up 1:1 with the kept
        tokens of the cleaned code. A mismatch means a chunk marker was
        inserted or lost, which would silently shift every following line.
        """
        result_parts = []

        # Tokenise up front so a file that cannot be tokenised at all is
        # reported as such: inside the loop it would surface as a short token
        # stream and be misreported as a missing chunk marker.
        try:
            tokens = list(tokenize.generate_tokens(StringIO(clean_code).readline))
        except tokenize.TokenError as exc:
            raise untokenisable(exc) from exc

        consumed = 0
        layout_iter = iter(all_layouts)

        for tok in tokens:
            token_type = tok.type
            token_string = tok.string

            if token_type in (tokenize.NL, tokenize.COMMENT):
                continue

            # `next(..., None)` rather than StopIteration handling: running
            # out of layouts is reported here, not by the iterator ending.
            meta = next(layout_iter, None)
            if meta is None:
                raise inconsistent("it has fewer layout records than code tokens")
            consumed += 1
            prefix = meta.get("p", "")

            result_parts.append(prefix)

            if token_type == tokenize.ENDMARKER:
                break

            content = token_string
            if token_type == tokenize.NAME and token_string in reverse_mapping:
                content = reverse_mapping[token_string]

            # If layout specifies content (e.g. restored docstring), use it
            if "c" in meta:
                content = meta["c"]
            # Restore the original newline text (e.g. `\r\n` on Windows)
            elif "nl" in meta:
                content = meta["nl"]

            result_parts.append(content)

        # At most one layout record may be left over: the trailing record
        # carries end-of-file whitespace. More than that means extra chunk
        # data was injected.
        leftover = len(all_layouts) - consumed
        if leftover > 1:
            raise inconsistent(
                f"it carries {len(all_layouts)} layout record(s) for "
                f"{consumed} code token(s)"
            )

        return "".join(result_parts)

    def restore_token_stream(
        self,
        obfuscated_code: str,
        reverse_mapping: dict[str, str],
        encryption_manager: Any | None = None,
        expected_layout_count: int | None = None,
    ) -> str:
        """Restore original code from an artifact with interleaved comments.

        `expected_layout_count` comes from the embedded metadata; when given,
        it is compared with the records actually read before anything is
        returned.
        """
        chunk_payloads = self._collect_chunk_payloads(obfuscated_code)

        clean_lines, all_layouts = self._split_lines_and_layouts(
            obfuscated_code, chunk_payloads, encryption_manager
        )

        # Every text tokenises to at least an ENDMARKER, so no layouts at all
        # means nothing was inserted or removed: this is not an artifact, and
        # calling it a lost chunk would send the reader hunting for one that
        # never existed.
        if not all_layouts:
            raise not_an_artifact()

        clean_code_base = "\n".join(clean_lines)

        # `no_eof_nl` on the last layout means the source had no trailing
        # newline; otherwise re-add one (splitlines/join drops it).
        append_newline = not all_layouts[-1].get("no_eof_nl")

        if append_newline:
            clean_code = clean_code_base + "\n"
        else:
            clean_code = clean_code_base

        result = self._replay_token_stream(clean_code, all_layouts, reverse_mapping)

        # Authoritative check: the artifact declares how many layout records
        # it should carry, which catches what the pairing checks cannot (see
        # CObfuscator._verify_layout_balance).
        if expected_layout_count is not None and len(all_layouts) != (
            expected_layout_count
        ):
            raise inconsistent(
                f"it carries {len(all_layouts)} layout record(s) but its "
                f"metadata declares {expected_layout_count}"
            )

        return result
