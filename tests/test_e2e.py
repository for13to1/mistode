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
End-to-end tests.

These exercise the real CLI in a separate process (fresh MappingManager),
covering the full obfuscate -> restore -> diff cycle that unit tests using
a shared in-memory mapping cannot catch (e.g. metadata embedding bugs).
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PYTHON_SRC = """\
# A sample module with imports, builtins, and docstrings
import math
from datetime import datetime


def calculate_area(radius):
    \"\"\"Calculate circle area\"\"\"
    return math.pi * radius ** 2


def format_result(value):
    return f"Result: {value:.2f}"


if __name__ == "__main__":
    print(format_result(calculate_area(2.0)))
"""

C_SRC = """\
#include <stdio.h>

#define PI 3.14159

struct Point {
    double x;
    double y;
};

double distance_squared(struct Point *p) {
    double dx = p->x;
    double dy = p->y;
    return dx * dx + dy * dy;
}

int main() {
    struct Point p;
    p.x = 3.0;
    p.y = 4.0;
    printf("distance^2: %f\\n", distance_squared(&p));
    return 0;
}
"""


def run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run the mistode CLI in a separate process (true cross-process test)."""
    return subprocess.run(
        [sys.executable, "-m", "mistode", *args],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )


class TestPythonEndToEnd:
    def test_obfuscate_restore_is_lossless(self, tmp_path: Path):
        src = tmp_path / "app.py"
        src.write_text(PYTHON_SRC, encoding="utf-8")
        obf = tmp_path / "app.obf.py"
        res = tmp_path / "app.res.py"

        result = run_cli("o", str(src), "--out", str(obf))
        assert result.returncode == 0, result.stderr
        assert obf.exists()

        result = run_cli("r", str(obf), "--out", str(res))
        assert result.returncode == 0, result.stderr
        assert res.read_text(encoding="utf-8") == PYTHON_SRC

    def test_obfuscated_code_is_valid_python(self, tmp_path: Path):
        src = tmp_path / "app.py"
        src.write_text(PYTHON_SRC, encoding="utf-8")
        obf = tmp_path / "app.obf.py"

        result = run_cli("o", str(src), "--out", str(obf))
        assert result.returncode == 0, result.stderr

        # The obfuscated file must still be importable/parseable
        check = subprocess.run(
            [sys.executable, "-c", f"import ast; ast.parse(open({str(obf)!r}).read())"],
            capture_output=True,
            text=True,
        )
        assert check.returncode == 0, check.stderr


class TestCEndToEnd:
    def test_obfuscate_restore_is_lossless(self, tmp_path: Path):
        src = tmp_path / "main.c"
        src.write_text(C_SRC, encoding="utf-8")
        obf = tmp_path / "main.obf.c"
        res = tmp_path / "main.res.c"

        result = run_cli("o", str(src), "--out", str(obf))
        assert result.returncode == 0, result.stderr
        assert obf.exists()

        result = run_cli("r", str(obf), "--out", str(res))
        assert result.returncode == 0, result.stderr
        assert res.read_text(encoding="utf-8") == C_SRC

    @pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not available")
    def test_obfuscated_code_compiles(self, tmp_path: Path):
        src = tmp_path / "main.c"
        src.write_text(C_SRC, encoding="utf-8")
        obf = tmp_path / "main.obf.c"

        result = run_cli("o", str(src), "--out", str(obf))
        assert result.returncode == 0, result.stderr

        compile_result = subprocess.run(
            ["gcc", "-c", str(obf), "-o", str(tmp_path / "main.o")],
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, compile_result.stderr


class TestProjectMode:
    """Directory (project) mode: multi-file obfuscation and restore."""

    def test_python_project_roundtrip_and_runs(self, tmp_path: Path):
        proj = tmp_path / "proj"
        (proj / "utils").mkdir(parents=True)
        (proj / "utils" / "mod.py").write_text(
            "def helper():\n    return 42\n\ndef _private():\n    return 1\n",
            encoding="utf-8",
        )
        (proj / "app.py").write_text(
            "from utils.mod import helper\n"
            "import utils.mod as m\n\n"
            "def main():\n"
            "    return helper() + m._private()\n\n"
            "print(main())\n",
            encoding="utf-8",
        )

        obf_dir = proj.with_name("proj.obf")
        result = run_cli("o", str(proj))
        assert result.returncode == 0, result.stderr
        # Mirror structure with original filenames (imports must keep working)
        assert (obf_dir / "app.py").exists()
        assert (obf_dir / "utils" / "mod.py").exists()

        # The obfuscated project must run and produce the same output
        run = subprocess.run(
            [sys.executable, str(obf_dir / "app.py")],
            capture_output=True,
            text=True,
        )
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "43"

        res_dir = proj.with_name("proj.res")
        result = run_cli("r", str(obf_dir))
        assert result.returncode == 0, result.stderr

        for rel in ("app.py", "utils/mod.py"):
            original = (proj / rel).read_bytes()
            restored = (res_dir / rel).read_bytes()
            assert restored == original

    @pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not available")
    def test_c_project_compiles_and_roundtrips(self, tmp_path: Path):
        proj = tmp_path / "cproj"
        proj.mkdir()
        (proj / "util.h").write_text(
            "#ifndef UTIL_H\n#define UTIL_H\nint shared_add(int a, int b);\n#endif\n",
            encoding="utf-8",
        )
        (proj / "util.c").write_text(
            '#include "util.h"\n\nint shared_add(int a, int b) {\n    return a + b;\n}\n',
            encoding="utf-8",
        )
        (proj / "main.c").write_text(
            '#include <stdio.h>\n#include "util.h"\n\n'
            "int main() {\n"
            '    printf("%d\\n", shared_add(2, 3));\n'
            "    return 0;\n}\n",
            encoding="utf-8",
        )

        obf_dir = proj.with_name("cproj.obf")
        result = run_cli("o", str(proj))
        assert result.returncode == 0, result.stderr

        # Obfuscated project must still compile and link
        compile_result = subprocess.run(
            [
                "gcc",
                "-I",
                str(obf_dir),
                str(obf_dir / "main.c"),
                str(obf_dir / "util.c"),
                "-o",
                str(tmp_path / "app"),
            ],
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, compile_result.stderr
        run = subprocess.run([str(tmp_path / "app")], capture_output=True, text=True)
        assert run.stdout.strip() == "5"

        res_dir = proj.with_name("cproj.res")
        result = run_cli("r", str(obf_dir))
        assert result.returncode == 0, result.stderr

        for rel in ("util.h", "util.c", "main.c"):
            original = (proj / rel).read_bytes()
            restored = (res_dir / rel).read_bytes()
            assert restored == original

    def test_project_skips_cache_and_venv_dirs(self, tmp_path: Path):
        proj = tmp_path / "proj"
        (proj / "__pycache__").mkdir(parents=True)
        (proj / ".venv" / "lib").mkdir(parents=True)
        (proj / "__pycache__" / "cached.py").write_text("x = 1\n")
        (proj / ".venv" / "lib" / "venvmod.py").write_text("y = 2\n")
        (proj / "real.py").write_text("z = 3\n")

        obf_dir = proj.with_name("proj.obf")
        result = run_cli("o", str(proj))
        assert result.returncode == 0, result.stderr

        # Only the real source file is obfuscated
        assert (obf_dir / "real.py").exists()
        assert not (obf_dir / "__pycache__").exists()
        assert not (obf_dir / ".venv").exists()

    def test_project_gbk_file_with_import(self, tmp_path: Path):
        """Cross-file import analysis must use the file's real encoding,
        so a GBK file containing an import still protects the imported
        name in the other module."""
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "leaf.py").write_text("def helper():\n    return 1\n")
        (proj / "mid.py").write_bytes(
            (
                "# -*- coding: gbk -*-\n"
                "# 中文注释\n"
                "from leaf import helper\n\n"
                "def run():\n"
                "    return helper()\n"
            ).encode("gbk")
        )
        (proj / "app.py").write_text("from mid import run\n\nprint(run())\n")

        obf_dir = proj.with_name("proj.obf")
        result = run_cli("o", str(proj))
        assert result.returncode == 0, result.stderr

        run = subprocess.run(
            [sys.executable, str(obf_dir / "app.py")],
            capture_output=True,
            text=True,
        )
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "1"

    @pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not available")
    def test_c_project_gbk_shared_symbol(self, tmp_path: Path):
        """C project with GBK-encoded files and a shared header symbol
        must obfuscate, compile, run, and restore byte-identically."""
        proj = tmp_path / "gcproj"
        proj.mkdir()
        (proj / "util.h").write_bytes(
            (
                "#ifndef UTIL_H\n#define UTIL_H\n"
                "/* 共享工具函数声明 */\n"
                "int shared_add(int a, int b);\n#endif\n"
            ).encode("gbk")
        )
        (proj / "util.c").write_bytes(
            (
                '#include "util.h"\n/* 实现 */\n'
                "int shared_add(int a, int b) {\n    return a + b;\n}\n"
            ).encode("gbk")
        )
        (proj / "main.c").write_bytes(
            (
                '#include <stdio.h>\n#include "util.h"\n'
                'int main() {\n    printf("%d\\n", shared_add(2, 3));\n'
                "    return 0;\n}\n"
            ).encode("gbk")
        )

        obf_dir = proj.with_name("gcproj.obf")
        result = run_cli("o", str(proj))
        assert result.returncode == 0, result.stderr

        compile_result = subprocess.run(
            [
                "gcc",
                "-I",
                str(obf_dir),
                str(obf_dir / "main.c"),
                str(obf_dir / "util.c"),
                "-o",
                str(tmp_path / "app"),
            ],
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, compile_result.stderr
        run = subprocess.run([str(tmp_path / "app")], capture_output=True, text=True)
        assert run.stdout.strip() == "5"

        res_dir = proj.with_name("gcproj.res")
        result = run_cli("r", str(obf_dir))
        assert result.returncode == 0, result.stderr

        for rel in ("util.h", "util.c", "main.c"):
            assert (res_dir / rel).read_bytes() == (proj / rel).read_bytes()


class TestEncryption:
    """--password encryption round-trip via the real CLI."""

    def test_password_roundtrip(self, tmp_path: Path):
        src = tmp_path / "app.py"
        src.write_text(PYTHON_SRC, encoding="utf-8")
        obf = tmp_path / "app.obf.py"
        res = tmp_path / "app.res.py"

        result = run_cli("o", str(src), "--out", str(obf), "--password", "s3cret")
        assert result.returncode == 0, result.stderr
        # Chunks must be encrypted, not plain
        assert "#@mistode:secure_chunk:" in obf.read_text(encoding="utf-8")

        result = run_cli("r", str(obf), "--out", str(res), "--password", "s3cret")
        assert result.returncode == 0, result.stderr
        assert res.read_text(encoding="utf-8") == PYTHON_SRC

    def test_wrong_password_fails(self, tmp_path: Path):
        src = tmp_path / "app.py"
        src.write_text(PYTHON_SRC, encoding="utf-8")
        obf = tmp_path / "app.obf.py"

        result = run_cli("o", str(src), "--out", str(obf), "--password", "right")
        assert result.returncode == 0, result.stderr

        result = run_cli(
            "r", str(obf), "--out", str(tmp_path / "r.py"), "--password", "wrong"
        )
        assert result.returncode != 0
        assert "mapping" in (result.stdout + result.stderr).lower()

    def test_missing_password_fails(self, tmp_path: Path):
        src = tmp_path / "app.py"
        src.write_text(PYTHON_SRC, encoding="utf-8")
        obf = tmp_path / "app.obf.py"

        result = run_cli("o", str(src), "--out", str(obf), "--password", "right")
        assert result.returncode == 0, result.stderr

        result = run_cli("r", str(obf), "--out", str(tmp_path / "r.py"))
        assert result.returncode != 0


class TestSeed:
    """--seed determinism via the real CLI."""

    def test_same_seed_deterministic(self, tmp_path: Path):
        src = tmp_path / "app.py"
        src.write_text(PYTHON_SRC, encoding="utf-8")

        run_cli("o", str(src), "--out", str(tmp_path / "a.obf.py"), "--seed", "42")
        run_cli("o", str(src), "--out", str(tmp_path / "b.obf.py"), "--seed", "42")

        a = (tmp_path / "a.obf.py").read_text(encoding="utf-8")
        b = (tmp_path / "b.obf.py").read_text(encoding="utf-8")
        assert a == b

    def test_different_seed_differs(self, tmp_path: Path):
        src = tmp_path / "app.py"
        src.write_text(PYTHON_SRC, encoding="utf-8")

        run_cli("o", str(src), "--out", str(tmp_path / "a.obf.py"), "--seed", "42")
        run_cli("o", str(src), "--out", str(tmp_path / "b.obf.py"), "--seed", "43")

        a = (tmp_path / "a.obf.py").read_text(encoding="utf-8")
        b = (tmp_path / "b.obf.py").read_text(encoding="utf-8")
        assert a != b


class TestNonUTF8:
    """Non-UTF-8 encodings (CJK) must round-trip byte-identically."""

    @pytest.mark.parametrize(
        "encoding,decl",
        [
            ("gbk", "# -*- coding: gbk -*-"),
            ("gbk", None),
            ("big5", "# -*- coding: big5 -*-"),
        ],
    )
    def test_cjk_roundtrip(self, tmp_path: Path, encoding: str, decl):
        body = 'def greet(name):\n    return "你好, " + name\n'
        content = (decl + "\n" if decl else "") + body + 'print(greet("世界"))\n'
        src = tmp_path / "cjk.py"
        src.write_bytes(content.encode(encoding))
        obf = tmp_path / "cjk.obf.py"
        res = tmp_path / "cjk.res.py"

        assert run_cli("o", str(src), "--out", str(obf)).returncode == 0
        # The obfuscated file is UTF-8 and must stay executable even when
        # the source declared a legacy encoding
        run = subprocess.run([sys.executable, str(obf)], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr

        assert run_cli("r", str(obf), "--out", str(res)).returncode == 0
        assert res.read_bytes() == content.encode(encoding)

    def test_utf8_bom_roundtrip(self, tmp_path: Path):
        content = "# hello\nprint('hi')\n"
        src = tmp_path / "bom.py"
        src.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
        obf = tmp_path / "bom.obf.py"
        res = tmp_path / "bom.res.py"

        assert run_cli("o", str(src), "--out", str(obf)).returncode == 0
        assert run_cli("r", str(obf), "--out", str(res)).returncode == 0
        # BOM is preserved in the restored output
        assert res.read_bytes() == b"\xef\xbb\xbf" + content.encode("utf-8")


class TestCRLF:
    """CRLF (Windows) line endings must round-trip bit-perfectly."""

    def test_python_crlf_roundtrip(self, tmp_path: Path):
        content = "def foo():\r\n    return 1\r\n"
        src = tmp_path / "crlf.py"
        src.write_bytes(content.encode("utf-8"))
        obf = tmp_path / "crlf.obf.py"
        res = tmp_path / "crlf.res.py"

        assert run_cli("o", str(src), "--out", str(obf)).returncode == 0
        assert run_cli("r", str(obf), "--out", str(res)).returncode == 0

        assert res.read_bytes() == content.encode("utf-8")

    def test_c_crlf_roundtrip(self, tmp_path: Path):
        content = "int main() {\r\n    return 0;\r\n}\r\n"
        src = tmp_path / "crlf.c"
        src.write_bytes(content.encode("utf-8"))
        obf = tmp_path / "crlf.obf.c"
        res = tmp_path / "crlf.res.c"

        assert run_cli("o", str(src), "--out", str(obf)).returncode == 0
        assert run_cli("r", str(obf), "--out", str(res)).returncode == 0

        assert res.read_bytes() == content.encode("utf-8")

    def test_c_file_without_obfuscatable_identifiers(self, tmp_path: Path):
        """A C file with only reserved identifiers has an empty mapping,
        which is valid and must still restore (regression for the empty-map
        guard raising spuriously)."""
        content = "int main() {\r\n    return 0;\r\n}\r\n"
        src = tmp_path / "simple.c"
        src.write_text(content, encoding="utf-8")
        obf = tmp_path / "simple.obf.c"
        res = tmp_path / "simple.res.c"

        assert run_cli("o", str(src), "--out", str(obf)).returncode == 0
        assert run_cli("r", str(obf), "--out", str(res)).returncode == 0

        assert res.read_bytes() == content.encode("utf-8")
