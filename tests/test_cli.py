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

"""Command Line Interface Tests"""

import subprocess
import sys
import tempfile
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestCLI:
    """
    CLI Test Class
    """

    def test_cli_help(self):
        """
        Test help command
        """
        result = subprocess.run(
            [sys.executable, "-m", "mistode.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0 or result.returncode == 1
        assert "obfuscate" in result.stdout
        assert "restore" in result.stdout

    def test_obfuscate_restore_cycle(self):
        """
        Test obfuscate and restore cycle
        """
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                '''
def test_function():
    """
    Test function
    """
    return "hello"
'''
            )
            original_file = f.name
            restored_file = ""

        try:
            # Obfuscate file
            obfuscate_result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "obfuscate", original_file],
                capture_output=True,
                text=True,
            )
            assert obfuscate_result.returncode == 0

            # Check if obfuscated file exists
            obfuscated_file = original_file.replace(".py", ".obf.py")
            assert Path(obfuscated_file).exists()

            # Restore file
            key_file = original_file.replace(".py", ".map.json")
            restore_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mistode.cli",
                    "restore",
                    obfuscated_file,
                ],
                capture_output=True,
                text=True,
            )
            assert restore_result.returncode == 0

            # Check if restored file exists
            restored_file = obfuscated_file.replace(".obf.py", ".res.py")
            assert Path(restored_file).exists()

        finally:
            # Clean up temporary files
            key_file = original_file.replace(".py", ".map.json")
            for file_path in [original_file, obfuscated_file, restored_file, key_file]:
                if Path(file_path).exists():
                    Path(file_path).unlink()

    def test_obfuscate_with_imports(self):
        """
        Test obfuscation with import statements
        """
        # Create temporary file with import statements
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                '''
import re
import os

def process_text(text):
    """
    Process text
    """
    return re.sub(r"\\s+", " ", text.strip())
'''
            )
            original_file = f.name

        try:
            # Obfuscate file
            obfuscate_result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "obfuscate", original_file],
                capture_output=True,
                text=True,
            )
            assert obfuscate_result.returncode == 0

            # Check if obfuscated file exists
            obfuscated_file = original_file.replace(".py", ".obf.py")
            assert Path(obfuscated_file).exists()

            # Read obfuscated file content
            with open(obfuscated_file, "r") as f:
                obfuscated_content = f.read()

            # Verify import statements are preserved
            assert "import re" in obfuscated_content
            assert "import os" in obfuscated_content
            assert "re.sub" in obfuscated_content

        finally:
            # Clean up temporary files
            for file_path in [original_file, obfuscated_file]:
                if Path(file_path).exists():
                    Path(file_path).unlink()

    def test_cli_invalid_command(self):
        """
        Test invalid command
        """
        result = subprocess.run(
            [sys.executable, "-m", "mistode.cli", "invalid"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "error" in result.stderr.lower() or "invalid" in result.stderr.lower()

    def test_obfuscate_nonexistent_file(self):
        """
        Test obfuscating nonexistent file
        """
        result = subprocess.run(
            [sys.executable, "-m", "mistode.cli", "obfuscate", "nonexistent.py"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        # Error message output to stdout
        assert (
            "error" in result.stdout.lower()
            or "could not read" in result.stdout.lower()
        )

    def test_restore_without_key_file(self):
        """
        Test restore without key file
        """
        # Create temporary obfuscated file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obf.py", delete=False) as f:
            f.write("def a(): return 1")
            obfuscated_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "restore", obfuscated_file],
                capture_output=True,
                text=True,
            )
            assert result.returncode != 0
            # Error message output to stdout
            assert "no mapping provided" in result.stdout.lower()
        finally:
            if Path(obfuscated_file).exists():
                Path(obfuscated_file).unlink()

    def test_obfuscate_c_file(self):
        """
        Test C file obfuscation
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(
                """
#include <stdio.h>

int main() {
    printf("Hello World");
    return 0;
}
"""
            )
            original_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "obfuscate", original_file],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

            # Check if obfuscated file exists
            obfuscated_file = original_file.replace(".c", ".obf.c")
            assert Path(obfuscated_file).exists()

        finally:
            for file_path in [original_file, obfuscated_file]:
                if Path(file_path).exists():
                    Path(file_path).unlink()

    def test_obfuscate_with_custom_options(self):
        """
        Test custom options
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test(): return 1")
            original_file = f.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mistode.cli",
                    "obfuscate",
                    original_file,
                    "--seed",
                    "123",
                    "--style",
                    "random",
                    "--length",
                    "12",
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

        finally:
            if Path(original_file).exists():
                Path(original_file).unlink()

    def test_obfuscate_with_output_file(self):
        """
        Test specified output file
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test(): return 1")
            original_file = f.name

        try:
            output_file = original_file.replace(".py", "_output.py")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mistode.cli",
                    "obfuscate",
                    original_file,
                    "--out",
                    output_file,
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            assert Path(output_file).exists()
        finally:
            for file_path in [original_file, output_file]:
                key_file = original_file.replace(".py", ".map.json")
                if Path(file_path).exists():
                    Path(file_path).unlink()
                if Path(key_file).exists():
                    Path(key_file).unlink()

    def test_obfuscate_with_key_file(self):
        """
        Test specified key file
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test(): return 1")
            original_file = f.name

        try:
            key_file = original_file.replace(".py", "_custom.map.json")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mistode.cli",
                    "obfuscate",
                    original_file,
                    "--key",
                    key_file,
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            assert Path(key_file).exists()
        finally:
            for file_path in [original_file]:
                obfuscated_file = original_file.replace(".py", ".obf.py")
                for fp in [obfuscated_file, key_file]:
                    if Path(fp).exists():
                        Path(fp).unlink()

    def test_restore_with_output_file(self):
        """
        Test restore with specified output file
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def original(): return 'original'")
            original_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "obfuscate", original_file],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

            obfuscated_file = original_file.replace(".py", ".obf.py")
            key_file = original_file.replace(".py", ".map.json")
            restored_file = original_file.replace(".py", "_restored.py")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mistode.cli",
                    "restore",
                    obfuscated_file,
                    "--out",
                    restored_file,
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            assert Path(restored_file).exists()
        finally:
            for file_path in [original_file, obfuscated_file, key_file, restored_file]:
                if Path(file_path).exists():
                    Path(file_path).unlink()

    def test_obfuscate_cpp_file(self):
        """
        Test C++ file obfuscation
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cpp", delete=False) as f:
            f.write(
                """
#include <iostream>
#include <string>

class Greeter {
private:
    std::string message;

public:
    Greeter(std::string msg) : message(msg) {}

    void greet() {
        std::cout << message << std::endl;
    }
};

int main() {
    Greeter g("Hello, World!");
    g.greet();
    return 0;
}
"""
            )
            original_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "obfuscate", original_file],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

            obfuscated_file = original_file.replace(".cpp", ".obf.cpp")
            assert Path(obfuscated_file).exists()

            with open(obfuscated_file, "r") as f:
                content = f.read()

            assert "#include" in content
            assert ":" in content
            assert "int main" in content

        finally:
            for file_path in [original_file, obfuscated_file]:
                key_file = original_file.replace(".h", ".map.json")
                if Path(file_path).exists():
                    Path(file_path).unlink()
                if Path(key_file).exists():
                    Path(key_file).unlink()

    def test_obfuscate_h_file(self):
        """
        Test header file obfuscation
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".h", delete=False) as f:
            f.write(
                """
#ifndef HEADER_H
#define HEADER_H

#define MAX_VALUE 100

int calculate_sum(int a, int b);

#endif
"""
            )
            original_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "obfuscate", original_file],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

            obfuscated_file = original_file.replace(".h", ".obf.h")
            assert Path(obfuscated_file).exists()

        finally:
            for file_path in [original_file, obfuscated_file]:
                key_file = original_file.replace(".h", ".map.json")
                if Path(file_path).exists():
                    Path(file_path).unlink()
                if Path(key_file).exists():
                    Path(key_file).unlink()

    def test_obfuscate_unknown_extension(self):
        """
        Test unknown extension file
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".unknown", delete=False
        ) as f:
            f.write("print('test')")
            original_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "obfuscate", original_file],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

            obfuscated_file = original_file.replace(".unknown", ".obf.unknown")
            assert Path(obfuscated_file).exists()

        finally:
            for file_path in [original_file, obfuscated_file]:
                key_file = original_file.replace(".unknown", ".map.json")
                if Path(file_path).exists():
                    Path(file_path).unlink()
                if Path(key_file).exists():
                    Path(key_file).unlink()

    def test_restore_with_alias(self):
        """
        Test restore with alias
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test(): return 1")
            original_file = f.name

        obfuscated_file = original_file.replace(".py", ".obf.py")
        key_file = original_file.replace(".py", ".map.json")
        restored_file = ""

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "obfuscate", original_file],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mistode.cli",
                    "restore",
                    obfuscated_file,
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

            restored_file = obfuscated_file.replace(".obf.py", ".res.py")
            assert Path(restored_file).exists()

        finally:
            for file_path in [original_file, obfuscated_file, key_file, restored_file]:
                if file_path and Path(file_path).exists():
                    Path(file_path).unlink()

    def test_obfuscate_with_alias(self):
        """
        Test obfuscate with alias
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test(): return 1")
            original_file = f.name

        obfuscated_file = original_file.replace(".py", ".obf.py")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "obfuscate", original_file],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

            assert Path(obfuscated_file).exists()

        finally:
            for file_path in [original_file, obfuscated_file]:
                key_file = original_file.replace(".py", ".map.json")
                if Path(file_path).exists():
                    Path(file_path).unlink()
                if Path(key_file).exists():
                    Path(key_file).unlink()

    def test_obfuscate_empty_file(self):
        """
        Test empty file obfuscation
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            original_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "obfuscate", original_file],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

            obfuscated_file = original_file.replace(".py", ".obf.py")
            assert Path(obfuscated_file).exists()

        finally:
            for file_path in [original_file, obfuscated_file]:
                key_file = original_file.replace(".py", ".map.json")
                if Path(file_path).exists():
                    Path(file_path).unlink()
                if Path(key_file).exists():
                    Path(key_file).unlink()

    def test_obfuscate_unicode_content(self):
        """
        Test Unicode content obfuscation
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# -*- coding: utf-8 -*-\ndef 你好(): return '世界'")
            original_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, "-m", "mistode.cli", "obfuscate", original_file],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0

            obfuscated_file = original_file.replace(".py", ".obf.py")
            assert Path(obfuscated_file).exists()

        finally:
            for file_path in [original_file, obfuscated_file]:
                key_file = original_file.replace(".py", ".map.json")
                if Path(file_path).exists():
                    Path(file_path).unlink()
                if Path(key_file).exists():
                    Path(key_file).unlink()

    def test_restore_non_obfuscated_file(self):
        """
        Test restoring non-obfuscated file
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test(): return 1")
            original_file = f.name

        key_file = original_file.replace(".py", ".map.json")

        with open(key_file, "w") as f:
            f.write(
                '{"twd": {}, "comments": {}, "files": {}, '
                '"encryption_key": null, "string_quote_types": {}}'
            )

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mistode.cli",
                    "restore",
                    original_file,
                    "--key",
                    key_file,
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 1

        finally:
            for file_path in [original_file, key_file]:
                if Path(file_path).exists():
                    Path(file_path).unlink()
