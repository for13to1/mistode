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
In-process tests for the CLI service layer.

The subprocess e2e tests exercise the real CLI but don't contribute to
coverage. These call ObfuscationService directly so the CLI code paths
(detect encoding, directory collection, cross-file analysis, single-file
and directory obfuscate/restore) are measured and regression-tested.
"""

from pathlib import Path

import pytest

from mistode.cli import Command, Language, ObfuscationService, Options


def _svc(command: Command, input_file: Path, output_file: Path, **kwargs):
    options = Options(
        command=command,
        input_file=input_file,
        output_file=output_file,
        **kwargs,
    )
    return ObfuscationService(options)


class TestDetectEncoding:
    def test_utf8(self, tmp_path: Path):
        p = tmp_path / "f.py"
        p.write_text("x = 1\n", encoding="utf-8")
        svc = _svc(Command.OBFUSCATE, p, tmp_path / "o.py")
        assert svc._detect_encoding(p) == "utf-8"

    def test_gbk(self, tmp_path: Path):
        p = tmp_path / "f.py"
        p.write_bytes("# 中文\nx = 1\n".encode("gbk"))
        svc = _svc(Command.OBFUSCATE, p, tmp_path / "o.py")
        assert svc._detect_encoding(p) == "gb18030"

    def test_utf8_bom(self, tmp_path: Path):
        p = tmp_path / "f.py"
        p.write_bytes(b"\xef\xbb\xbfx = 1\n")
        svc = _svc(Command.OBFUSCATE, p, tmp_path / "o.py")
        assert svc._detect_encoding(p) == "utf-8-sig"

    def test_utf16_le(self, tmp_path: Path):
        p = tmp_path / "f.py"
        p.write_bytes("x = 1\n".encode("utf-16-le"))
        svc = _svc(Command.OBFUSCATE, p, tmp_path / "o.py")
        assert svc._detect_encoding(p) == "utf-16-le"

    def test_missing_file_raises(self, tmp_path: Path):
        p = tmp_path / "missing.py"
        svc = _svc(Command.OBFUSCATE, p, tmp_path / "o.py")
        with pytest.raises(Exception):
            svc._detect_encoding(p)


class TestCollectSourceFiles:
    def test_skips_hidden_and_build_dirs(self, tmp_path: Path):
        proj = tmp_path / "proj"
        (proj / ".venv").mkdir(parents=True)
        (proj / "build" / "CMakeFiles").mkdir(parents=True)
        (proj / "bin").mkdir()
        (proj / "src").mkdir()
        (proj / "real.py").write_text("x = 1\n")
        (proj / "src" / "real.c").write_text("int f() { return 0; }\n")
        (proj / ".venv" / "v.py").write_text("y = 1\n")
        (proj / "build" / "CMakeFiles" / "g.c").write_text("int g() { return 0; }\n")
        (proj / "bin" / "stale.c").write_text("int s() { return 0; }\n")

        from mistode.project import collect_source_files

        files = collect_source_files(proj)
        rel = sorted(str(f.relative_to(proj)) for f in files)
        assert rel == ["real.py", "src/real.c"]


class TestCrossFileAnalysis:
    def test_python_imports(self, tmp_path: Path):
        a = tmp_path / "a.py"
        a.write_text("from mod import helper\nfrom pkg.x import foo, bar\nimport z\n")
        b = tmp_path / "b.py"
        b.write_text("from . import rel\n")

        svc = _svc(Command.OBFUSCATE, a, tmp_path / "o.py")
        imports = svc._analyzer().collect_cross_file_imports([a, b])
        # `import z` binds the module name z, so it is preserved too
        assert imports == {"helper", "foo", "bar", "rel", "z"}

    def test_c_shared_symbols(self, tmp_path: Path):
        h = tmp_path / "util.h"
        h.write_text("int shared(int a, int b);\n")
        c = tmp_path / "util.c"
        c.write_text('#include "util.h"\nint shared(int a, int b) { return a + b; }\n')
        m = tmp_path / "main.c"
        m.write_text('#include "util.h"\nint main() { return shared(1, 2); }\n')

        svc = _svc(Command.OBFUSCATE, m, tmp_path / "o.c")
        shared = svc._analyzer().collect_cross_file_symbols([h, c, m])
        assert "shared" in shared


class TestSingleFileInProcess:
    def test_obfuscate_restore(self, tmp_path: Path, capsys):
        src = tmp_path / "a.py"
        src.write_text("def f():\n    return 1\n")
        out = tmp_path / "a.obf.py"
        svc = _svc(Command.OBFUSCATE, src, out)
        svc.execute()
        assert out.exists()

        res = tmp_path / "a.res.py"
        _svc(Command.RESTORE, out, res).execute()
        assert res.read_text(encoding="utf-8") == "def f():\n    return 1\n"

    def test_obfuscate_syntax_error_raises(self, tmp_path: Path):
        src = tmp_path / "bad.py"
        src.write_text("def broken(:\n    pass\n")
        out = tmp_path / "bad.obf.py"
        svc = _svc(Command.OBFUSCATE, src, out)
        with pytest.raises(Exception):
            svc.execute()


class TestDirectoryInProcess:
    def test_obfuscate_restore_directory(self, tmp_path: Path, capsys):
        proj = tmp_path / "proj"
        (proj / "utils").mkdir(parents=True)
        (proj / "utils" / "mod.py").write_text("def helper():\n    return 42\n")
        (proj / "app.py").write_text("from utils.mod import helper\nprint(helper())\n")

        out = tmp_path / "proj.obf"
        _svc(Command.OBFUSCATE, proj, out).execute()
        assert (out / "app.py").exists()
        assert (out / "utils" / "mod.py").exists()

        res = tmp_path / "proj.res"
        _svc(Command.RESTORE, out, res).execute()
        assert (res / "app.py").read_text() == (proj / "app.py").read_text()
        assert (res / "utils" / "mod.py").read_text() == (
            proj / "utils" / "mod.py"
        ).read_text()

    def test_empty_directory_raises(self, tmp_path: Path):
        proj = tmp_path / "empty"
        proj.mkdir()
        out = tmp_path / "empty.obf"
        svc = _svc(Command.OBFUSCATE, proj, out)
        with pytest.raises(Exception):
            svc.execute()


class TestPasswordSeedDerivation:
    def test_password_derives_seed(self, tmp_path: Path):
        src = tmp_path / "a.py"
        src.write_text("x = 1\n")
        # Two services with the same password (no explicit seed) must
        # derive the same seed and thus produce identical output
        o1 = tmp_path / "a1.obf.py"
        o2 = tmp_path / "a2.obf.py"
        _svc(Command.OBFUSCATE, src, o1, password="s3cret").execute()
        _svc(Command.OBFUSCATE, src, o2, password="s3cret").execute()
        assert o1.read_text() == o2.read_text()


class TestCLanguageInProcess:
    def test_c_single_file_obfuscate_restore(self, tmp_path: Path):
        src = tmp_path / "a.c"
        src.write_text("int add(int a, int b) { return a + b; }\n")
        out = tmp_path / "a.obf.c"
        _svc(Command.OBFUSCATE, src, out, language=Language.C).execute()
        assert out.exists()

        res = tmp_path / "a.res.c"
        _svc(Command.RESTORE, out, res, language=Language.C).execute()
        assert res.read_text() == src.read_text()

    def test_c_directory_obfuscate_restore(self, tmp_path: Path):
        proj = tmp_path / "cproj"
        proj.mkdir()
        (proj / "util.h").write_text("int shared(int a, int b);\n")
        (proj / "util.c").write_text(
            '#include "util.h"\nint shared(int a, int b) { return a + b; }\n'
        )
        (proj / "main.c").write_text(
            '#include "util.h"\nint main() { return shared(1, 2); }\n'
        )

        out = tmp_path / "cproj.obf"
        _svc(Command.OBFUSCATE, proj, out).execute()
        assert (out / "util.c").exists()
        assert (out / "main.c").exists()

        res = tmp_path / "cproj.res"
        _svc(Command.RESTORE, out, res).execute()
        for name in ("util.h", "util.c", "main.c"):
            assert (res / name).read_text() == (proj / name).read_text()


class TestKeyFile:
    """`--key` must contain the real mapping and be usable for restore."""

    def test_key_mapping_is_not_empty(self, tmp_path: Path):
        src = tmp_path / "a.py"
        src.write_text("def api(uid):\n    return uid * 2\n", encoding="utf-8")
        out = tmp_path / "a.obf.py"
        key = tmp_path / "a.map.json"

        _svc(Command.OBFUSCATE, src, out, key_file=key).execute()

        import json

        data = json.loads(key.read_text(encoding="utf-8"))
        assert data["identifier_mapping"], "key file must carry the mapping"
        assert "api" in data["identifier_mapping"]

    def test_restore_from_key_without_embedded_metadata(self, tmp_path: Path):
        src = tmp_path / "a.py"
        original = "def api(uid):\n    return uid * 2\n"
        src.write_text(original, encoding="utf-8")
        out = tmp_path / "a.obf.py"
        key = tmp_path / "a.map.json"
        _svc(Command.OBFUSCATE, src, out, key_file=key).execute()

        # Drop the embedded metadata so the key file is the only source.
        stripped = "\n".join(
            line
            for line in out.read_text(encoding="utf-8").splitlines()
            if not line.startswith("#@mistode:metadata:")
        )
        out.write_text(stripped + "\n", encoding="utf-8")

        restored = tmp_path / "a.res.py"
        _svc(Command.RESTORE, out, restored, key_file=key).execute()
        assert restored.read_text(encoding="utf-8") == original


class TestAssets:
    """Project mode must keep the deliverable runnable."""

    def _project(self, tmp_path: Path) -> Path:
        proj = tmp_path / "proj"
        (proj / "pkg").mkdir(parents=True)
        (proj / "data").mkdir()
        (proj / "pkg" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (proj / "data" / "conf.json").write_text('{"n": 1}\n', encoding="utf-8")
        (proj / "data" / "secret.env").write_text("TOKEN=x\n", encoding="utf-8")
        return proj

    def test_copy_is_default(self, tmp_path: Path):
        proj = self._project(tmp_path)
        out = tmp_path / "proj.obf"
        _svc(Command.OBFUSCATE, proj, out).execute()

        assert (out / "pkg" / "app.py").exists()
        assert (out / "data" / "conf.json").exists()
        # Credential-looking files are part of the deliverable by default.
        assert (out / "data" / "secret.env").exists()

    def test_skip_secrets(self, tmp_path: Path):
        proj = self._project(tmp_path)
        out = tmp_path / "proj.obf"
        _svc(Command.OBFUSCATE, proj, out, assets_skip_secrets=True).execute()
        assert (out / "data" / "conf.json").exists()
        assert not (out / "data" / "secret.env").exists()

    def test_skip(self, tmp_path: Path):
        proj = self._project(tmp_path)
        out = tmp_path / "proj.obf"
        _svc(Command.OBFUSCATE, proj, out, assets="skip").execute()
        assert (out / "pkg" / "app.py").exists()
        assert not (out / "data" / "conf.json").exists()

    def test_list_does_not_copy(self, tmp_path: Path, capsys):
        proj = self._project(tmp_path)
        out = tmp_path / "proj.obf"
        _svc(Command.OBFUSCATE, proj, out, assets="list").execute()

        assert not (out / "data" / "conf.json").exists()
        assert "conf.json" in capsys.readouterr().out


class TestSingleFileAggressiveMethods:
    def test_flag_renames_provable_methods(self, tmp_path: Path):
        src = tmp_path / "m.py"
        src.write_text(
            "class A:\n"
            "    def go(self):\n"
            "        return self.step()\n"
            "    def step(self):\n"
            "        return 3\n",
            encoding="utf-8",
        )
        plain = tmp_path / "plain.py"
        aggressive = tmp_path / "aggressive.py"

        _svc(Command.OBFUSCATE, src, plain, seed=7).execute()
        _svc(
            Command.OBFUSCATE,
            src,
            aggressive,
            seed=7,
            aggressive_methods=True,
        ).execute()

        plain_text = plain.read_text(encoding="utf-8")
        aggressive_text = aggressive.read_text(encoding="utf-8")
        assert "def step(" in plain_text
        assert "def step(" not in aggressive_text


class TestStarImports:
    """Star imports must protect the target module's public names."""

    def _run_project(self, tmp_path: Path, files: dict[str, str]) -> Path:
        proj = tmp_path / "proj"
        for name, text in files.items():
            path = proj / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        out = tmp_path / "proj.obf"
        _svc(Command.OBFUSCATE, proj, out).execute()
        return out

    def test_absolute_star_import(self, tmp_path: Path):
        out = self._run_project(
            tmp_path,
            {
                "utils.py": "def helper():\n    return 42\n",
                "main.py": "from utils import *\nprint(helper())\n",
            },
        )
        assert "def helper(" in (out / "utils.py").read_text(encoding="utf-8")

    def test_package_star_import(self, tmp_path: Path):
        out = self._run_project(
            tmp_path,
            {
                "pkg/__init__.py": "from .mod import *\n",
                "pkg/mod.py": "def helper():\n    return 7\n",
                "main.py": "import pkg\nprint(pkg.helper())\n",
            },
        )
        assert "def helper(" in (out / "pkg" / "mod.py").read_text(encoding="utf-8")


class TestRestoreDirectoryAssets:
    def test_assets_come_back(self, tmp_path: Path):
        proj = tmp_path / "proj"
        (proj / "data").mkdir(parents=True)
        (proj / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (proj / "data" / "conf.json").write_text('{"n": 1}\n', encoding="utf-8")

        obf = tmp_path / "proj.obf"
        res = tmp_path / "proj.res"
        _svc(Command.OBFUSCATE, proj, obf).execute()
        _svc(Command.RESTORE, obf, res).execute()

        assert (res / "data" / "conf.json").read_text(encoding="utf-8") == '{"n": 1}\n'
        assert (res / "app.py").read_text(encoding="utf-8") == "VALUE = 1\n"
