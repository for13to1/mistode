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

"""Directory scanning, asset mirroring and cross-file analysis."""

import ast
import shutil
from collections.abc import Callable
from pathlib import Path

from .c import CObfuscator
from .core import MappingManager, NameGenerator

SUPPORTED_EXTS = {".py", ".c", ".h", ".cpp"}

# Build output, caches and virtualenvs. A project mirrored without these is
# still complete.
SKIP_DIRS = {
    "build",
    "dist",
    "bin",
    "obj",
    "out",
    "target",
    "CMakeFiles",
    "Debug",
    "Release",
    "node_modules",
    "venv",
    "env",
    "__pycache__",
}

ASSET_SKIP_DIRS = SKIP_DIRS | {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
}

ASSET_SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".o",
    ".obj",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".a",
    ".lib",
}

# Excluded only when --assets-skip-secrets is given.
SECRET_PATTERNS = (".env", ".env.", ".pem", ".key", ".pfx", ".p12", ".keystore")


def is_python_file(path: Path) -> bool:
    return path.suffix.lower() == ".py"


def in_skipped_dir(path: Path, root: Path) -> bool:
    """True if any path component is hidden (dot-prefixed, covering
    .git/.venv/.idea/...) or is a known build/artifact directory."""
    return any(
        part.startswith(".") or part in SKIP_DIRS
        for part in path.relative_to(root).parts
    )


def collect_source_files(directory: Path) -> list[Path]:
    """Recursively collect supported source files, skipping hidden,
    virtualenv and build/artifact directories."""
    return sorted(
        p
        for p in directory.rglob("*")
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_EXTS
        and not in_skipped_dir(p, directory)
    )


def _is_secret_like(path: Path) -> bool:
    name = path.name.lower()
    return any(
        name == p or name.startswith(p) or name.endswith(p) for p in SECRET_PATTERNS
    )


def collect_asset_files(directory: Path, skip_secrets: bool = False) -> list[Path]:
    """Files that are not obfuscated sources but belong to the deliverable
    (templates, data, configs, images...)."""
    assets = []
    for p in sorted(directory.rglob("*")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(directory).parts
        if any(
            part in ASSET_SKIP_DIRS or part.startswith(".") for part in rel_parts[:-1]
        ):
            continue
        if p.suffix.lower() in SUPPORTED_EXTS:
            continue
        if p.suffix.lower() in ASSET_SKIP_SUFFIXES:
            continue
        if skip_secrets and _is_secret_like(p):
            continue
        assets.append(p)
    return assets


def copy_assets(source_dir: Path, out_dir: Path, skip_secrets: bool = False) -> int:
    """Mirror non-source files so the obfuscated tree stays runnable."""
    assets = collect_asset_files(source_dir, skip_secrets)
    for p in assets:
        dest = out_dir / p.relative_to(source_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    return len(assets)


class ProjectAnalyzer:
    """Cross-file analyses for project mode.

    ``read_text`` is injected so encoding handling stays in the CLI.
    """

    def __init__(self, root: Path, read_text: Callable[[Path], str]):
        self.root = root
        self._read_text = read_text

    def _parse(self, path: Path) -> ast.AST | None:
        try:
            return ast.parse(self._read_text(path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            return None

    def _python_trees(self, files: list[Path]) -> list[tuple[Path, ast.AST]]:
        trees = []
        for f in files:
            if not is_python_file(f):
                continue
            tree = self._parse(f)
            if tree is not None:
                trees.append((f, tree))
        return trees

    # ----- Python: module surface -------------------------------------

    @staticmethod
    def collect_module_level_names(tree: ast.AST) -> set[str]:  # noqa: C901
        """Module-scope definitions, including those nested in
        `if`/`try`/`with` blocks."""
        names: set[str] = set()

        def visit(stmts):
            for stmt in stmts:
                if isinstance(
                    stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    names.add(stmt.name)
                elif isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            names.add(target.id)
                elif isinstance(stmt, ast.AnnAssign) and isinstance(
                    stmt.target, ast.Name
                ):
                    names.add(stmt.target.id)
                elif isinstance(
                    stmt,
                    (ast.If, ast.For, ast.While, ast.With, ast.AsyncFor, ast.AsyncWith),
                ):
                    visit(stmt.body)
                    visit(stmt.orelse)
                elif isinstance(stmt, ast.Try):
                    visit(stmt.body)
                    for handler in stmt.handlers:
                        visit(handler.body)
                    visit(stmt.orelse)
                    visit(stmt.finalbody)

        visit(tree.body)
        return names

    @staticmethod
    def collect_all_exports(tree: ast.AST) -> set[str]:
        """Names declared in a module's `__all__`, including
        `__all__ += (...)` appends (possibly inside `if`/`try` blocks)."""
        exports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
                    value = node.value
                    if isinstance(value, (ast.List, ast.Tuple)):
                        for elt in value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                exports.add(elt.value)
        return exports

    def get_public_names(self, tree: ast.AST) -> set[str]:
        """Names a `from mod import *` would import."""
        exports = self.collect_all_exports(tree)
        if exports:
            return exports
        return {
            n for n in self.collect_module_level_names(tree) if not n.startswith("_")
        }

    def _module_name(self, path: Path) -> str:
        rel = path.relative_to(self.root)
        parts = list(rel.parts)
        if path.name == "__init__.py":
            parts.pop()
        elif parts:
            parts[-1] = path.stem
        return ".".join(parts)

    def resolve_relative_module(
        self, from_file: Path, module: str | None, level: int
    ) -> str:
        """Resolve `from .mod import *` to an absolute module name."""
        parts = list(from_file.relative_to(self.root).parts)
        base = parts[:-1]
        # level=1: current package; level=2: parent package, etc.
        base = base[: len(base) - (level - 1)]
        if module:
            base += module.split(".")
        return ".".join(base)

    def collect_cross_file_imports(self, files: list[Path]) -> set[str]:  # noqa: C901
        """Names that form the project's cross-module surface.

        `from X import name`, names exposed by `from X import *`, and module
        names bound by `import X.Y`.
        """
        imported: set[str] = set()
        file_by_module = {self._module_name(f): f for f in files}

        for f, tree in self._python_trees(files):
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "*":
                            # Absolute and package star imports both
                            # expose the target's public names; `node.module`
                            # is None for `from . import *`.
                            if node.level > 0:
                                target = self.resolve_relative_module(
                                    f, node.module, node.level
                                )
                            else:
                                target = node.module
                            if target:
                                imported.add(target.split(".")[-1])
                                target_file = file_by_module.get(target)
                                if target_file:
                                    target_tree = self._parse(target_file)
                                    if target_tree is not None:
                                        imported |= self.get_public_names(target_tree)
                        else:
                            imported.add(alias.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imported.add(alias.name.split(".")[0])
        return imported

    def collect_cross_file_keywords(self, files: list[Path]) -> set[str]:
        """Argument names passed as keywords anywhere in the project."""
        keywords: set[str] = set()
        for _f, tree in self._python_trees(files):
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg:
                            keywords.add(kw.arg)
        return keywords

    def collect_cross_file_attributes(self, files: list[Path]) -> set[str]:
        """Every attribute name accessed as `X.attr`, chained included.

        Attribute access is never renamed, so definitions reachable through
        one must keep their names. Conservative by design.
        """
        attrs: set[str] = set()
        for _f, tree in self._python_trees(files):
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    attrs.add(node.attr)
        return attrs

    def collect_obfuscatable_methods(self, files: list[Path]) -> set[str]:  # noqa: C901
        """Methods safe to rename: every `X.method` access has a known
        receiver (`self` or the class name); unknown receivers block it."""
        class_methods: dict[str, set[str]] = {}
        trees: list[ast.AST] = []
        for _f, tree in self._python_trees(files):
            trees.append(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = {
                        stmt.name
                        for stmt in node.body
                        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                    }
                    if methods:
                        class_methods[node.name] = methods

        blocked: set[str] = set()
        for tree in trees:
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    receiver = node.value
                    safe = isinstance(receiver, ast.Name) and (
                        receiver.id == "self" or receiver.id in class_methods
                    )
                    if safe:
                        continue
                    # Chained receivers (`self.parser.add_argument`) and
                    # unknown objects block the method.
                    for methods in class_methods.values():
                        if node.attr in methods:
                            blocked.add(node.attr)

        all_methods: set[str] = set()
        for methods in class_methods.values():
            all_methods |= methods
        return all_methods - blocked

    # ----- C ------------------------------------------------------------

    def collect_cross_file_symbols(self, files: list[Path]) -> set[str]:
        """C identifiers shared by two or more files.

        They must keep their names everywhere so the project still links.
        """
        scanner = CObfuscator(MappingManager(), NameGenerator(), "scan")
        defined_per_file: dict[Path, set[str]] = {}
        all_ids_per_file: dict[Path, set[str]] = {}
        for f in files:
            if f.suffix.lower() not in SUPPORTED_EXTS or is_python_file(f):
                continue
            try:
                content = self._read_text(f)
            except (OSError, UnicodeDecodeError):
                continue
            defined_per_file[f] = scanner._scan_defined_symbols(content)
            all_ids_per_file[f] = {
                m.group("ident") for m in scanner._tokenize(content) if m.group("ident")
            }

        occurrences: dict[str, int] = {}
        for syms in all_ids_per_file.values():
            for sym in syms:
                occurrences[sym] = occurrences.get(sym, 0) + 1

        any_defined: set[str] = set()
        for syms in defined_per_file.values():
            any_defined |= syms

        return {
            sym
            for sym, count in occurrences.items()
            if count >= 2 and sym in any_defined
        }
