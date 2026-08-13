import base64
import json
import tokenize
import zlib
from io import StringIO
from typing import Any


class LayoutEngine:
    """
    Handles token-stream based obfuscation and restoration.
    Separates the code logic (Keywords, Ops, Renamed Identifiers) from
    Layout (Whitespace, Comments, String Styles).
    """

    def obfuscate_token_stream(  # noqa: C901
        self,
        source_code: str,
        replacements: dict[tuple[int, int], str],
        encryption_manager: Any | None = None,
    ) -> str:
        """
        Obfuscates the source code by filtering the token stream.
        Generates interleaved layout comments.

        Args:
            source_code: Original source.
            replacements: Dict mapping (line, col) -> new_name.
            encryption_manager: Optional manager to encrypt layout chunks.

        Returns:
            obfuscated_code (with interleaved comments)
        """
        source_io = StringIO(source_code)

        # We need to buffer tokens and layout data until we emit a line in
        # the obfuscated code.
        # Structure:
        # [ (layout_entry, token_tuple), (layout_entry, token_tuple), ... ]
        # When we decide to emit a newline in obfuscated code, we take the
        # accumulated layout entries, compress/encrypt them, allow the code
        # line to follow.

        kept_tokens: list[tuple[int, str, dict[str, Any]]] = []
        # list of (token_type, token_string, layout_metadata_for_this_token)

        # Buffer for 'skipped' content (whitespace, comments) that precedes
        # the next kept token
        pending_prefix = ""
        prev_end_pos = (1, 0)

        logical_line_start = True
        last_newline_empty = False

        for tok in tokenize.generate_tokens(source_io.readline):
            token_type = tok.type
            token_string = tok.string
            start_line, start_col = tok.start
            end_line, end_col = tok.end

            # Reset flag on every token, only set it when NEWLINE is processed?
            # Or just set it when NEWLINE matches.
            if token_type == tokenize.NEWLINE:
                last_newline_empty = token_string == ""
                # A newline always means the next token is at the start of
                # a logical line
                logical_line_start = True
            else:
                # If we see any other token after newline (e.g. DEDENT? ENDMARKER?),
                # we keep the state if it was the last significant thing.
                # Actually ENDMARKER comes right after.
                pass

            # 1. Calc Whitespace/Gap since last token
            gap = ""
            if start_line > prev_end_pos[0]:
                lines = source_code.splitlines(keepends=True)
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
                layout_lines = source_code.splitlines(keepends=True)
                if start_line <= len(layout_lines):
                    gap += layout_lines[start_line - 1][prev_end_pos[1] : start_col]

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

            # Docstring Obfuscation:
            # If we are at logical line start and see a string, it is likely
            # a docstring.
            # We replace it with an empty string (or minimal) to save
            # space/secure it, and store the original content in the layout
            # for restoration.
            if logical_line_start and token_type == tokenize.STRING:
                layout_meta = {
                    "p": pending_prefix,
                    "c": token_string,  # Save content for restoration
                }
                pending_prefix = ""
                # Use empty string as obfuscated token
                # Note: tokenize.untokenize might expect quotes?
                # If we produce `""`, it's valid.
                kept_tokens.append((token_type, '""', layout_meta))

                # Consume it from logical line standpoint
                # (Next token still starts a logical line? No, docstring is a statement)
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

        # Handle trailing layout
        if pending_prefix or last_newline_empty:
            # Attach to a dummy ENDMARKER or just last token?
            # We can attach to a virtual token
            meta = {"p": pending_prefix}
            if last_newline_empty:
                meta["no_eof_nl"] = True
            kept_tokens.append((tokenize.ENDMARKER, "", meta))

        # 3. Reconstruct Obfuscated Code with Interleaved Comments
        output_lines = []

        current_line_tokens: list[str] = []
        current_line_layouts: list[dict[str, Any]] = []

        indents = [""]
        at_line_start = True

        fstring_depth = 0
        FSTRING_START = tokenize.FSTRING_START
        FSTRING_END = tokenize.FSTRING_END

        for idx, (ttype, tstring, layout_meta) in enumerate(kept_tokens):
            if ttype == tokenize.ENDMARKER:
                # Just save the layout if there is any important suffix
                # Typically this is trailing newlines/comments of the file
                if layout_meta:
                    current_line_layouts.append(layout_meta)
                continue

            # Indentation Logic

            if ttype == tokenize.INDENT:
                indents.append(tstring)
                # INDENT changes state but doesn't consume "start of line" for content.
                # The next token (e.g. NAME) will handle printing the indent.

                current_line_layouts.append(layout_meta)
                continue

            elif ttype == tokenize.DEDENT:
                if list(indents):
                    indents.pop()
                current_line_layouts.append(layout_meta)
                continue
            elif ttype in (tokenize.NL, tokenize.NEWLINE):
                # End of line in Obfuscated Code
                current_line_layouts.append(layout_meta)

                # Flush current line
                self._flush_line(
                    output_lines,
                    current_line_tokens,
                    current_line_layouts,
                    encryption_manager,
                )

                # Reset
                current_line_tokens = []
                current_line_layouts = []
                at_line_start = True
                continue

            # Normal Token
            current_line_layouts.append(layout_meta)

            # Formatting (Spacing) logic similar to before
            # Determine if we need space before this token
            prefix_space = ""

            # Check F-String state to prevent spacing inside strings
            in_fstring = fstring_depth > 0

            # Update depth
            if ttype == FSTRING_START:
                fstring_depth += 1
            elif ttype == FSTRING_END:
                fstring_depth -= 1

            if at_line_start:
                if indents:
                    prefix_space = indents[-1]
                at_line_start = False
            else:
                # Minimal spacing logic
                if current_line_tokens:
                    prev_str = current_line_tokens[-1]
                    # Only apply spacing logic if NOT inside an f-string
                    if not in_fstring:
                        # But wait, FSTRING_START itself needs space?
                        # in_fstring uses state BEFORE update.
                        # So FSTRING_START (depth=0) gets space. Correct.
                        if self._needs_space(prev_str, tstring, ttype):
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

        encoded = ""
        if encryption_manager:
            encoded = encryption_manager.encrypt(compressed)
            comment = f"#@mistode:secure_chunk:{encoded}"
        else:
            encoded = base64.b64encode(compressed).decode("ascii")
            comment = f"#@mistode:chunk:{encoded}"

        output_lines.append(comment)

        code_line = "".join(tokens)
        output_lines.append(code_line)

    def restore_token_stream(  # noqa: C901
        self,
        obfuscated_code: str,
        reverse_mapping: dict[str, str],
        encryption_manager: Any | None = None,
    ) -> str:
        """
        Restores original code from obfuscated code with interleaved comments.
        """
        result_parts = []

        # We process line by line (or chunk by chunk)
        # 1. Read layout comment
        # 2. Read code line
        # 3. Tokenize code line
        # 4. Apply layout

        # Since tokenize works best on full stream or line-by-line,
        # we can iterate lines, check for comment, parse it.

        lines = obfuscated_code.splitlines()

        # Tokenizer on the stripped code?
        # If we just tokenize the whole file, we get tokens.
        # But we need to sync them with the Layout Chunks.
        # The Layout Chunks were emitted per *Obfuscated Line*.
        # So we should iterate the Obfuscated Lines, grab the tokens in
        # them, apply layout.

        # But `tokenize` might span lines (multi-line strings?).
        # Our obfuscator construction puts everything on one line unless it
        # was naturally split by our logic.
        # But we preserved NEWLINEs as structural, so it should be largely
        # line-correspondent.

        # Strategy:
        # Pre-process lines to extract layout chunks map: LineIndex -> LayoutData
        # Then tokenize the CLEAN code.
        # As we iterate tokens, check which line they are on, consume
        # LayoutData for that line.

        clean_lines = []
        layout_map = {}  # code_line_idx -> [layout_dicts]

        current_line_idx = 0
        current_layout_data = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#@mistode:chunk:") or stripped.startswith(
                "#@mistode:secure_chunk:"
            ):
                # Parse Layout
                try:
                    payload = stripped.split(":", 2)[2]
                    if (
                        stripped.startswith("#@mistode:secure_chunk:")
                        and encryption_manager
                    ):
                        decoded = encryption_manager.decrypt(payload)
                    else:
                        decoded = base64.b64decode(payload)

                    decompressed = zlib.decompress(decoded)
                    chunk_layouts = json.loads(decompressed.decode("utf-8"))
                    # If multiple comment lines appear (rare), extend?
                    # Our logic emits one comment per code line.
                    current_layout_data.extend(chunk_layouts)
                except Exception:
                    # Ignore invalid chunks
                    pass
                continue

            # This is a code line (or empty)
            clean_lines.append(line)
            if current_layout_data:
                layout_map[current_line_idx] = current_layout_data
                current_layout_data = []  # consumed
            current_line_idx += 1

        if current_layout_data:
            layout_map[current_line_idx] = current_layout_data

        clean_code_base = "\n".join(clean_lines)

        # Validation: If we have code but NO layout found, implementation
        # assumes it's not a proper mistode obfuscated file
        if clean_code_base.strip() and not layout_map:
            raise ValueError(
                "File does not appear to be obfuscated (no layout chunks found)."
            )

        # Check for no_eof_nl flag in the last layout chunk (ENDMARKER)
        # If the flag is present, it means the original file did NOT have
        # a trailing newline.
        # Otherwise, implies it DID (or default behavior).
        # We default to appending \n because splitlines/join eats the final
        # one.

        append_newline = True

        all_layouts = []
        for idx in range(len(clean_lines) + 1):  # Covers potential trailing layout
            if idx in layout_map:
                all_layouts.extend(layout_map[idx])

        if all_layouts:
            last_meta = all_layouts[-1]
            if last_meta.get("no_eof_nl"):
                append_newline = False

        if append_newline:
            clean_code = clean_code_base + "\n"
        else:
            clean_code = clean_code_base

        # Now tokenize clean_code
        try:
            # We need a global token index counter per line?
            # Or just a global queue of layout items?
            # If we flatten the layout_data from all lines, it should match
            # the token stream sequence!
            # Because `kept_tokens` was sequential.

            layout_iter = iter(all_layouts)

            for tok in tokenize.generate_tokens(StringIO(clean_code).readline):
                token_type = tok.type
                token_string = tok.string

                if token_type in (tokenize.NL, tokenize.COMMENT):
                    continue

                # Fetch layout (if available)
                meta = next(layout_iter, {})
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

        except StopIteration, tokenize.TokenError:
            pass

        return "".join(result_parts)
