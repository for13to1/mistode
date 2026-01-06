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

"""CLI Unit Tests"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mistode.cli import (
    ArgumentParser,
    CLIError,
    Command,
    FileNotFoundError,
    Language,
    ObfuscationError,
    ObfuscationService,
    Options,
)


class TestOptions:
    """
    Test Options Data Class
    """

    def test_options_creation(self):
        """
        Test creating Options object
        """
        options = Options(
            command=Command.OBFUSCATE,
            input_file=Path("test.py"),
            output_file=Path("test.obf.py"),
            key_file=Path("test.map.json"),
            seed=123,
            style="random",
            length=12,
            language=Language.PYTHON,
        )
        assert options.command == Command.OBFUSCATE
        assert options.input_file == Path("test.py")
        assert options.output_file == Path("test.obf.py")
        assert options.key_file == Path("test.map.json")
        assert options.seed == 123
        assert options.style == "random"
        assert options.length == 12
        assert options.language == Language.PYTHON

    def test_options_defaults(self):
        """
        Test Options defaults
        """
        options = Options(
            command=Command.OBFUSCATE,
            input_file=Path("test.py"),
        )
        assert options.output_file is None
        assert options.key_file is None
        assert options.seed is None
        assert options.style == "similar"
        assert options.length == 16
        assert options.language == Language.PYTHON


class TestObfuscationService:
    """
    Test ObfuscationService Class
    """

    def test_service_initialization(self):
        """
        Test service initialization
        """
        options = Options(
            command=Command.OBFUSCATE,
            input_file=Path("test.py"),
            output_file=Path("test.obf.py"),
            key_file=Path("test.map.json"),
        )
        service = ObfuscationService(options)
        assert service.options == options
        assert service.mm is not None
        assert service.gen is not None

    def test_read_file_success(self):
        """
        Test successful file reading
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("test content")
            test_file = f.name

        try:
            options = Options(
                command=Command.OBFUSCATE,
                input_file=Path(test_file),
                output_file=Path("test.obf.py"),
                key_file=Path("test.map.json"),
            )
            service = ObfuscationService(options)
            content = service._read_file(Path(test_file))
            assert content == "test content"
        finally:
            Path(test_file).unlink()

    def test_read_file_not_found(self):
        """
        Test reading nonexistent file
        """
        options = Options(
            command=Command.OBFUSCATE,
            input_file=Path("nonexistent.py"),
            output_file=Path("test.obf.py"),
            key_file=Path("test.map.json"),
        )
        service = ObfuscationService(options)
        with pytest.raises(FileNotFoundError):
            service._read_file(Path("nonexistent.py"))

    def test_write_file_success(self):
        """
        Test successful file writing
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            test_file = f.name

        try:
            options = Options(
                command=Command.OBFUSCATE,
                input_file=Path("test.py"),
                output_file=Path(test_file),
                key_file=Path("test.map.json"),
            )
            service = ObfuscationService(options)
            service._write_file(Path(test_file), "test content")
            assert Path(test_file).read_text() == "test content"
        finally:
            Path(test_file).unlink()

    def test_write_file_creates_directory(self):
        """
        Test creating directory when writing file
        """
        test_file = Path(tempfile.gettempdir()) / "test_dir" / "test.py"

        try:
            options = Options(
                command=Command.OBFUSCATE,
                input_file=Path("test.py"),
                output_file=test_file,
                key_file=Path("test.map.json"),
            )
            service = ObfuscationService(options)
            service._write_file(test_file, "test content")
            assert test_file.exists()
            assert test_file.read_text() == "test content"
        finally:
            if test_file.exists():
                test_file.unlink()
                test_file.parent.rmdir()

    def test_register_output_file(self):
        """
        Test registering output file
        """
        options = Options(
            command=Command.OBFUSCATE,
            input_file=Path("test.py"),
            output_file=Path("test.obf.py"),
            key_file=Path("test.map.json"),
        )
        service = ObfuscationService(options)
        service._register_output_file("test.py", "test.obf.py")
        assert "test.obf.py" in service.mm.file_mapping

    def test_print_success(self):
        """
        Test printing success message
        """
        options = Options(
            command=Command.OBFUSCATE,
            input_file=Path("test.py"),
            output_file=Path("test.obf.py"),
            key_file=Path("test.map.json"),
        )
        service = ObfuscationService(options)
        with patch("builtins.print") as mock_print:
            service._print_success("test message")
            mock_print.assert_called_once_with("OK test message")


class TestArgumentParser:
    """
    Test ArgumentParser Class
    """

    def test_parser_initialization(self):
        """
        Test parser initialization
        """
        parser = ArgumentParser()
        assert parser.parser is not None

    def test_parse_obfuscate_command(self):
        """
        Test parsing obfuscate command
        """
        parser = ArgumentParser()
        options = parser.parse(["obfuscate", "test.py"])
        assert options.command == Command.OBFUSCATE
        assert options.input_file == Path("test.py")
        assert options.language == Language.PYTHON

    def test_parse_restore_command(self):
        """
        Test parsing restore command
        """
        parser = ArgumentParser()
        options = parser.parse(["restore", "test.py"])
        assert options.command == Command.RESTORE
        assert options.input_file == Path("test.py")

    def test_parse_with_seed(self):
        """
        Test parsing command with seed
        """
        parser = ArgumentParser()
        options = parser.parse(["obfuscate", "test.py", "--seed", "123"])
        assert options.seed == 123

    def test_parse_with_style(self):
        """
        Test parsing command with style
        """
        parser = ArgumentParser()
        options = parser.parse(["obfuscate", "test.py", "--style", "random"])
        assert options.style == "random"

    def test_parse_with_length(self):
        """
        Test parsing command with length
        """
        parser = ArgumentParser()
        options = parser.parse(["obfuscate", "test.py", "--length", "12"])
        assert options.length == 12

    def test_parse_with_output_file(self):
        """
        Test parsing command with output file
        """
        parser = ArgumentParser()
        options = parser.parse(["obfuscate", "test.py", "--out", "output.py"])
        assert options.output_file == Path("output.py")

    def test_parse_with_key_file(self):
        """
        Test parsing command with key file
        """
        parser = ArgumentParser()
        options = parser.parse(["obfuscate", "test.py", "--key", "custom.map.json"])
        assert options.key_file == Path("custom.map.json")

    def test_normalize_command_obfuscate(self):
        """
        Test normalizing obfuscate command
        """
        parser = ArgumentParser()
        assert parser._normalize_command("obfuscate") == Command.OBFUSCATE
        assert parser._normalize_command("o") == Command.OBFUSCATE
        assert parser._normalize_command("obf") == Command.OBFUSCATE

    def test_normalize_command_restore(self):
        """
        Test normalizing restore command
        """
        parser = ArgumentParser()
        assert parser._normalize_command("restore") == Command.RESTORE
        assert parser._normalize_command("r") == Command.RESTORE
        assert parser._normalize_command("res") == Command.RESTORE

    def test_normalize_command_invalid(self):
        """
        Test normalizing invalid command
        """
        parser = ArgumentParser()
        with pytest.raises(CLIError):
            parser._normalize_command("invalid")

    def test_detect_language_python(self):
        """
        Test detecting Python language
        """
        parser = ArgumentParser()
        assert parser._detect_language(".py") == Language.PYTHON

    def test_detect_language_c(self):
        """
        Test detecting C language
        """
        parser = ArgumentParser()
        assert parser._detect_language(".c") == Language.C
        assert parser._detect_language(".h") == Language.C
        assert parser._detect_language(".cpp") == Language.C

    def test_detect_language_default(self):
        """
        Test default language detection
        """
        parser = ArgumentParser()
        assert parser._detect_language(".unknown") == Language.PYTHON

    def test_resolve_output_path_obfuscate_with_custom(self):
        """
        Test resolving obfuscate output path (custom)
        """
        parser = ArgumentParser()
        input_path = Path("test.py")
        output_path = parser._resolve_output_path(
            input_path, "custom.py", Command.OBFUSCATE
        )
        assert output_path == Path("custom.py")

    def test_resolve_output_path_obfuscate_default(self):
        """
        Test resolving obfuscate output path (default)
        """
        parser = ArgumentParser()
        input_path = Path("test.py")
        output_path = parser._resolve_output_path(input_path, None, Command.OBFUSCATE)
        assert output_path == Path("test.obf.py")

    def test_resolve_output_path_restore_with_custom(self):
        """
        Test resolving restore output path (custom)
        """
        parser = ArgumentParser()
        input_path = Path("test.obf.py")
        output_path = parser._resolve_output_path(
            input_path, "restored.py", Command.RESTORE
        )
        assert output_path == Path("restored.py")

    def test_resolve_output_path_restore_default(self):
        """
        Test resolving restore output path (default)
        """
        parser = ArgumentParser()
        input_path = Path("test.obf.py")
        output_path = parser._resolve_output_path(input_path, None, Command.RESTORE)
        assert output_path == Path("test.res.py")

    def test_resolve_key_path_custom(self):
        """
        Test resolving key file path (custom)
        """
        parser = ArgumentParser()
        input_path = Path("test.py")
        key_path = parser._resolve_key_path(
            input_path, "custom.map.json", Command.OBFUSCATE, Language.PYTHON
        )
        assert key_path == Path("custom.map.json")

    def test_resolve_key_path_default_obfuscate(self):
        """
        Test resolving key file path (obfuscate default)
        """
        parser = ArgumentParser()
        input_path = Path("test.py")
        key_path = parser._resolve_key_path(
            input_path, None, Command.OBFUSCATE, Language.PYTHON
        )
        assert key_path is None

    def test_resolve_key_path_default_restore(self):
        """
        Test resolving key file path (restore default)
        """
        parser = ArgumentParser()
        input_path = Path("test.obf.py")
        key_path = parser._resolve_key_path(
            input_path, None, Command.RESTORE, Language.PYTHON
        )
        assert key_path is None

    def test_resolve_key_path_default_obfuscate_c(self):
        """
        Test resolving key file path (obfuscate default for C)
        """
        parser = ArgumentParser()
        input_path = Path("test.c")
        key_path = parser._resolve_key_path(
            input_path, None, Command.OBFUSCATE, Language.C
        )
        assert key_path is None


class TestCommandEnum:
    """
    Test Command Enum
    """

    def test_command_values(self):
        """
        Test command enum values
        """
        assert Command.OBFUSCATE.value == "obfuscate"
        assert Command.RESTORE.value == "restore"


class TestLanguageEnum:
    """
    Test Language Enum
    """

    def test_language_values(self):
        """
        Test language enum values
        """
        assert Language.PYTHON.value == "python"
        assert Language.C.value == "c"


class TestCLIError:
    """
    Test CLI Error Class
    """

    def test_cli_error_creation(self):
        """
        Test creating CLI error
        """
        error = CLIError("Test error")
        assert str(error) == "Test error"

    def test_file_not_found_error(self):
        """
        Test file not found error
        """
        error = FileNotFoundError("File not found")
        assert isinstance(error, CLIError)

    def test_obfuscation_error(self):
        """
        Test obfuscation error
        """
        error = ObfuscationError("Obfuscation failed")
        assert isinstance(error, CLIError)
