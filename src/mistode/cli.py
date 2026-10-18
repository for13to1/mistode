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
import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .c import CObfuscator
from .core import MappingManager, NameGenerator
from .encrypt import derive_seed
from .project import (
    ProjectAnalyzer,
    collect_asset_files,
    collect_source_files,
    copy_assets,
    is_python_file,
)
from .python import PythonObfuscator


class Command(Enum):
    OBFUSCATE = "obfuscate"
    RESTORE = "restore"


class Language(Enum):
    PYTHON = "python"
    C = "c"


class CLIError(Exception):
    """Base class for errors reported without a traceback."""

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
    cipher: str | None = None
    seed: int | None = None
    style: str = "similar"
    length: int = 16
    language: Language = Language.PYTHON
    stats: bool = False
    aggressive_methods: bool = False
    assets: str = "copy"  # copy | skip | list
    assets_skip_secrets: bool = False


class ObfuscationService:
    def __init__(self, options: Options):
        self.options = options
        self.mm = MappingManager()
        # Without --seed, the password also seeds identifier generation so
        # repeated runs produce the same output.
        seed = options.seed
        if seed is None and options.password:
            seed = derive_seed(options.password)

        self.gen = NameGenerator(length=options.length, style=options.style, seed=seed)
        self.stats_data = {}

    def execute(self) -> None:
        if (
            self.options.command == Command.OBFUSCATE
            and self.options.cipher not in (None, "none")
            and not self.options.password
        ):
            raise ObfuscationError(
                f"❌ Error: --cipher {self.options.cipher} requires --password.\n"
                "💡 Hint: add --password, or use --cipher none for plain payloads."
            )
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
            # Method renaming is opt-in and uses the same receiver proof
            # as directory mode.
            methods = (
                self._analyzer().collect_obfuscatable_methods([options.input_file])
                if options.aggressive_methods
                else set()
            )
            obfuscator = PythonObfuscator(
                self.mm,
                self.gen,
                options.input_file.name,
                obfuscatable_methods=methods,
            )
            key_path = str(options.key_file) if options.key_file else None
            try:
                result = obfuscator.obfuscate(
                    content,
                    key_path,
                    encryption_key=options.password,
                    source_encoding=encoding,
                    cipher=options.cipher,
                )
            except SyntaxError as e:
                raise ObfuscationError(
                    f"❌ Error: Failed to parse {options.input_file}\n💡 Details: {e}"
                )
        else:
            obfuscator = CObfuscator(self.mm, self.gen, options.input_file.name)
            try:
                result = obfuscator.obfuscate(
                    content,
                    source_encoding=encoding,
                    source_dir=options.input_file.parent,
                    encryption_key=options.password,
                    cipher=options.cipher,
                )
            except ValueError as e:
                raise ObfuscationError(f"❌ Error: {e}")

        assert options.output_file is not None
        # Output is always UTF-8 so it runs anywhere; the original encoding
        # travels in the metadata for byte-identical restoration.
        self._write_file(options.output_file, result)

        if options.stats:
            self._collect_obfuscation_stats(content, result, obfuscator)

        self._print_success(f"Obfuscated {options.input_file} -> {options.output_file}")
        if options.key_file:
            # Python already wrote it; self.mm would be empty.
            if options.language == Language.C:
                self.mm.save_mapping(options.key_file)
            self._print_success(f"Key saved to {options.key_file}")

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
                    key_path,
                    content,
                    encryption_key=options.password,
                    cipher=options.cipher,
                )
            else:
                obfuscator = CObfuscator(self.mm, self.gen, options.input_file.name)
                result = obfuscator.restore(
                    content,
                    encryption_key=options.password,
                    cipher=options.cipher,
                )
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

    def _read_text(self, path: Path) -> str:
        return self._read_file(path, self._detect_encoding(path))

    def _analyzer(self) -> ProjectAnalyzer:
        root = (
            self.options.input_file
            if self.options.input_file.is_dir()
            else self.options.input_file.parent
        )
        return ProjectAnalyzer(root, self._read_text)

    def _handle_assets(self, out_dir: Path) -> None:
        """Copy (or report) non-source files so the obfuscated tree stays a
        runnable, self-contained deliverable."""
        mode = self.options.assets
        if mode == "skip":
            return

        source_dir = self.options.input_file
        skip_secrets = self.options.assets_skip_secrets
        if mode == "list":
            assets = collect_asset_files(source_dir, skip_secrets)
            for p in assets:
                print(f"asset: {p.relative_to(source_dir)}")
            print(f"({len(assets)} asset file(s); not copied in --assets list mode)")
            return

        copied = copy_assets(source_dir, out_dir, skip_secrets)
        if copied:
            self._print_success(f"Copied {copied} non-source asset file(s)")

    def _obfuscate_directory(self) -> None:
        options = self.options
        files = collect_source_files(options.input_file)
        if not files:
            raise ObfuscationError(
                f"❌ Error: No supported source files (.py/.c/.h/.cpp) "
                f"found in {options.input_file}"
            )

        out_dir = options.output_file
        assert out_dir is not None

        analyzer = self._analyzer()
        # Preserve everything that is referenced across files.
        python_imports = analyzer.collect_cross_file_imports(files)
        python_keywords = analyzer.collect_cross_file_keywords(files)
        python_attrs = analyzer.collect_cross_file_attributes(files)
        # Method renaming is opt-in: it is only provably safe for
        # self-contained code, since external callers of a library's
        # methods are invisible to static analysis.
        python_methods = (
            analyzer.collect_obfuscatable_methods(files)
            if options.aggressive_methods
            else set()
        )
        c_shared = analyzer.collect_cross_file_symbols(files)

        for f in files:
            rel = f.relative_to(options.input_file)
            out = out_dir / rel
            encoding = self._detect_encoding(f)
            content = self._read_file(f, encoding)

            if is_python_file(f):
                obfuscator = PythonObfuscator(
                    self.mm,
                    self.gen,
                    f.name,
                    obfuscatable_methods=python_methods,
                )
                # Cross-module names must keep their spelling; provably
                # local methods are exempt because their call sites are
                # renamed together.
                obfuscator.ignore_set.update(python_imports)
                obfuscator.ignore_set.update(python_attrs - python_methods)
                obfuscator.preserved_keywords.update(python_keywords)
                try:
                    result = obfuscator.obfuscate(
                        content,
                        encryption_key=options.password,
                        source_encoding=encoding,
                        cipher=options.cipher,
                    )
                except SyntaxError as e:
                    raise ObfuscationError(
                        f"❌ Error: Failed to parse {f}\n💡 Details: {e}"
                    )
                # Fold the per-file mapping into MappingManager so a
                # project-wide key can be written once at the end.
                self.mm.mapping.update(obfuscator.identifier_mapping)
            else:
                obfuscator = CObfuscator(self.mm, self.gen, f.name)
                # Symbols shared across files must keep their names
                try:
                    result = obfuscator.obfuscate(
                        content,
                        source_encoding=encoding,
                        extra_whitelisted=c_shared,
                        source_dir=f.parent,
                        encryption_key=options.password,
                        cipher=options.cipher,
                    )
                except ValueError as e:
                    raise ObfuscationError(f"❌ Error: {e}")
            self._write_file(out, result)

        self._handle_assets(out_dir)

        if options.key_file:
            self.mm.save_mapping(options.key_file)
            self._print_success(f"Key saved to {options.key_file}")

        self._print_success(
            f"Obfuscated {options.input_file} -> {out_dir} ({len(files)} files)"
        )

    def _restore_directory(self) -> None:
        options = self.options
        files = collect_source_files(options.input_file)
        if not files:
            raise ObfuscationError(
                f"❌ Error: No source files found in {options.input_file}"
            )

        out_dir = options.output_file
        assert out_dir is not None

        if options.key_file:
            raise ObfuscationError(
                "❌ Error: --key is not supported in project (directory) mode.\n"
                "💡 Hint: restore from embedded metadata, or restore files "
                "individually with their key."
            )

        for f in files:
            rel = f.relative_to(options.input_file)
            out = out_dir / rel
            encoding = self._detect_encoding(f)
            content = self._read_file(f, encoding)

            try:
                if is_python_file(f):
                    obfuscator = PythonObfuscator(self.mm, self.gen, f.name)
                    result = obfuscator.restore(
                        None,
                        content,
                        encryption_key=options.password,
                        cipher=options.cipher,
                    )
                else:
                    obfuscator = CObfuscator(self.mm, self.gen, f.name)
                    result = obfuscator.restore(
                        content,
                        encryption_key=options.password,
                        cipher=options.cipher,
                    )
            except ValueError as e:
                raise ObfuscationError(str(e))

            restore_encoding = obfuscator.mm.source_encoding or encoding
            self._write_file(out, result, restore_encoding)

        # Assets were mirrored into the obfuscated tree; bring them back so
        # the restored project is complete again.
        self._handle_assets(out_dir)

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

    def _print_success(self, message: str) -> None:
        print(f"OK {message}")

    def _collect_obfuscation_stats(
        self, original: str, obfuscated: str, obfuscator
    ) -> None:
        """Collect statistics about the obfuscation process"""

        # PythonObfuscator keeps its mapping on the instance;
        # CObfuscator uses MappingManager directly.
        if isinstance(obfuscator, PythonObfuscator):
            total_identifiers = len(obfuscator.identifier_mapping)
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
                    # Unreadable or malformed config is ignored.
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
            "--cipher",
            choices=["none", "stream"],
            default=None,
            help=(
                "Payload cipher used when a password is given: 'stream' "
                "(default, authenticated) or 'none'. Without --password "
                "payloads are always plain base64."
            ),
        )
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

        obf.add_argument(
            "--assets",
            choices=["copy", "skip", "list"],
            default=None,
            help=(
                "Project mode: whether to copy non-source files (templates, "
                "data, configs). copy (default) includes them so the result "
                "stays runnable; skip ignores them; list only reports what "
                "would be copied."
            ),
        )
        obf.add_argument(
            "--assets-skip-secrets",
            action="store_true",
            help=(
                "Skip credential-looking files (.env, *.pem, *.key...) when "
                "copying; they are included by default."
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
        res.add_argument(
            "--cipher",
            choices=["none", "stream"],
            default=None,
            help="Payload cipher (must match the one used to obfuscate)",
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
        key_file = self._resolve_key_path(input_path, raw.key, cmd)

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
            cipher=(
                raw.cipher
                if hasattr(raw, "cipher") and raw.cipher is not None
                else config.get("cipher")
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
            assets=(
                raw.assets
                if hasattr(raw, "assets") and raw.assets is not None
                else config.get("assets", "copy")
            ),
            assets_skip_secrets=(
                True
                if getattr(raw, "assets_skip_secrets", False)
                else config.get("assets_skip_secrets", False)
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
        self, input_path: Path, key: str, cmd: Command
    ) -> Path | None:

        if key:
            return Path(key)

        if cmd == Command.RESTORE:
            if input_path.stem.endswith(".obf"):
                original_stem = input_path.stem[:-4]
                fallback = input_path.parent / f"{original_stem}.map.json"
                if fallback.exists():
                    return fallback
            # No key file: restoration may still succeed from embedded
            # metadata.
            return None

        # Obfuscation writes a key only when explicitly requested.
        return None


def run() -> None:
    arg_parser = ArgumentParser()

    try:
        options = arg_parser.parse()
    except SystemExit as e:
        # argparse exits 0 for --help/--version and 2 for usage errors;
        # only forward its code instead of forcing a failure exit.
        sys.exit(e.code if isinstance(e.code, int) else 1)

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
