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
import zlib
from typing import Dict, Optional, Set, cast

from .core import MappingManager, NameGenerator


class ImportAnalyzer:
    """
    Import Statement Analyzer - Identifies identifiers that should not be
    obfuscated
    """

    def __init__(self) -> None:
        self.module_aliases: Dict[str, str] = {}
        self.imported_names: Set[str] = set()
        self.module_attrs: Dict[str, Set[str]] = {}

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

    def get_module_name(self, alias: str) -> Optional[str]:
        return self.module_aliases.get(alias)

    def is_imported_name(self, name: str) -> bool:
        return name in self.imported_names

    def is_module_attribute(self, module: str, attr: str) -> bool:
        if module in self.module_attrs:
            return attr in self.module_attrs[module]
        return False


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

        self.ignore_set: Set[str] = set(keyword.kwlist)
        self.ignore_set.update(dir(builtins))
        self.ignore_set.add("self")
        self.ignore_set.add("cls")

        self.import_analyzer = ImportAnalyzer()
        self._cached_tree: Optional[ast.AST] = None

        self.mapping_records: Dict[str, str | Dict[str, str]] = {
            "identifier_mapping": {},
            "docstring_mapping": {},
            "string_prefixes": {},
            "quote_types": {},
            "original_to_unparsed": {},
        }

    def obfuscate(
        self,
        source_code: str,
        mapping_file: Optional[str] = None,
        embed_metadata: bool = True,
    ) -> str:

        tree = ast.parse(source_code)
        self._cached_tree = tree

        self.import_analyzer.analyze(tree)

        # Transform the AST to obfuscate identifiers with proper scoping
        transformed_tree = self._obfuscate_identifiers(tree)

        # Generate the obfuscated code from the transformed AST
        obfuscated_code = ast.unparse(transformed_tree)

        # Inject original source as distributed comments
        obfuscated_code = self._inject_source_as_comments(source_code, obfuscated_code)

        if embed_metadata:
            metadata_comment = self._generate_metadata_comment()
            obfuscated_code += f"\n\n{metadata_comment}"

        if mapping_file:
            self._save_mapping(mapping_file)

        return obfuscated_code

    def _inject_source_as_comments(self, source_code: str, obfuscated_code: str) -> str:
        compressed = zlib.compress(source_code.encode("utf-8"))
        encoded = base64.b64encode(compressed).decode("ascii")

        lines = obfuscated_code.splitlines()
        if not lines:
            return obfuscated_code

        import math

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
            new_lines.append(f"#@mistode:chunk:{chunk}")
            new_lines.append(line)

        return "\n".join(new_lines)

    def _extract_source_from_comments(self, obfuscated_code: str) -> Optional[str]:
        chunks = []
        lines = obfuscated_code.splitlines()
        found_any = False

        prefix = "#@mistode:chunk:"

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(prefix):
                chunk = stripped[len(prefix) :]
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

    def _obfuscate_identifiers(self, tree: ast.AST) -> ast.AST:
        """
        Transform the AST to obfuscate identifiers while properly handling scoping.
        This method now uses a proper NodeVisitor/NodeTransformer approach.
        """

        class ObfuscationTransformer(ast.NodeTransformer):
            def __init__(self, obfuscator):
                self.obfuscator = obfuscator
                self.scope_stack = []

            def _process_arguments(self, args):
                """
                Process function argument obfuscation
                """
                original_args = []
                for arg in args:
                    original_args.append(arg.arg)
                    if (
                        arg.arg not in self.obfuscator.ignore_set
                        and not arg.arg.startswith("_")
                    ):
                        arg.arg = self.obfuscator._generate_obfuscated_name(arg.arg)
                return original_args

            def visit_FunctionDef(self, node):
                if (
                    node.name not in self.obfuscator.ignore_set
                    and not node.name.startswith("_")
                ):
                    original_name = node.name
                    node.name = self.obfuscator._generate_obfuscated_name(original_name)

                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    docstring_node = node.body[0].value
                    original_doc = docstring_node.value
                    if original_doc.strip() and not node.name.startswith("_"):
                        obfuscated_doc = self.obfuscator._generate_obfuscated_docstring(
                            original_doc
                        )
                        docstring_map: Dict[str, str] = cast(
                            Dict[str, str],
                            self.obfuscator.mapping_records["docstring_mapping"],
                        )
                        docstring_map[original_doc] = obfuscated_doc
                        docstring_node.value = obfuscated_doc

                original_args = self._process_arguments(node.args.args)
                self.scope_stack.append(set(original_args))
                node.body = [self.visit(item) for item in node.body]
                self.scope_stack.pop()

                return node

            def visit_Lambda(self, node):
                original_args = self._process_arguments(node.args.args)
                self.scope_stack.append(set(original_args))
                node.body = self.visit(node.body)
                self.scope_stack.pop()
                return node

            def visit_arg(self, node):
                return node

            def visit_Name(self, node):
                current_scope = set()
                for scope in self.scope_stack:
                    current_scope.update(scope)

                should_obfuscate = (
                    node.id not in self.obfuscator.ignore_set
                    and not node.id.startswith("_")
                    and not self.obfuscator.import_analyzer.is_imported_name(node.id)
                    and not self.obfuscator.import_analyzer.is_imported_module(node.id)
                )

                if should_obfuscate:
                    node.id = self.obfuscator._generate_obfuscated_name(node.id)

                return node

            def visit_ClassDef(self, node):
                if (
                    node.name not in self.obfuscator.ignore_set
                    and not node.name.startswith("_")
                ):
                    node.name = self.obfuscator._generate_obfuscated_name(node.name)

                self.generic_visit(node)
                return node

            def visit_Call(self, node):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    identifier_map = self.obfuscator.mapping_records[
                        "identifier_mapping"
                    ]

                    if func_name in identifier_map:
                        for kw_arg in node.keywords:
                            if kw_arg.arg and kw_arg.arg in identifier_map:
                                kw_arg.arg = identifier_map[kw_arg.arg]

                self.generic_visit(node)
                return node

        transformer = ObfuscationTransformer(self)
        return transformer.visit(tree)

    def _should_preserve_attribute(self, node: ast.Attribute) -> bool:
        base = node.value

        if isinstance(base, ast.Constant):
            return True

        builtin_methods = {
            "strip",
            "upper",
            "lower",
            "replace",
            "split",
            "join",
            "find",
            "format",
            "encode",
            "decode",
            "append",
            "extend",
            "pop",
            "remove",
            "insert",
            "sort",
            "reverse",
            "keys",
            "values",
            "items",
            "get",
            "update",
            "copy",
            "clear",
            "startswith",
            "endswith",
            "count",
            "index",
            "isalnum",
            "isalpha",
            "isdigit",
            "islower",
            "isupper",
        }
        if node.attr in builtin_methods:
            return True

        if isinstance(base, ast.Name):
            if self.import_analyzer.is_imported_name(base.id):
                return True

        return False

    def _generate_obfuscated_name(self, original: str) -> str:
        identifier_map: Dict[str, str] = cast(
            Dict[str, str], self.mapping_records["identifier_mapping"]
        )

        if original in identifier_map:
            return identifier_map[original]

        obfuscated = self.gen.generate()

        identifier_map[original] = obfuscated

        return obfuscated

    def _generate_obfuscated_docstring(self, original_doc: str) -> str:
        import hashlib

        doc_hash = hashlib.sha256(original_doc.encode()).hexdigest()[:12]
        return f"Obfuscated Docstring: {doc_hash}"

    def _get_mapping_info(self) -> Dict:
        """
        Get complete mapping information
        """
        return {
            "identifier_mapping": self.mapping_records["identifier_mapping"],
            "docstring_mapping": self.mapping_records["docstring_mapping"],
            "string_prefixes": self.mapping_records["string_prefixes"],
            "quote_types": self.mapping_records["quote_types"],
            "original_to_unparsed": self.mapping_records["original_to_unparsed"],
        }

    def _generate_metadata_comment(self) -> str:
        mapping_info = self._get_mapping_info()
        json_str = json.dumps(mapping_info, ensure_ascii=False)
        compressed = zlib.compress(json_str.encode("utf-8"))
        encoded = base64.b64encode(compressed).decode("ascii")
        return f"#@mistode:metadata:{encoded}"

    def _extract_metadata_from_code(self, code: str) -> Optional[Dict]:
        for line in code.splitlines():
            if line.startswith("#@mistode:metadata:"):
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

    def restore(self, mapping_file: str, obfuscated_code: Optional[str] = None) -> str:
        mapping_info = {}
        if mapping_file:
            with open(mapping_file, "r", encoding="utf-8") as f:
                mapping_info = json.load(f)

        if obfuscated_code and not mapping_info:
            extracted = self._extract_metadata_from_code(obfuscated_code)
            if extracted:
                mapping_info = extracted

        if obfuscated_code:
            original_source = self._extract_source_from_comments(obfuscated_code)
            if original_source:
                return original_source

        if not mapping_info:
            raise ValueError("No mapping provided via file or embedded metadata.")

        identifier_mapping = mapping_info["identifier_mapping"]
        reverse_mapping = {v: k for k, v in identifier_mapping.items()}
        docstring_mapping = mapping_info.get("docstring_mapping", {})

        if obfuscated_code is None:
            if self._cached_tree is None:
                raise ValueError(
                    "No obfuscated code provided. "
                    "Provide obfuscated_code or obfuscate first."
                )
            obfuscated_code = ast.unparse(self._cached_tree)

        tree = ast.parse(obfuscated_code)

        class RestorationTransformer(ast.NodeTransformer):
            def __init__(self, reverse_mapping, docstring_mapping):
                self.reverse_mapping = reverse_mapping
                self.docstring_mapping = docstring_mapping

            def visit_FunctionDef(self, node):
                if node.name in self.reverse_mapping:
                    node.name = self.reverse_mapping[node.name]

                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    docstring_node = node.body[0].value
                    obfuscated_doc = docstring_node.value
                    # Look for the original docstring in the mapping
                    for original, obfuscated in self.docstring_mapping.items():
                        if obfuscated == obfuscated_doc:
                            docstring_node.value = original
                            break

                for arg in node.args.args:
                    if arg.arg in self.reverse_mapping:
                        arg.arg = self.reverse_mapping[arg.arg]

                # Visit the function body
                self.generic_visit(node)
                return node

            def visit_Lambda(self, node):
                # Restore lambda arguments
                for arg in node.args.args:
                    if arg.arg in self.reverse_mapping:
                        arg.arg = self.reverse_mapping[arg.arg]

                # Visit the lambda body
                self.generic_visit(node)
                return node

            def visit_arg(self, node):
                return node

            def visit_Name(self, node):
                if node.id in self.reverse_mapping:
                    node.id = self.reverse_mapping[node.id]
                return node

            def visit_ClassDef(self, node):
                if node.name in self.reverse_mapping:
                    node.name = self.reverse_mapping[node.name]

                self.generic_visit(node)
                return node

        transformer = RestorationTransformer(reverse_mapping, docstring_mapping)
        restored_tree = transformer.visit(tree)

        restored_code = ast.unparse(restored_tree)
        return restored_code
