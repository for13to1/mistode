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
Layout engine edge cases: f-strings, hashes inside strings, multiline
strings, comment content, async/comprehensions. Each case asserts both
lossless restoration AND that the obfuscated code still executes
correctly (functional equivalence, observed via underscore-prefixed
variables which the obfuscator preserves).
"""

from mistode.core import MappingManager, NameGenerator
from mistode.python import PythonObfuscator


def _roundtrip(source: str, password: str | None = None):
    """Obfuscate then restore; returns (obfuscated, restored)."""
    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = PythonObfuscator(mm, gen, "test.py")
    obfuscated = obfuscator.obfuscate(source, encryption_key=password)
    restored = obfuscator.restore(None, obfuscated, encryption_key=password)
    return obfuscated, restored


def _result(source: str):
    """Exec source and return the underscore-prefixed `_result` variable."""
    ns: dict = {}
    exec(compile(source, "<test>", "exec"), ns)
    return ns["_result"]


class TestLayoutEdgeCases:
    def test_fstring_nested_and_format_specs(self):
        source = (
            "def fmt(x, width=8):\n"
            "    return f\"{f'{x}'!r:>{width}}\"\n"
            "_result = fmt(3)\n"
        )
        obfuscated, restored = _roundtrip(source)
        assert restored == source
        assert _result(obfuscated) == _result(source)

    def test_hash_inside_string_is_not_comment(self):
        source = 's = "# not a comment"\nt = "a#b"\n_result = (s, t)\n'
        obfuscated, restored = _roundtrip(source)
        assert restored == source
        assert _result(obfuscated) == ("# not a comment", "a#b")

    def test_multiline_strings(self):
        source = (
            's = """line1\nline2 with "quotes" and # hash\nline3"""\n'
            "t = '''another\nmultiline'''\n"
            "_result = (s, t)\n"
        )
        obfuscated, restored = _roundtrip(source)
        assert restored == source
        assert _result(obfuscated) == _result(source)

    def test_comment_with_code_like_text(self):
        source = "# def fake_function(): return 1\nx = 1  # int y = 2\n_result = x\n"
        obfuscated, restored = _roundtrip(source)
        assert restored == source
        assert _result(obfuscated) == 1

    def test_async_and_comprehensions(self):
        source = (
            "async def fetch(url):\n"
            "    results = [x * 2 for x in range(3) if x % 2]\n"
            "    return {k: v for k, v in zip('ab', results)}\n"
            "import asyncio\n"
            "_result = asyncio.run(fetch('http://x'))\n"
        )
        obfuscated, restored = _roundtrip(source)
        assert restored == source
        assert _result(obfuscated) == {"a": 2}

    def test_encoding_declaration_preserved(self):
        source = "# -*- coding: utf-8 -*-\ndef f():\n    return 1\n_result = f()\n"
        obfuscated, restored = _roundtrip(source)
        assert restored == source
        assert _result(obfuscated) == 1

    def test_operators_stay_compact(self):
        source = "def calc(a, b):\n    return a**2 + b*3 - a//b\n_result = calc(5, 2)\n"
        obfuscated, restored = _roundtrip(source)
        assert restored == source
        assert _result(obfuscated) == _result(source)

    def test_docstring_variants(self):
        source = (
            'def a():\n    """plain"""\n    return 1\n\n'
            "def b():\n    '''single'''\n    return 2\n\n"
            "def c():\n    return 3\n"
            "_result = (a(), b(), c())\n"
        )
        obfuscated, restored = _roundtrip(source)
        assert restored == source
        assert _result(obfuscated) == (1, 2, 3)

    def test_secure_roundtrip_edge_cases(self):
        source = (
            "def g():\n"
            '    return f"mixed {chr(35)} end"\n'
            "x = '''\n# inside multiline\n'''\n"
            "_result = (g(), x)\n"
        )
        obfuscated, restored = _roundtrip(source, password="edge-pass")
        assert restored == source
        assert _result(obfuscated) == _result(source)
