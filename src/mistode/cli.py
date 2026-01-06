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
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Union

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


class FileNotFoundError(CLIError):
    pass


class ObfuscationError(CLIError):
    pass


@dataclass
class Options:
    command: Command
    input_file: Path
    output_file: Optional[Path] = None
    key_file: Optional[Path] = None
    seed: Optional[int] = None
    style: str = "similar"
    length: int = 16
    language: Language = Language.PYTHON


class ObfuscationService:
    def __init__(self, options: Options):
        self.options = options
        self.mm = MappingManager()
        self.gen = NameGenerator(
            length=options.length, style=options.style, seed=options.seed
        )

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
            result = obfuscator.obfuscate(content, key_path)  # type: ignore
        else:
            obfuscator = CObfuscator(self.mm, self.gen, options.input_file.name)
            result = obfuscator.obfuscate(content)

        assert options.output_file is not None
        self._write_file(options.output_file, result)
        self._register_output_file(options.input_file.name, options.output_file.name)

        self._print_success(f"Obfuscated {options.input_file} -> {options.output_file}")
        if options.key_file:
            self.mm.save_mapping(options.key_file)
            self._print_success(f"Key saved to {options.key_file}")
        elif options.language == Language.C:
            # C now supports embedded metadata
            pass

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
                result = obfuscator.restore(key_path, content)  # type: ignore
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
        except FileNotFoundError:
            raise FileNotFoundError(f"Input file not found: {path}")
        except PermissionError:
            raise FileNotFoundError(f"Permission denied: {path}")
        except Exception as e:
            raise FileNotFoundError(f"Failed to read {path}: {e}")

    def _write_file(self, path: Path, content: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except PermissionError:
            raise ObfuscationError(f"Permission denied: {path}")
        except Exception as e:
            raise ObfuscationError(f"Failed to write {path}: {e}")

    def _load_mapping(self, key_file: Path) -> None:
        try:
            self.mm.load_mapping(key_file)
        except Exception as e:
            msg = f"Failed to load key file {key_file}: {e}"
            raise ObfuscationError(msg)

    def _register_output_file(self, original_name: str, output_name: str) -> None:
        self.mm.register_file(original_name, output_name)

    def _print_success(self, message: str) -> None:
        print(f"OK {message}")


class ArgumentParser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="Mistode Code Obfuscator",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self._setup_subparsers()

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
        obf.add_argument("--key", "-k", help="Path to key file")
        obf.add_argument("--seed", "-s", type=int, help="Random seed")
        obf.add_argument(
            "--style",
            choices=["similar", "random"],
            default="similar",
            help="Naming style: similar or random",
        )
        obf.add_argument(
            "--length",
            "-l",
            type=int,
            choices=range(8, 33),
            metavar="8-32",
            default=16,
            help="Token length (8-32, default: 16)",
        )

    def _add_restore_command(self, subparsers) -> None:
        res = subparsers.add_parser(
            "restore", aliases=["r", "res"], help="Restore an obfuscated file"
        )
        res.add_argument("input_file", help="Path to obfuscated file")
        res.add_argument("--out", "-o", help="Path to output file")
        res.add_argument("--key", "-k", help="Path to key file")

    def parse(self, args=None) -> Options:
        raw = self.parser.parse_args(args)
        return self._convert_to_options(raw)

    def _convert_to_options(self, raw) -> Options:
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
            seed=getattr(raw, "seed", None),
            style=getattr(raw, "style", "similar"),
            length=getattr(raw, "length", 16),
            language=language,
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
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ObfuscationError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)


main = run


if __name__ == "__main__":
    run()
