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
from typing import Optional, Union

from .c import CObfuscator
from .core import MappingManager, NameGenerator
from .encrypt import EncryptionManager
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
    output_file: Optional[Path] = None
    key_file: Optional[Path] = None
    password: Optional[str] = None
    seed: Optional[int] = None
    style: str = "similar"
    length: int = 16
    language: Language = Language.PYTHON
    stats: bool = False


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
        content = self._read_file(options.input_file)

        assert options.key_file is not None or options.command == Command.OBFUSCATE

        obfuscator: Union[PythonObfuscator, CObfuscator]
        if options.language == Language.PYTHON:
            obfuscator = PythonObfuscator(self.mm, self.gen, options.input_file.name)
            key_path = str(options.key_file) if options.key_file else None
            result = obfuscator.obfuscate(
                content, key_path, encryption_key=options.password
            )
        else:
            obfuscator = CObfuscator(self.mm, self.gen, options.input_file.name)
            result = obfuscator.obfuscate(content)

        assert options.output_file is not None
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
        content = self._read_file(options.input_file)

        if options.key_file:
            self._load_mapping(options.key_file)

        try:
            obfuscator: Union[PythonObfuscator, CObfuscator]
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
        self._write_file(options.output_file, result)
        self._print_success(f"Restored {options.input_file} -> {options.output_file}")
        if options.key_file:
            self._print_success(f"Key used: {options.key_file}")
        else:
            self._print_success("Key used: Embedded metadata")

    def _read_file(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:  # Catch file not found and other OS errors
            raise FileNotFound(
                f"❌ Error: Input file not found: {path}\n"
                f"💡 Hint: Check if the file path is correct or use an absolute path"
            )
        except PermissionError:
            raise FileNotFound(
                f"❌ Error: Permission denied: {path}\n"
                f"💡 Hint: Check file permissions or try running with appropriate rights"
            )
        except UnicodeDecodeError:
            raise FileNotFound(
                f"❌ Error: File encoding issue: {path}\n"
                f"💡 Hint: Ensure the file is a valid text file with UTF-8 encoding"
            )
        except Exception as e:
            raise FileNotFound(f"❌ Error: Failed to read {path}\n" f"💡 Details: {e}")

    def _write_file(self, path: Path, content: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except PermissionError:
            raise ObfuscationError(
                f"❌ Error: Permission denied when writing: {path}\n"
                f"💡 Hint: Check directory permissions or try a different output location"
            )
        except OSError as e:
            raise ObfuscationError(
                f"❌ Error: Failed to write {path}\n"
                f"💡 Details: {e}\n"
                f"💡 Hint: Ensure you have enough disk space and write permissions"
            )
        except Exception as e:
            raise ObfuscationError(
                f"❌ Error: Failed to write {path}\n" f"💡 Details: {e}"
            )

    def _load_mapping(self, key_file: Path) -> None:
        try:
            self.mm.load_mapping(key_file)
        except OSError:  # Catch file not found and other OS errors
            raise ObfuscationError(
                f"❌ Error: Key file not found: {key_file}\n"
                f"💡 Hint: Ensure the key file exists or try restoration without --key (using embedded metadata)"
            )
        except json.JSONDecodeError:
            raise ObfuscationError(
                f"❌ Error: Invalid key file format: {key_file}\n"
                f"💡 Hint: The key file may be corrupted. Try using embedded metadata instead."
            )
        except Exception as e:
            raise ObfuscationError(
                f"❌ Error: Failed to load key file {key_file}\n" f"💡 Details: {e}"
            )

    def _register_output_file(self, original_name: str, output_name: str) -> None:
        self.mm.register_file(original_name, output_name)

    def _print_success(self, message: str) -> None:
        print(f"OK {message}")

    def _collect_obfuscation_stats(
        self, original: str, obfuscated: str, obfuscator
    ) -> None:
        """Collect statistics about the obfuscation process"""
        import os

        # Count identifiers
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
                f"  Preserved identifiers: {self.stats_data['preserved_identifiers']} (imports/builtins)"
            )

        # Format file sizes
        orig_kb = self.stats_data["original_size"] / 1024
        obf_kb = self.stats_data["obfuscated_size"] / 1024
        print(f"  Original size: {orig_kb:.2f} KB")
        print(f"  Obfuscated size: {obf_kb:.2f} KB")
        print(
            f"  Size change: {self.stats_data['size_increase']:+d} bytes ({self.stats_data['size_percent']:+.1f}%)"
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
        import os

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
            f"Invalid command: {cmd}. "
            f"Use 'obfuscate' (or 'o') or 'restore' (or 'r')."
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
    ) -> Optional[Path]:

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
