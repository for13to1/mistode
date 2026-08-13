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

"""
Python Code Obfuscator - Reliable and Reversible Obfuscation based on AST
"""

import ast
import base64
import builtins
import json
import keyword
import tokenize
import zlib
from io import StringIO
from typing import cast

from .core import MappingManager, NameGenerator
from .encrypt import EncryptionManager
from .layout import LayoutEngine


class ImportAnalyzer:
    """
    Import Analyzer - Identifies identifiers that should not be obfuscated,
    including imported names, built-ins, and other protected identifiers
    """

    def __init__(self) -> None:
        self.module_aliases: dict[str, str] = {}
        self.imported_names: set[str] = set()
        self.module_attrs: dict[str, set[str]] = {}

    def analyze(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    orig_name = alias.name
                    asname = alias.asname or alias.name
                    self.module_aliases[asname] = orig_name
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        name = alias.asname or alias.name
                        self.imported_names.add(name)
                        if node.module not in self.module_attrs:
                            self.module_attrs[node.module] = set()
                        self.module_attrs[node.module].add(alias.name)

    def is_imported_module(self, name: str) -> bool:
        return name in self.module_aliases

    def is_imported_name(self, name: str) -> bool:
        return name in self.imported_names


class PythonObfuscator:
    """
    Python Code Obfuscator - Ensures complete reversibility and consistent
    formatting
    """

    def __init__(
        self,
        mapping_manager: MappingManager,
        generator: NameGenerator,
        filename: str = "unknown",
    ):
        self.mm = mapping_manager
        self.gen = generator
        self.filename = filename

        self.ignore_set: set[str] = set(keyword.kwlist)
        self.ignore_set.update(dir(builtins))
        self.ignore_set.add("self")
        self.ignore_set.add("cls")

        self.import_analyzer = ImportAnalyzer()
        self._cached_tree: ast.AST | None = None
        self.preserved_keywords: set[str] = set()

        self.mapping_records: dict[str, str | dict[str, str]] = {
            "identifier_mapping": {},
            "docstring_mapping": {},
            "string_prefixes": {},
            "quote_types": {},
            "original_to_unparsed": {},
            "ordered_identifiers": [],
        }

    def obfuscate(
        self,
        source_code: str,
        mapping_file: str | None = None,
        embed_metadata: bool = True,
        encryption_key: str | None = None,
        source_encoding: str | None = None,
    ) -> str:
        # Initialize encryption manager if key is provided
        encryption_manager = (
            EncryptionManager(encryption_key) if encryption_key else None
        )

        self.mm.source_encoding = source_encoding

        tree = ast.parse(source_code)
        self._cached_tree = tree

        self.import_analyzer.analyze(tree)

        # Collect all keyword arguments used in calls to prevent obfuscating
        # external APIs
        self._collect_preserved_keywords(tree)
        self._collect_all_exports(tree)

        # Collect replacements for identifiers based on AST analysis
        replacements = self._collect_replacements(tree, source_code)

        # Generate obfuscated code and layout data using token stream transformation
        layout_engine = LayoutEngine()
        obfuscated_code = layout_engine.obfuscate_token_stream(
            source_code, replacements, encryption_manager
        )

        # Save layout data - NO LONGER NEEDED as it is interleaved
        # self.mapping_records["layout_data"] = ...

        if embed_metadata:
            metadata_comment = self._generate_metadata_comment(encryption_manager)
            obfuscated_code += f"\n\n{metadata_comment}"

        if mapping_file:
            self._save_mapping(mapping_file)

        return obfuscated_code

    def _collect_preserved_keywords(self, tree: ast.AST) -> None:
        """
        Collect all argument names used as keywords in calls.
        These must be preserved to avoid breaking external libraries matching.
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg:
                        self.preserved_keywords.add(kw.arg)

    def _collect_all_exports(self, tree: ast.AST) -> None:
        """
        Collect names declared in module-level `__all__` lists.

        These are the module's public contract and must keep their original
        names so `from module import *` (and external imports) keep working.
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(
                                    elt.value, str
                                ):
                                    self.ignore_set.add(elt.value)

    def _collect_replacements(  # noqa: C901
        self, tree: ast.AST, source_code: str
    ) -> dict[tuple[int, int], str]:
        """
        Traverse the AST to collect identifier replacements (line, col) -> new_name.
        Uses token stream analysis to pinpoint exact locations of definitions.
        """
        replacements: dict[tuple[int, int], str] = {}

        # Pre-tokenize source for precise location finding
        try:
            tokens = list(tokenize.generate_tokens(StringIO(source_code).readline))
        except tokenize.TokenError:
            # Fallback for invalid code (shouldn't happen here)
            tokens = []

        class ReplacementCollector(ast.NodeVisitor):
            def __init__(self, obfuscator, tokens, source_code):
                self.obfuscator = obfuscator
                self.tokens = tokens
                self.lines = source_code.splitlines()

            def _should_obfuscate(self, name: str) -> bool:
                return (
                    name not in self.obfuscator.ignore_set
                    and not name.startswith("_")
                    and not self.obfuscator.import_analyzer.is_imported_name(name)
                    and not self.obfuscator.import_analyzer.is_imported_module(name)
                    and name not in self.obfuscator.preserved_keywords
                )

            def _char_col(self, lineno: int, byte_col: int) -> int:
                """
                Convert an AST column (a UTF-8 byte offset) to the character
                offset used by tokenize, so multibyte characters (e.g. CJK)
                don't shift replacement positions.
                """
                if lineno > len(self.lines):
                    return byte_col
                line = self.lines[lineno - 1]
                return len(
                    line.encode("utf-8")[:byte_col].decode("utf-8", errors="ignore")
                )

            def _register_replacement(self, name: str, lineno: int, col_offset: int):
                if not lineno:
                    return
                new_name = self.obfuscator._generate_obfuscated_name(name)
                replacements[(lineno, col_offset)] = new_name

            def _find_def_name_location(  # noqa: C901
                self,
                node_lineno: int,
                name: str,
                is_class: bool = False,
                is_async: bool = False,
            ) -> tuple[int, int] | None:
                """
                Scan tokens starting from node_lineno to find the definition name.
                Skips decorators, looks for 'def'/'class' keyword then the name.
                """
                # Find start index in tokens (approximate binary search or scan)
                start_idx = 0
                for i, tok in enumerate(self.tokens):
                    if tok.start[0] >= node_lineno:
                        start_idx = i
                        break

                # Scan forward
                state = (
                    "search_keyword"  # search_keyword -> found_keyword -> found_name
                )
                # Keyword to look for
                target_keyword = "class" if is_class else "def"

                for i in range(start_idx, len(self.tokens)):
                    tok = self.tokens[i]
                    if tok.type == tokenize.NAME:
                        if state == "search_keyword":
                            if tok.string == target_keyword:
                                state = "found_keyword"
                            elif tok.string == "async" and is_async and not is_class:
                                pass  # Found async, next should be def
                            # Else it might be a decorator name or something, skip
                        elif state == "found_keyword":
                            if tok.string == name:
                                # Found exactly the name we want
                                return tok.start
                            # If we hit another keyword or unexpected token?
                            # Example: def foo ( ...
                            # 'foo' is NAME.
                            pass
                    elif tok.type == tokenize.OP:
                        pass  # punctuation

                    # Safety break if we go too far?
                    # E.g. next definition starts?
                    # But nested definitions exist.
                    # Just rely on finding the specific name soon after keyword.

                return None

            def visit_FunctionDef(self, node):
                if self._should_obfuscate(node.name):
                    # Find exact location in token stream
                    is_async = False  # Regular FunctionDef
                    loc = self._find_def_name_location(
                        node.lineno, node.name, is_class=False, is_async=is_async
                    )
                    if loc:
                        self._register_replacement(node.name, loc[0], loc[1])

                for arg in node.args.args:
                    if self._should_obfuscate(arg.arg):
                        self._register_replacement(
                            arg.arg,
                            arg.lineno,
                            self._char_col(arg.lineno, arg.col_offset),
                        )

                for arg in node.args.kwonlyargs:
                    if self._should_obfuscate(arg.arg):
                        self._register_replacement(
                            arg.arg,
                            arg.lineno,
                            self._char_col(arg.lineno, arg.col_offset),
                        )

                if node.args.vararg and self._should_obfuscate(node.args.vararg.arg):
                    self._register_replacement(
                        node.args.vararg.arg,
                        node.args.vararg.lineno,
                        node.args.vararg.col_offset,
                    )

                if node.args.kwarg and self._should_obfuscate(node.args.kwarg.arg):
                    self._register_replacement(
                        node.args.kwarg.arg,
                        node.args.kwarg.lineno,
                        node.args.kwarg.col_offset,
                    )

                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node):
                if self._should_obfuscate(node.name):
                    loc = self._find_def_name_location(
                        node.lineno, node.name, is_class=False, is_async=True
                    )
                    if loc:
                        self._register_replacement(node.name, loc[0], loc[1])

                # Visit body and args same as FunctionDef
                # Copying arg visiting logic since AsyncFunctionDef has same structure
                for arg in node.args.args:
                    if self._should_obfuscate(arg.arg):
                        self._register_replacement(
                            arg.arg,
                            arg.lineno,
                            self._char_col(arg.lineno, arg.col_offset),
                        )

                for arg in node.args.kwonlyargs:
                    if self._should_obfuscate(arg.arg):
                        self._register_replacement(
                            arg.arg,
                            arg.lineno,
                            self._char_col(arg.lineno, arg.col_offset),
                        )

                if node.args.vararg and self._should_obfuscate(node.args.vararg.arg):
                    self._register_replacement(
                        node.args.vararg.arg,
                        node.args.vararg.lineno,
                        node.args.vararg.col_offset,
                    )

                if node.args.kwarg and self._should_obfuscate(node.args.kwarg.arg):
                    self._register_replacement(
                        node.args.kwarg.arg,
                        node.args.kwarg.lineno,
                        node.args.kwarg.col_offset,
                    )

                self.generic_visit(node)

            def visit_ClassDef(self, node):
                # Class-level names (class variables, constants, enum
                # members, method names, nested classes) are referenced
                # via `Class.attr` / `obj.attr`, and attribute names are
                # never obfuscated. So these bound names must stay original
                # too, or attribute lookups break.
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name):
                                self.obfuscator.ignore_set.add(target.id)
                    elif isinstance(stmt, ast.AnnAssign) and isinstance(
                        stmt.target, ast.Name
                    ):
                        self.obfuscator.ignore_set.add(stmt.target.id)
                    elif isinstance(
                        stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        self.obfuscator.ignore_set.add(stmt.name)

                if self._should_obfuscate(node.name):
                    loc = self._find_def_name_location(
                        node.lineno, node.name, is_class=True
                    )
                    if loc:
                        self._register_replacement(node.name, loc[0], loc[1])
                self.generic_visit(node)

            def visit_Name(self, node):
                if isinstance(node.ctx, (ast.Store, ast.Load, ast.Del)):
                    if self._should_obfuscate(node.id):
                        self._register_replacement(
                            node.id,
                            node.lineno,
                            self._char_col(node.lineno, node.col_offset),
                        )

            def visit_arg(self, node):
                if self._should_obfuscate(node.arg):
                    self._register_replacement(
                        node.arg,
                        node.lineno,
                        self._char_col(node.lineno, node.col_offset),
                    )

            def visit_Call(self, node):
                for kw in node.keywords:
                    if kw.arg and self._should_obfuscate(kw.arg):
                        # kw.lineno/col_offset point to the argument name start
                        self._register_replacement(
                            kw.arg, kw.lineno, self._char_col(kw.lineno, kw.col_offset)
                        )
                self.generic_visit(node)

            def visit_Lambda(self, node):
                for arg in node.args.args:
                    if self._should_obfuscate(arg.arg):
                        self._register_replacement(
                            arg.arg,
                            arg.lineno,
                            self._char_col(arg.lineno, arg.col_offset),
                        )
                self.generic_visit(node)

        collector = ReplacementCollector(self, tokens, source_code)
        collector.visit(tree)
        return replacements

    def _generate_obfuscated_name(self, original: str) -> str:
        identifier_map: dict[str, str] = cast(
            dict[str, str], self.mapping_records["identifier_mapping"]
        )

        if original in identifier_map:
            return identifier_map[original]

        obfuscated = self.gen.generate()

        identifier_map[original] = obfuscated

        return obfuscated

    def _get_mapping_info(self) -> dict:
        """
        Get complete mapping information
        """
        return {
            "identifier_mapping": self.mapping_records["identifier_mapping"],
            "docstring_mapping": self.mapping_records["docstring_mapping"],
            "string_prefixes": self.mapping_records["string_prefixes"],
            "quote_types": self.mapping_records["quote_types"],
            "original_to_unparsed": self.mapping_records["original_to_unparsed"],
            "source_encoding": self.mm.source_encoding,
        }

    def _generate_metadata_comment(
        self, encryption_manager: EncryptionManager | None = None
    ) -> str:
        mapping_info = self._get_mapping_info()
        json_str = json.dumps(mapping_info, ensure_ascii=False)
        compressed = zlib.compress(json_str.encode("utf-8"))

        if encryption_manager:
            encoded = encryption_manager.encrypt(compressed)
            return f"#@mistode:secure_metadata:{encoded}"
        else:
            encoded = base64.b64encode(compressed).decode("ascii")
            return f"#@mistode:metadata:{encoded}"

    def _extract_metadata_from_code(
        self, code: str, encryption_manager: EncryptionManager | None = None
    ) -> dict | None:
        for line in code.splitlines():
            if encryption_manager and line.startswith("#@mistode:secure_metadata:"):
                try:
                    encoded = line.split(":", 2)[2].strip()
                    compressed = encryption_manager.decrypt(encoded)
                    json_str = zlib.decompress(compressed).decode("utf-8")
                    return json.loads(json_str)
                except Exception:
                    return None
            elif not encryption_manager and line.startswith("#@mistode:metadata:"):
                try:
                    encoded = line.split(":", 2)[2].strip()
                    compressed = base64.b64decode(encoded)
                    json_str = zlib.decompress(compressed).decode("utf-8")
                    return json.loads(json_str)
                except Exception:
                    return None
        return None

    def _save_mapping(self, mapping_file: str) -> None:
        mapping_info = self._get_mapping_info()
        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump(mapping_info, f, indent=2, ensure_ascii=False)

    def restore(  # noqa: C901
        self,
        mapping_file: str | None = None,
        obfuscated_code: str | None = None,
        encryption_key: str | None = None,
    ) -> str:
        mapping_info = {}
        encryption_manager = (
            EncryptionManager(encryption_key) if encryption_key else None
        )

        if mapping_file:
            with open(mapping_file, "r", encoding="utf-8") as f:
                mapping_info = json.load(f)

        if obfuscated_code and not mapping_info:
            extracted = self._extract_metadata_from_code(
                obfuscated_code, encryption_manager
            )
            if extracted:
                mapping_info = extracted

        if mapping_info.get("source_encoding"):
            self.mm.source_encoding = mapping_info["source_encoding"]

        if obfuscated_code is None:
            if self._cached_tree is None:
                raise ValueError(
                    "No obfuscated code provided. "
                    "Provide obfuscated_code or obfuscate first."
                )
            obfuscated_code = ast.unparse(self._cached_tree)

        if not mapping_info:
            raise ValueError(
                "No mapping provided via file or embedded metadata, "
                "or decryption failed (incorrect key?)."
            )

        identifier_mapping = mapping_info.get("identifier_mapping", {})
        reverse_mapping = {v: k for k, v in identifier_mapping.items()}

        # Strip metadata comment if present in the restoration input
        # The LayoutEngine expects clean obfuscated code (or code matching
        # the layout data exactly)
        # However, obfuscate() appended metadata after the code.
        # We need to remove the appended metadata part.

        clean_obfuscated_code = obfuscated_code
        if "#@mistode:" in obfuscated_code:
            # find the index
            idx = obfuscated_code.find("\n\n#@mistode:")
            if idx != -1:
                clean_obfuscated_code = obfuscated_code[:idx]
            else:
                # Try other format?
                idx = obfuscated_code.find("#@mistode:")
                if idx != -1:
                    # If it was at start of line
                    clean_obfuscated_code = obfuscated_code[:idx].rstrip()

        # Restore using LayoutEngine (Token Stream Restoration)
        # layout_data = mapping_info.get("layout_data", "") # Not used anymore
        layout_engine = LayoutEngine()
        restored_code = layout_engine.restore_token_stream(
            clean_obfuscated_code, reverse_mapping, encryption_manager
        )

        return restored_code
