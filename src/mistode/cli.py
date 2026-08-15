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

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .c import CObfuscator
from .core import MappingManager, NameGenerator
from .python import PythonObfuscator


class Command(Enum):
    OBFUSCATE = "obfuscate"
    RESTORE = "restore"


class Language(Enum):
    PYTHON = "python"
    C = "c"


class CLIError(Exception):
    """
    CLI Error Base Class
    """

    pass


class FileNotFound(CLIError):
    """Custom FileNotFound to avoid conflict with built-in FileNotFoundError"""

    def __init__(self, filepath: str = ""):
        self.filepath = filepath
        super().__init__(
            f"File not found: {filepath}" if filepath else "File not found"
        )


class ObfuscationError(CLIError):
    pass


@dataclass
class Options:
    command: Command
    input_file: Path
    output_file: Path | None = None
    key_file: Path | None = None
    password: str | None = None
    seed: int | None = None
    style: str = "similar"
    length: int = 16
    language: Language = Language.PYTHON
    stats: bool = False
    aggressive_methods: bool = False


class ObfuscationService:
    def __init__(self, options: Options):
        self.options = options
        self.mm = MappingManager()
        # If seed is not provided but password is, derive seed from password
        seed = options.seed
        if seed is None and options.password:
            # Deterministic seed from password for consistent obfuscation
            import hashlib

            seed = int.from_bytes(
                hashlib.sha256(options.password.encode()).digest()[:8], "big"
            )

        self.gen = NameGenerator(length=options.length, style=options.style, seed=seed)
        self.stats_data = {}

    def execute(self) -> None:
        if self.options.command == Command.OBFUSCATE:
            self._obfuscate()
        else:
            self._restore()

    def _obfuscate(self) -> None:
        options = self.options
        if options.input_file.is_dir():
            self._obfuscate_directory()
            return

        encoding = self._detect_encoding(options.input_file)
        content = self._read_file(options.input_file, encoding)

        obfuscator: PythonObfuscator | CObfuscator
        if options.language == Language.PYTHON:
            obfuscator = PythonObfuscator(self.mm, self.gen, options.input_file.name)
            key_path = str(options.key_file) if options.key_file else None
            try:
                result = obfuscator.obfuscate(
                    content,
                    key_path,
                    encryption_key=options.password,
                    source_encoding=encoding,
                )
            except SyntaxError as e:
                raise ObfuscationError(
                    f"❌ Error: Failed to parse {options.input_file}\n💡 Details: {e}"
                )
        else:
            obfuscator = CObfuscator(self.mm, self.gen, options.input_file.name)
            result = obfuscator.obfuscate(content, source_encoding=encoding)

        assert options.output_file is not None
        # The obfuscated file is always written as UTF-8 so it stays
        # executable/compilable; the original encoding is stored in the
        # metadata for bit-perfect restoration.
        self._write_file(options.output_file, result)
        self._register_output_file(options.input_file.name, options.output_file.name)

        # Collect statistics
        if options.stats:
            self._collect_obfuscation_stats(content, result, obfuscator)

        self._print_success(f"Obfuscated {options.input_file} -> {options.output_file}")
        if options.key_file:
            self.mm.save_mapping(options.key_file)
            self._print_success(f"Key saved to {options.key_file}")
        elif options.language == Language.C:
            # C now supports embedded metadata
            pass

        if options.stats:
            self._print_stats()

    def _restore(self) -> None:
        options = self.options
        if options.input_file.is_dir():
            self._restore_directory()
            return

        encoding = self._detect_encoding(options.input_file)
        content = self._read_file(options.input_file, encoding)

        if options.key_file:
            self._load_mapping(options.key_file)

        try:
            obfuscator: PythonObfuscator | CObfuscator
            if options.language == Language.PYTHON:
                obfuscator = PythonObfuscator(
                    self.mm, self.gen, options.input_file.name
                )
                key_path = str(options.key_file) if options.key_file else None
                result = obfuscator.restore(
                    key_path, content, encryption_key=options.password
                )
            else:
                obfuscator = CObfuscator(self.mm, self.gen, options.input_file.name)
                result = obfuscator.restore(content)
        except ValueError as e:
            raise ObfuscationError(str(e))

        assert options.output_file is not None
        # Restore in the original encoding (recorded in the embedded
        # metadata) for byte-identical output.
        restore_encoding = obfuscator.mm.source_encoding or encoding
        self._write_file(options.output_file, result, restore_encoding)
        self._print_success(f"Restored {options.input_file} -> {options.output_file}")
        if options.key_file:
            self._print_success(f"Key used: {options.key_file}")
        else:
            self._print_success("Key used: Embedded metadata")

    SUPPORTED_EXTS = {".py", ".c", ".h", ".cpp"}
    SKIP_DIRS = {
        # Build/artifact output directories (common across Python and C)
        "build",
        "dist",
        "bin",
        "obj",
        "out",
        "target",
        "CMakeFiles",
        "Debug",
        "Release",
        # Non-hidden virtualenv/package dirs
        "node_modules",
        "venv",
        "env",
        "__pycache__",
    }

    def _in_skipped_dir(self, path: Path, root: Path) -> bool:
        """True if any path component is hidden (dot-prefixed, covering
        .git/.venv/.idea/... ) or is a known build/artifact directory."""
        return any(
            part.startswith(".") or part in self.SKIP_DIRS
            for part in path.relative_to(root).parts
        )

    def _collect_source_files(self, directory: Path) -> list[Path]:
        """Recursively collect supported source files under a directory,
        skipping hidden, virtualenv, and build/artifact directories."""
        return sorted(
            p
            for p in directory.rglob("*")
            if p.is_file()
            and p.suffix.lower() in self.SUPPORTED_EXTS
            and not self._in_skipped_dir(p, directory)
        )

    def _language_for_file(self, path: Path) -> Language:
        return Language.PYTHON if path.suffix.lower() == ".py" else Language.C

    def _collect_module_level_names(self, tree: ast.AST) -> set[str]:  # noqa: C901
        """Collect definitions in module scope, including those nested in
        `if`/`try`/`with` blocks (still module scope), but not inside
        function or class bodies."""
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

    def _collect_all_exports(self, tree: ast.AST) -> set[str]:
        """Collect names declared in a module's `__all__`, including
        `__all__ += (...)` appends (possibly inside `if`/`try` blocks).
        These are the module's true public API."""
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

    def _get_public_names(self, tree: ast.AST) -> set[str]:
        """Names a `from mod import *` would import: the module's `__all__`
        if declared, otherwise its non-underscore module-level definitions."""
        exports = self._collect_all_exports(tree)
        if exports:
            return exports
        return {
            n for n in self._collect_module_level_names(tree) if not n.startswith("_")
        }

    def _collect_cross_file_imports(self, files: list[Path]) -> set[str]:  # noqa: C901
        """
        Python project mode: every name that is part of the project's
        cross-module surface and therefore must keep its original spelling:

        - `from X import name` bindings
        - star-import targets: the names `from X import *` would expose
          (X's `__all__`, or its public module-level definitions)
        - module names bound by `import X.Y` / star imports (e.g. `mod` in
          `mod.__all__`)

        Module-level names that are *not* exported or referenced stay
        obfuscatable.
        """
        imported: set[str] = set()

        def module_name(path: Path) -> str:
            root = (
                self.options.input_file
                if self.options.input_file.is_dir()
                else self.options.input_file.parent
            )
            rel = path.relative_to(root)
            parts = list(rel.parts)
            if path.name == "__init__.py":
                parts.pop()
            elif parts:
                parts[-1] = path.stem
            return ".".join(parts)

        file_by_module = {module_name(f): f for f in files}

        for f in files:
            if self._language_for_file(f) != Language.PYTHON:
                continue
            try:
                encoding = self._detect_encoding(f)
                tree = ast.parse(self._read_file(f, encoding))
            except OSError, UnicodeDecodeError, SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "*":
                            # `from .mod import *` binds `mod` itself and
                            # exposes mod's public names
                            if node.module:
                                mod = node.module.split(".")[-1]
                                imported.add(mod)
                                # Resolve relative star-import target
                                if node.level > 0:
                                    target = self._resolve_relative_module(
                                        f, node.module, node.level
                                    )
                                    target_file = file_by_module.get(target)
                                    if target_file:
                                        try:
                                            target_tree = ast.parse(
                                                self._read_file(
                                                    target_file,
                                                    self._detect_encoding(target_file),
                                                )
                                            )
                                            imported |= self._get_public_names(
                                                target_tree
                                            )
                                        except OSError, UnicodeDecodeError, SyntaxError:
                                            pass
                        else:
                            imported.add(alias.name)
            # `import X.Y` binds the top-level name X; `from X import *`
            # binds X as well (used as `X.__all__`)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported.add(alias.name.split(".")[0])
        return imported

    def _resolve_relative_module(
        self, from_file: Path, module: str | None, level: int
    ) -> str:
        """
        Resolve a relative import (`from .mod import *`, `from ..pkg.mod
        import *`) to an absolute module name within the project.
        """
        rel = from_file.relative_to(self.options.input_file)
        parts = list(rel.parts)
        if from_file.name == "__init__.py":
            base = parts[:-1]
        else:
            base = parts[:-1]
        # level=1: current package; level=2: parent package, etc.
        base = base[: len(base) - (level - 1)]
        if module:
            base += module.split(".")
        return ".".join(base)

    def _collect_obfuscatable_methods(self, files: list[Path]) -> set[str]:  # noqa: C901
        """
        Python project mode: class method names that may be renamed.

        A method is only safe to rename if every `X.method` attribute
        access across the project has a known receiver: `self` (inside
        the class) or the class name itself. Any access on a variable of
        unknown type blocks the method.
        """
        class_methods: dict[str, set[str]] = {}
        trees: list[ast.AST] = []
        for f in files:
            if self._language_for_file(f) != Language.PYTHON:
                continue
            try:
                encoding = self._detect_encoding(f)
                tree = ast.parse(self._read_file(f, encoding))
            except OSError, UnicodeDecodeError, SyntaxError:
                continue
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
                    # Safe receivers: `self` or a known class name directly
                    safe = isinstance(receiver, ast.Name) and (
                        receiver.id == "self" or receiver.id in class_methods
                    )
                    if safe:
                        continue
                    # Anything else - including chained receivers such as
                    # `self.parser.add_argument` - is an unknown object
                    for methods in class_methods.values():
                        if node.attr in methods:
                            blocked.add(node.attr)

        all_methods: set[str] = set()
        for methods in class_methods.values():
            all_methods |= methods
        return all_methods - blocked

    def _collect_cross_file_keywords(self, files: list[Path]) -> set[str]:
        """
        Python project mode: argument names passed as keyword arguments
        anywhere in the project. A function's parameter may be referenced
        as a keyword in a *different* file, so every such name must keep
        its original spelling across all files.
        """
        keywords: set[str] = set()
        for f in files:
            if self._language_for_file(f) != Language.PYTHON:
                continue
            try:
                encoding = self._detect_encoding(f)
                tree = ast.parse(self._read_file(f, encoding))
            except OSError, UnicodeDecodeError, SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg:
                            keywords.add(kw.arg)
        return keywords

    def _collect_cross_file_attributes(self, files: list[Path]) -> set[str]:
        """
        Python project mode: attribute names accessed as `X.attr` anywhere.
        Since attribute access is never renamed, any definition reachable
        via `module.attr` must keep its original name in every file.
        """
        attrs: set[str] = set()
        for f in files:
            if self._language_for_file(f) != Language.PYTHON:
                continue
            try:
                encoding = self._detect_encoding(f)
                tree = ast.parse(self._read_file(f, encoding))
            except OSError, UnicodeDecodeError, SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    attrs.add(node.attr)
        return attrs

    def _collect_cross_file_symbols(self, files: list[Path]) -> set[str]:
        """
        C project mode: identifiers *defined* in one file and appearing in
        at least two files (e.g. via a shared header). These are shared
        across compilation units and must keep their original names in
        every file so the project still links.
        """
        scanner = CObfuscator(self.mm, self.gen, "scan")
        defined_per_file: dict[Path, set[str]] = {}
        all_ids_per_file: dict[Path, set[str]] = {}
        for f in files:
            if self._language_for_file(f) != Language.C:
                continue
            try:
                encoding = self._detect_encoding(f)
                content = self._read_file(f, encoding)
            except OSError, UnicodeDecodeError:
                continue
            defined_per_file[f] = scanner._scan_defined_symbols(content)
            all_ids_per_file[f] = {
                m.group(3) for m in scanner._tokenize(content) if m.group(3)
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

    def _obfuscate_directory(self) -> None:
        options = self.options
        files = self._collect_source_files(options.input_file)
        if not files:
            raise ObfuscationError(
                f"❌ Error: No supported source files (.py/.c/.h/.cpp) "
                f"found in {options.input_file}"
            )

        out_dir = options.output_file
        assert out_dir is not None

        # Cross-file analysis so references between files stay intact
        python_imports = self._collect_cross_file_imports(files)
        python_keywords = self._collect_cross_file_keywords(files)
        python_attrs = self._collect_cross_file_attributes(files)
        # Method renaming is opt-in: it is only provably safe for
        # self-contained code, since external callers of a library's
        # methods are invisible to static analysis.
        python_methods = (
            self._collect_obfuscatable_methods(files)
            if options.aggressive_methods
            else set()
        )
        c_shared = self._collect_cross_file_symbols(files)

        for f in files:
            rel = f.relative_to(options.input_file)
            out = out_dir / rel
            encoding = self._detect_encoding(f)
            content = self._read_file(f, encoding)

            if self._language_for_file(f) == Language.PYTHON:
                obfuscator = PythonObfuscator(
                    self.mm,
                    self.gen,
                    f.name,
                    obfuscatable_methods=python_methods,
                )
                # Names imported elsewhere / used as keywords / accessed
                # as attributes elsewhere in the project must not change.
                # Methods proven obfuscatable are exempt from the attribute
                # preservation (their self/class call sites are renamed in
                # tandem).
                obfuscator.ignore_set.update(python_imports)
                obfuscator.ignore_set.update(python_attrs - python_methods)
                obfuscator.preserved_keywords.update(python_keywords)
                try:
                    result = obfuscator.obfuscate(
                        content,
                        encryption_key=options.password,
                        source_encoding=encoding,
                    )
                except SyntaxError as e:
                    raise ObfuscationError(
                        f"❌ Error: Failed to parse {f}\n💡 Details: {e}"
                    )
            else:
                obfuscator = CObfuscator(self.mm, self.gen, f.name)
                # Symbols shared across files must keep their names
                result = obfuscator.obfuscate(
                    content,
                    source_encoding=encoding,
                    extra_whitelisted=c_shared,
                )
            self._write_file(out, result)

        self._print_success(
            f"Obfuscated {options.input_file} -> {out_dir} ({len(files)} files)"
        )

    def _restore_directory(self) -> None:
        options = self.options
        files = self._collect_source_files(options.input_file)
        if not files:
            raise ObfuscationError(
                f"❌ Error: No source files found in {options.input_file}"
            )

        out_dir = options.output_file
        assert out_dir is not None

        for f in files:
            rel = f.relative_to(options.input_file)
            out = out_dir / rel
            encoding = self._detect_encoding(f)
            content = self._read_file(f, encoding)

            try:
                if self._language_for_file(f) == Language.PYTHON:
                    obfuscator = PythonObfuscator(self.mm, self.gen, f.name)
                    result = obfuscator.restore(
                        None, content, encryption_key=options.password
                    )
                else:
                    obfuscator = CObfuscator(self.mm, self.gen, f.name)
                    result = obfuscator.restore(content)
            except ValueError as e:
                raise ObfuscationError(str(e))

            restore_encoding = obfuscator.mm.source_encoding or encoding
            self._write_file(out, result, restore_encoding)

        self._print_success(
            f"Restored {options.input_file} -> {out_dir} ({len(files)} files)"
        )

    def _detect_encoding(self, path: Path) -> str:  # noqa: C901
        """
        Detect the file encoding by BOM and strict-decoding candidates.

        Order matters: UTF-8 first (superset checks would otherwise accept
        UTF-8 bytes as GB18030 and produce mojibake), then common CJK
        encodings, then UTF-16, with latin-1 as a never-failing fallback.
        """
        try:
            raw = path.read_bytes()
        except OSError:
            raise FileNotFound(
                f"❌ Error: Input file not found: {path}\n"
                f"💡 Hint: Check if the file path is correct or use an absolute path"
            )

        if raw.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if raw.startswith(b"\xff\xfe\x00\x00"):
            return "utf-32-le"
        if raw.startswith(b"\x00\x00\xfe\xff"):
            return "utf-32-be"
        if raw.startswith(b"\xff\xfe"):
            return "utf-16-le"
        if raw.startswith(b"\xfe\xff"):
            return "utf-16-be"

        # UTF-16/32 without a BOM pairs ASCII bytes with NUL bytes, which
        # would otherwise decode as valid (but wrong) UTF-8. Infer
        # endianness from whether NUL bytes sit on odd or even positions.
        if b"\x00" in raw:
            nul_even = raw[0::2].count(0)
            nul_odd = raw[1::2].count(0)
            if nul_odd > nul_even:
                return "utf-16-le"
            return "utf-16-be"

        for enc in ("utf-8", "gb18030", "big5", "shift_jis", "utf-16"):
            try:
                raw.decode(enc)
                return enc
            except UnicodeDecodeError:
                continue

        return "latin-1"

    def _read_file(self, path: Path, encoding: str = "utf-8") -> str:
        try:
            # newline="" keeps CRLF intact for bit-perfect restoration
            with open(path, "r", encoding=encoding, newline="") as f:
                return f.read()
        except OSError:  # Catch file not found and other OS errors
            raise FileNotFound(
                f"❌ Error: Input file not found: {path}\n"
                f"💡 Hint: Check if the file path is correct or use an absolute path"
            )
        except PermissionError:
            raise FileNotFound(
                f"❌ Error: Permission denied: {path}\n"
                f"💡 Hint: Check file permissions or try running "  # noqa: E501
                f"with appropriate rights"
            )
        except UnicodeDecodeError:
            raise FileNotFound(
                f"❌ Error: File encoding issue: {path}\n"
                f"💡 Hint: Ensure the file is a valid text file (UTF-8, GBK, "  # noqa: E501
                f"Big5, Shift_JIS, or UTF-16)"
            )
        except Exception as e:
            raise FileNotFound(f"❌ Error: Failed to read {path}\n💡 Details: {e}")

    def _write_file(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # newline="" prevents newline translation on Windows
            with open(path, "w", encoding=encoding, newline="") as f:
                f.write(content)
        except PermissionError:
            raise ObfuscationError(
                f"❌ Error: Permission denied when writing: {path}\n"
                f"💡 Hint: Check directory permissions or try a "  # noqa: E501
                f"different output location"
            )
        except OSError as e:
            raise ObfuscationError(
                f"❌ Error: Failed to write {path}\n"
                f"💡 Details: {e}\n"
                f"💡 Hint: Ensure you have enough disk space and write permissions"
            )
        except Exception as e:
            raise ObfuscationError(f"❌ Error: Failed to write {path}\n💡 Details: {e}")

    def _load_mapping(self, key_file: Path) -> None:
        try:
            self.mm.load_mapping(key_file)
        except OSError:  # Catch file not found and other OS errors
            raise ObfuscationError(
                f"❌ Error: Key file not found: {key_file}\n"
                f"💡 Hint: Ensure the key file exists or try restoration "  # noqa: E501
                f"without --key (using embedded metadata)"
            )
        except json.JSONDecodeError:
            raise ObfuscationError(
                f"❌ Error: Invalid key file format: {key_file}\n"
                f"💡 Hint: The key file may be corrupted. Try using "  # noqa: E501
                f"embedded metadata instead."
            )
        except Exception as e:
            raise ObfuscationError(
                f"❌ Error: Failed to load key file {key_file}\n💡 Details: {e}"
            )

    def _register_output_file(self, original_name: str, output_name: str) -> None:
        self.mm.register_file(original_name, output_name)

    def _print_success(self, message: str) -> None:
        print(f"OK {message}")

    def _collect_obfuscation_stats(
        self, original: str, obfuscated: str, obfuscator
    ) -> None:
        """Collect statistics about the obfuscation process"""

        # Count identifiers
        # PythonObfuscator tracks its own mapping in mapping_records,
        # while CObfuscator uses MappingManager.mapping directly.
        if hasattr(obfuscator, "mapping_records"):
            total_identifiers = len(obfuscator.mapping_records["identifier_mapping"])
        else:
            total_identifiers = len(self.mm.mapping)
        preserved_count = 0

        # Try to count preserved identifiers (imports/builtins)
        if hasattr(obfuscator, "import_analyzer"):
            preserved_count = len(obfuscator.import_analyzer.imported_names) + len(
                obfuscator.import_analyzer.module_aliases
            )

        # Calculate file sizes
        original_size = len(original.encode("utf-8"))
        obfuscated_size = len(obfuscated.encode("utf-8"))
        size_increase = obfuscated_size - original_size
        size_percent = (size_increase / original_size * 100) if original_size > 0 else 0

        self.stats_data = {
            "total_identifiers": total_identifiers,
            "preserved_identifiers": preserved_count,
            "original_size": original_size,
            "obfuscated_size": obfuscated_size,
            "size_increase": size_increase,
            "size_percent": size_percent,
            "has_key": self.options.key_file is not None,
        }

    def _print_stats(self) -> None:
        """Print collected statistics"""
        if not self.stats_data:
            return

        print("\n=== Obfuscation Statistics ===")
        print(f"  Identifiers obfuscated: {self.stats_data['total_identifiers']}")
        if self.stats_data["preserved_identifiers"] > 0:
            print(
                f"  Preserved identifiers: "  # noqa: E501
                f"{self.stats_data['preserved_identifiers']} (imports/builtins)"
            )

        # Format file sizes
        orig_kb = self.stats_data["original_size"] / 1024
        obf_kb = self.stats_data["obfuscated_size"] / 1024
        print(f"  Original size: {orig_kb:.2f} KB")
        print(f"  Obfuscated size: {obf_kb:.2f} KB")
        print(
            f"  Size change: {self.stats_data['size_increase']:+d} bytes "  # noqa: E501
            f"({self.stats_data['size_percent']:+.1f}%)"
        )

        # Restoration method
        if self.stats_data["has_key"]:
            print("  Restoration: Key file + Embedded metadata")
        else:
            print("  Restoration: Embedded metadata only")
        print("===============================")


class ArgumentParser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="Mistode Code Obfuscator",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self.parser.add_argument(
            "--version",
            "-v",
            action="version",
            version=self._get_version_string(),
        )
        self._setup_subparsers()

    def _get_version_string(self) -> str:
        from . import __version__

        return f"Mistode {__version__} (Python {sys.version.split()[0]})"

    def _load_config(self) -> dict:
        """Load configuration from pyproject.toml if it exists"""
        config = {}

        # Try to find and load pyproject.toml

        cwd = Path.cwd()

        # Check current directory and parent directories
        for parent in [cwd] + list(cwd.parents):
            config_file = parent / "pyproject.toml"
            if config_file.exists():
                try:
                    import tomllib

                    with open(config_file, "rb") as f:
                        data = tomllib.load(f)
                        # Look for [tool.mistode] section
                        if "tool" in data and "mistode" in data["tool"]:
                            config = data["tool"]["mistode"]
                except Exception:
                    # If config file is invalid, just skip it
                    pass
                break

        return config

    def _setup_subparsers(self) -> None:
        subparsers = self.parser.add_subparsers(
            dest="command", required=True, title="commands"
        )

        self._add_obfuscate_command(subparsers)
        self._add_restore_command(subparsers)

    def _add_obfuscate_command(self, subparsers) -> None:
        obf = subparsers.add_parser(
            "obfuscate", aliases=["o", "obf"], help="Obfuscate a source file"
        )
        obf.add_argument("input_file", help="Path to input source file")
        obf.add_argument("--out", "-o", help="Path to output file")
        obf.add_argument("--key", "-k", help="Path to key file (JSON map)")
        obf.add_argument(
            "--password", "-p", "--pwd", help="Password for encryption/decryption"
        )
        obf.add_argument("--seed", "-s", type=int, help="Random seed")
        obf.add_argument(
            "--style",
            choices=["similar", "random"],
            default=None,
            help="Naming style: similar or random (default: similar)",
        )
        obf.add_argument(
            "--length",
            "-l",
            type=int,
            choices=range(8, 33),
            metavar="8-32",
            default=None,
            help="Token length (8-32, default: 16)",
        )
        obf.add_argument(
            "--stats",
            action="store_true",
            help="Display obfuscation statistics",
        )
        obf.add_argument(
            "--aggressive-methods",
            action="store_true",
            help=(
                "Rename class methods whose receivers are provably local "
                "(self/class name). Only safe for self-contained code; "
                "libraries may be called by external code through method "
                "names and will break."
            ),
        )

    def _add_restore_command(self, subparsers) -> None:
        res = subparsers.add_parser(
            "restore", aliases=["r", "res"], help="Restore an obfuscated file"
        )
        res.add_argument("input_file", help="Path to obfuscated file")
        res.add_argument("--out", "-o", help="Path to output file")
        res.add_argument("--key", "-k", help="Path to key file (JSON map)")
        res.add_argument(
            "--password", "-p", "--pwd", help="Password for encryption/decryption"
        )
        res.add_argument(
            "--stats",
            action="store_true",
            help="Display restoration statistics",
        )

    def parse(self, args=None) -> Options:
        raw = self.parser.parse_args(args)
        return self._convert_to_options(raw)

    def _convert_to_options(self, raw) -> Options:
        # Load config file defaults
        config = self._load_config()

        cmd = self._normalize_command(raw.command)
        input_path = Path(raw.input_file)
        ext = input_path.suffix.lower()

        language = self._detect_language(ext)
        output_file = self._resolve_output_path(input_path, raw.out, cmd)
        key_file = self._resolve_key_path(input_path, raw.key, cmd, language)

        return Options(
            command=cmd,
            input_file=input_path,
            output_file=output_file,
            key_file=key_file,
            seed=(
                raw.seed
                if hasattr(raw, "seed") and raw.seed is not None
                else config.get("seed", None)
            ),
            password=(
                raw.password
                if hasattr(raw, "password")
                else config.get("password", None)
            ),
            style=(
                raw.style
                if hasattr(raw, "style") and raw.style is not None
                else config.get("style", "similar")
            ),
            length=(
                raw.length
                if hasattr(raw, "length") and raw.length is not None
                else config.get("length", 16)
            ),
            language=language,
            stats=(
                raw.stats
                if hasattr(raw, "stats") and raw.stats
                else config.get("stats", False)
            ),
            aggressive_methods=(
                raw.aggressive_methods
                if hasattr(raw, "aggressive_methods") and raw.aggressive_methods
                else False
            ),
        )

    def _normalize_command(self, cmd: str) -> Command:
        aliases = {
            "o": Command.OBFUSCATE,
            "obf": Command.OBFUSCATE,
            "obfuscate": Command.OBFUSCATE,
            "r": Command.RESTORE,
            "res": Command.RESTORE,
            "restore": Command.RESTORE,
        }
        if cmd in aliases:
            return aliases[cmd]
        raise CLIError(
            f"Invalid command: {cmd}. Use 'obfuscate' (or 'o') or 'restore' (or 'r')."
        )

    def _detect_language(self, ext: str) -> Language:
        if ext in [".py"]:
            return Language.PYTHON
        if ext in [".c", ".h", ".cpp"]:
            return Language.C
        return Language.PYTHON

    def _resolve_output_path(self, input_path: Path, out: str, cmd: Command) -> Path:
        if out:
            return Path(out)

        # Directory (project) mode: mirror the tree, keep original filenames
        if input_path.is_dir():
            if cmd == Command.OBFUSCATE:
                return Path(str(input_path) + ".obf")
            name = str(input_path)
            if name.endswith(".obf"):
                name = name[:-4]
            return Path(name + ".res")

        parent = input_path.parent
        stem = input_path.stem

        if cmd == Command.OBFUSCATE:
            suffix = ".obf" + input_path.suffix
            return parent / f"{stem}{suffix}"
        else:
            if stem.endswith(".obf"):
                stem = stem[:-4]
            return parent / f"{stem}.res{input_path.suffix}"

    def _resolve_key_path(
        self, input_path: Path, key: str, cmd: Command, language: Language
    ) -> Path | None:

        if key:
            return Path(key)

        if cmd == Command.RESTORE:
            if input_path.stem.endswith(".obf"):
                original_stem = input_path.stem[:-4]
                fallback = input_path.parent / f"{original_stem}.map.json"
                if fallback.exists():
                    return fallback
            # For restore, if no explicit key and no implicit key file found,
            # return None. The restoration might succeed with embedded metadata
            return None

        if cmd == Command.OBFUSCATE and language == Language.C:
            # Reverted: C now supports embedded metadata, so no keyed enforcement needed
            return None

        # For obfuscate, we only save key if explicitly requested
        return None


def run() -> None:
    arg_parser = ArgumentParser()

    try:
        options = arg_parser.parse()
    except SystemExit:
        sys.exit(1)

    service = ObfuscationService(options)

    try:
        service.execute()
    except FileNotFound as e:
        print(f"{e}")
        sys.exit(1)
    except ObfuscationError as e:
        print(f"{e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)


main = run


if __name__ == "__main__":
    run()
