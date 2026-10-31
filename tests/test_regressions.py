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

"""Regression tests for semantics and payload-integrity defects.

Each test names the failure it prevents:

* scope/traversal-order regressions (class bodies, match captures) produced
  artifacts that raised ``NameError`` at runtime while restoring cleanly.
* payload-marker confusion (a string literal that looks like a chunk) either
  aborted restoration or silently corrupted it.
* configuration regressions silently downgraded encryption to plaintext.
"""

import base64
import json
import zlib

import pytest

from mistode.c import CObfuscator
from mistode.core import MappingManager, NameGenerator
from mistode.encrypt import make_cipher
from mistode.payload import PayloadError, decode_layouts, decode_metadata
from mistode.python import PythonObfuscator, _comment_tokens


def _roundtrip_python(source: str) -> tuple[str, str]:
    obfuscator = PythonObfuscator(MappingManager(), NameGenerator(), "t.py")
    artifact = obfuscator.obfuscate(source)
    restored = PythonObfuscator(MappingManager(), NameGenerator(), "t.py").restore(
        None, artifact
    )
    return artifact, restored


def _run_python(source: str) -> str:
    """Obfuscate `source`, run the artifact, and return its stdout."""
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    obfuscator = PythonObfuscator(MappingManager(), NameGenerator(), "t.py")
    artifact = obfuscator.obfuscate(source)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "artifact.py"
        path.write_text(artifact, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout


class TestClassBodyTraversalOrder:
    """A class-body name must never be renamed while its uses are not.

    The class body is visited only when traversal reaches the ``class``
    statement, while module-level references are recorded as soon as they are
    visited. Registering class-body names during traversal therefore split a
    definition from its uses whenever the class appeared after them.
    """

    def test_module_reference_before_class_body(self):
        source = (
            "value = 10\n"
            'print("before", value)\n'
            "\n"
            "class C:\n"
            "    value = 2\n"
            "\n"
            "    def get(self):\n"
            "        return self.value\n"
            "\n"
            "\n"
            "def f():\n"
            "    return value\n"
            "\n"
            'print("after", f())\n'
        )
        assert _run_python(source) == "before 10\nafter 10\n"

    def test_module_function_shares_name_with_method(self):
        source = (
            "def run():\n"
            '    return "module-run"\n'
            "\n"
            "\n"
            "class C:\n"
            "    def run(self):\n"
            '        return "method-run"\n'
            "\n"
            "\n"
            "print(run())\n"
        )
        assert _run_python(source) == "module-run\n"

    def test_module_function_shares_name_with_method_call(self):
        source = (
            "def helper():\n"
            "    return 1\n"
            "\n"
            "\n"
            "class C:\n"
            "    def helper(self):\n"
            "        return 2\n"
            "\n"
            "\n"
            "print(helper())\n"
        )
        assert _run_python(source) == "1\n"


class TestMatchCaptureBindings:
    """Match captures live on ``MatchAs``/``MatchStar``, not on ``ast.Name``.

    A capture name therefore has no replacement site, so renaming its uses
    leaves the binding behind and raises ``NameError``.
    """

    def test_sequence_capture(self):
        source = (
            "def handle(x):\n"
            "    match x:\n"
            "        case [a, b]:\n"
            "            return a + b\n"
            "        case _:\n"
            "            return None\n"
            "\n"
            "\n"
            "print(handle([1, 2]))\n"
        )
        assert _run_python(source) == "3\n"

    def test_mapping_capture(self):
        source = (
            "def handle(x):\n"
            "    match x:\n"
            '        case {"k": v}:\n'
            "            return v\n"
            "        case _:\n"
            "            return 0\n"
            "\n"
            "\n"
            'print(handle({"k": 9}))\n'
        )
        assert _run_python(source) == "9\n"

    def test_guard_capture(self):
        source = (
            "def sign(v):\n"
            "    match v:\n"
            "        case n if n > 0:\n"
            '            return "pos"\n'
            "        case n:\n"
            '            return "other"\n'
            "\n"
            "\n"
            "print(sign(2), sign(-1))\n"
        )
        assert _run_python(source) == "pos other\n"

    def test_star_capture(self):
        source = (
            "def split(x):\n"
            "    match x:\n"
            "        case [first, *rest]:\n"
            "            return first, tuple(rest)\n"
            "        case _:\n"
            "            return None\n"
            "\n"
            "\n"
            "print(split([1, 2, 3]))\n"
        )
        assert _run_python(source) == "(1, (2, 3))\n"


class TestMarkerConfusionPython:
    """A string literal that *contains* a chunk marker is not a chunk."""

    def test_single_line_string_marker_roundtrips(self):
        source = 'x = "#@mistode:chunk:AAAA"\nprint(x)\n'
        _, restored = _roundtrip_python(source)
        assert restored == source

    def test_multiline_string_marker_roundtrips(self):
        source = 'TEXT = """header\n#@mistode:chunk:AAAA\nfooter"""\nprint(TEXT)\n'
        artifact, restored = _roundtrip_python(source)
        assert restored == source
        assert _run_python(source) == "header\n#@mistode:chunk:AAAA\nfooter\n"

    def test_multiline_string_with_valid_payload_roundtrips(self):
        """A decodable payload inside a string must not become layout data."""
        payload = base64.b64encode(
            zlib.compress(json.dumps([{"p": "    "}]).encode())
        ).decode()
        source = (
            f'TEXT = """head\n#@mistode:chunk:{payload}\ntail"""\nprint(repr(TEXT))\n'
        )
        artifact, restored = _roundtrip_python(source)
        assert artifact.count(payload) == 1
        assert restored == source


class TestUndecodablePayloadIsReported:
    """A chunk payload that cannot be decoded is an error, not a skip."""

    def test_undecodable_chunk_is_reported(self):
        obfuscator = PythonObfuscator(MappingManager(), NameGenerator(), "t.py")
        artifact = obfuscator.obfuscate("x = 1\nprint(x)\n")
        broken = artifact.replace("#@mistode:chunk:", "#@mistode:chunk:!!!", 1)
        with pytest.raises(ValueError, match="Malformed chunk payload"):
            PythonObfuscator(MappingManager(), NameGenerator(), "t.py").restore(
                None, broken
            )


def _obfuscate_c(source: str) -> str:
    return CObfuscator(MappingManager(), NameGenerator(), "t.c").obfuscate(source)


def _restore_c(artifact: str) -> str:
    mapping = MappingManager()
    return CObfuscator(mapping, NameGenerator(), "t.c").restore(artifact)


C_SOURCE_WITH_MARKER_LINE = (
    "#include <stdio.h>\n"
    "int main(void)\n"
    "{\n"
    "    const char *m =\n"
    '"/* @mistode:chunk:AAAA */";\n'
    "    (void)m;\n"
    "    return 0;\n"
    "}\n"
)


class TestMarkerConfusionC:
    """C chunk markers must be anchored at the start of a line."""

    def test_string_literal_on_its_own_line_roundtrips(self):
        artifact = _obfuscate_c(C_SOURCE_WITH_MARKER_LINE)
        assert _restore_c(artifact) == C_SOURCE_WITH_MARKER_LINE

    def test_string_literal_inline_roundtrips(self):
        source = (
            "#include <stdio.h>\n"
            "int main(void){ const char *m = "
            '"/* @mistode:chunk:AAAA */"; (void)m; return 0; }\n'
        )
        artifact = _obfuscate_c(source)
        assert _restore_c(artifact) == source

    def test_string_literal_with_valid_payload_roundtrips(self):
        """A decodable payload inside a string literal is still just a string."""
        payload = base64.b64encode(
            zlib.compress(json.dumps([{"p": "    "}]).encode())
        ).decode()
        source = (
            "#include <stdio.h>\n"
            "int main(void)\n"
            "{\n"
            f'    const char *m =\n"/* @mistode:chunk:{payload} */";\n'
            "    (void)m;\n"
            "    return 0;\n"
            "}\n"
        )
        artifact = _obfuscate_c(source)
        assert _restore_c(artifact) == source


class TestLayoutBalance:
    """Injected chunk markers must be detected even with valid payloads."""

    @staticmethod
    def _injected_artifact() -> tuple[str, str]:
        source = '#include <stdio.h>\nint main(void){puts("x");return 0;}\n'
        artifact = _obfuscate_c(source)
        payload = base64.b64encode(
            zlib.compress(json.dumps([{"p": "  "}]).encode())
        ).decode()
        lines = artifact.split("\n")
        chunks = [
            i for i, line in enumerate(lines) if line.startswith("/* @mistode:chunk:")
        ]
        lines.insert(chunks[1], f"/* @mistode:chunk:{payload} */")
        return source, "\n".join(lines)

    def test_injected_wellformed_chunk_is_rejected(self):
        """Shape validation cannot catch this; the balance check must."""
        _, injected = self._injected_artifact()
        with pytest.raises(ValueError, match="inconsistent"):
            _restore_c(injected)

    def test_lost_chunk_is_rejected(self):
        source = '#include <stdio.h>\nint main(void){puts("x");return 0;}\n'
        artifact = _obfuscate_c(source)
        lines = artifact.split("\n")
        chunks = [
            i for i, line in enumerate(lines) if line.startswith("/* @mistode:chunk:")
        ]
        # Drop a middle chunk: later code tokens are then left without layout.
        del lines[chunks[1]]
        with pytest.raises(ValueError, match="inconsistent"):
            _restore_c("\n".join(lines))

    def test_dropping_the_first_chunk_is_detected(self):
        """A single deleted record is caught by the metadata layout count.

        Pairing alone cannot see it: the remaining records still pair up, so
        the leftover count stays inside the range a healthy artifact can
        occupy. The count embedded in the metadata makes the loss observable.
        """
        source = '#include <stdio.h>\nint main(void){puts("x");return 0;}\n'
        artifact = _obfuscate_c(source)
        lines = artifact.split("\n")
        first = next(
            i for i, line in enumerate(lines) if line.startswith("/* @mistode:chunk:")
        )
        del lines[first]
        with pytest.raises(ValueError, match="metadata declares"):
            _restore_c("\n".join(lines))

    def test_injecting_one_record_is_detected(self):
        """The symmetric case: one extra record is caught the same way."""
        source = '#include <stdio.h>\nint main(void){puts("x");return 0;}'
        artifact = _obfuscate_c(source)
        payload = base64.b64encode(
            zlib.compress(json.dumps([{"p": "  "}]).encode())
        ).decode()
        lines = artifact.split("\n")
        chunks = [
            i for i, line in enumerate(lines) if line.startswith("/* @mistode:chunk:")
        ]
        lines.insert(chunks[1], f"/* @mistode:chunk:{payload} */")
        with pytest.raises(ValueError, match="metadata declares"):
            _restore_c("\n".join(lines))

    def test_python_dropping_one_record_is_detected(self):
        source = "x = 1\nprint(x)\n"
        artifact, _ = _roundtrip_python(source)
        lines = artifact.split("\n")
        first = next(
            i for i, line in enumerate(lines) if line.startswith("#@mistode:chunk:")
        )
        del lines[first]
        # Caught one layer earlier than the metadata check: some code token
        # is left with no layout record.
        with pytest.raises(ValueError, match="inconsistent"):
            PythonObfuscator(MappingManager(), NameGenerator(), "t.py").restore(
                None, "\n".join(lines)
            )

    def test_python_injecting_one_record_is_detected(self):
        source = "x = 1\nprint(x)\n"
        artifact, _ = _roundtrip_python(source)
        payload = base64.b64encode(
            zlib.compress(json.dumps([{"p": "  "}]).encode())
        ).decode()
        lines = artifact.split("\n")
        chunks = [
            i for i, line in enumerate(lines) if line.startswith("#@mistode:chunk:")
        ]
        lines.insert(chunks[1], f"#@mistode:chunk:{payload}")
        with pytest.raises(ValueError, match="metadata declares"):
            PythonObfuscator(MappingManager(), NameGenerator(), "t.py").restore(
                None, "\n".join(lines)
            )


class TestKeyFilePathDiagnostics:
    """A non-empty mapping file skips metadata extraction.

    The tokeniser error then has to be reported by the layout stage. Placement
    matters: damage before the first chunk leaves no markers collected at all,
    which used to be misreported as "no layout chunks found".
    """

    @staticmethod
    def _artifact_and_key(tmp_path):
        obfuscator = PythonObfuscator(MappingManager(), NameGenerator(), "t.py")
        artifact = obfuscator.obfuscate("x = 1\nprint(x)\n")
        assert obfuscator.identifier_mapping, "key file must not be empty"
        key = tmp_path / "key.json"
        key.write_text(
            json.dumps({"identifier_mapping": obfuscator.identifier_mapping}),
            encoding="utf-8",
        )
        return artifact, key

    def test_damage_before_the_first_chunk_reports_tokenise_failure(self, tmp_path):
        artifact, key = self._artifact_and_key(tmp_path)
        broken = 'msg = "unterminated\n' + artifact
        with pytest.raises(ValueError, match="does not tokenise"):
            PythonObfuscator(MappingManager(), NameGenerator(), "t.py").restore(
                str(key), broken
            )

    def test_damage_after_the_last_chunk_still_restores(self, tmp_path):
        """Every marker was collected before the failure, so it is recoverable."""
        artifact, key = self._artifact_and_key(tmp_path)
        broken = artifact + 'msg = "unterminated\n'
        restored = PythonObfuscator(MappingManager(), NameGenerator(), "t.py").restore(
            str(key), broken
        )
        assert restored == "x = 1\nprint(x)\n"


class TestNoChunkDiagnosis:
    """A file with no chunk is "not an artifact", not a lost chunk.

    Reporting "a chunk marker was inserted or removed" sends the reader
    looking for a chunk that never existed.
    """

    @pytest.mark.parametrize("code", ["", "\n", "\n\n\n", "   \n  \n", "  "])
    def test_blank_input_is_not_an_artifact(self, code):
        from mistode.layout import LayoutEngine

        with pytest.raises(ValueError, match="not appear to be obfuscated"):
            LayoutEngine().restore_token_stream(code, {})

    def test_missing_layouts_after_a_chunk_are_reported_as_inconsistent(self):
        """The other branch: a chunk exists, but too few records for the code."""
        from mistode.layout import LayoutEngine

        layouts = base64.b64encode(
            zlib.compress(json.dumps([{"p": ""}]).encode())
        ).decode()
        artifact = f"#@mistode:chunk:{layouts}\nx = 1 + 2\n"
        with pytest.raises(ValueError, match="inconsistent"):
            LayoutEngine().restore_token_stream(artifact, {})


class TestPayloadShape:
    """A decodable payload with the wrong structure is still rejected.

    base64 + zlib + JSON all succeed for these payloads, so only the shape
    check stands between them and a corrupt layout queue.
    """

    @staticmethod
    def _encode(obj) -> str:
        return base64.b64encode(zlib.compress(json.dumps(obj).encode())).decode()

    @pytest.mark.parametrize("payload", [{"p": " "}, ["x"], "hi", 42])
    def test_layouts_must_be_a_list_of_records(self, payload):
        with pytest.raises(PayloadError, match="not a list of layout records"):
            decode_layouts(self._encode(payload), secure=False, cipher=None)

    @pytest.mark.parametrize("payload", [[1, 2], "hi", 7])
    def test_metadata_must_be_an_object(self, payload):
        with pytest.raises(PayloadError, match="expected a JSON object"):
            decode_metadata(self._encode(payload), secure=False, cipher=None)


class TestReindentedArtifact:
    """Markers are located by token position, not by line offset.

    An artifact whose marker lines were indented (or joined onto a code line)
    still restores: the reader maps each comment token back to the line it
    starts on instead of requiring the marker to begin the line.
    """

    @staticmethod
    def _indent_markers(artifact: str) -> str:
        return "\n".join(
            "    " + line if line.startswith("/* @mistode:") else line
            for line in artifact.split("\n")
        )

    def test_indented_markers_restore(self):
        source = '#include <stdio.h>\nint main(void){puts("x");return 0;}\n'
        artifact = _obfuscate_c(source)
        assert _restore_c(self._indent_markers(artifact)) == source

    def test_indented_markers_restore_with_password(self):
        source = "#include <stdio.h>\nint main(void){return 0;}\n"
        obfuscator = CObfuscator(MappingManager(), NameGenerator(), "t.c")
        artifact = obfuscator.obfuscate(source, encryption_key="k")
        restored = CObfuscator(MappingManager(), NameGenerator(), "t.c").restore(
            self._indent_markers(artifact), encryption_key="k"
        )
        assert restored == source

    def test_marker_joined_onto_a_code_line_restores(self):
        source = '#include <stdio.h>\nint main(void){puts("x");return 0;}\n'
        artifact = _obfuscate_c(source)
        joined = "\n".join(
            "int zz = 0; " + line if line.startswith("/* @mistode:chunk:") else line
            for line in artifact.split("\n")
        )
        assert _restore_c(joined) == source

    def test_reindented_source_with_fake_marker_restores(self):
        """The two fixes must hold together.

        Reader correctness now depends on the lexer's comment classification
        and on locating that comment by offset. A string literal that looks
        like a marker must stay program data *and* the real markers must still
        be found after the artifact is re-indented.
        """
        source = (
            "#include <stdio.h>\n"
            "int main(void)\n"
            "{\n"
            '    const char *m =\n"/* @mistode:chunk:AAAA */";\n'
            "    (void)m;\n"
            "    return 0;\n"
            "}\n"
        )
        artifact = _obfuscate_c(source)
        # The fake marker is still present in the artifact as string content.
        assert '"/* @mistode:chunk:AAAA */"' in artifact
        assert _restore_c(self._indent_markers(artifact)) == source

    def test_reindented_source_with_fake_metadata_marker_restores(self):
        source = (
            "#include <stdio.h>\n"
            "int main(void)\n"
            "{\n"
            '    puts("/* @mistode:metadata:AAAA */");\n'
            "    return 0;\n"
            "}\n"
        )
        artifact = _obfuscate_c(source)
        assert _restore_c(self._indent_markers(artifact)) == source

    def test_marker_after_a_colon_on_the_same_line_restores(self):
        """The payload is taken from the comment token, not re-split on `:`.

        Recovering it from the raw line with `split(":", 2)` breaks as soon as
        the preceding code contains a colon, so the comment text is used.
        """
        source = '#include <stdio.h>\nint main(void){puts("a:b");return 0;}\n'
        artifact = _obfuscate_c(source)
        chunk = next(
            line
            for line in artifact.split("\n")
            if line.startswith("/* @mistode:chunk:")
        )
        shifted = artifact.replace(chunk, 'int zz = 0; printf("%d:", zz); ' + chunk)
        assert _restore_c(shifted) == source

    def test_python_marker_after_a_colon_on_the_same_line_restores(self):
        source = 'x = 1\nprint("a:b")\n'
        artifact, _ = _roundtrip_python(source)
        chunk = next(
            line for line in artifact.split("\n") if line.startswith("#@mistode:chunk:")
        )
        shifted = artifact.replace(chunk, 'y = "a:b"; ' + chunk)
        restored = PythonObfuscator(MappingManager(), NameGenerator(), "t.py").restore(
            None, shifted
        )
        assert restored == source

    def test_reindented_python_with_fake_marker_restores(self):
        """Only the real markers move; the string content must stay intact."""
        source = 'TEXT = """header\n#@mistode:chunk:AAAA\nfooter"""\nprint(TEXT)\n'
        artifact, _ = _roundtrip_python(source)
        lines = artifact.split("\n")
        # Locate real markers as comment tokens; the lookalike inside the
        # string is program data and must not be touched.
        marker_lines = {
            tok.start[0]
            for tok in _comment_tokens(artifact)
            if tok.string.startswith("#@mistode:")
        }
        indented = "\n".join(
            "    " + line if i + 1 in marker_lines else line
            for i, line in enumerate(lines)
        )
        restored = PythonObfuscator(MappingManager(), NameGenerator(), "t.py").restore(
            None, indented
        )
        assert restored == source


class TestLegalEdgeCasesStillRestore:
    """The balance check must not reject legitimate artifacts."""

    @pytest.mark.parametrize(
        "name,source",
        [
            ("normal", "#include <stdio.h>\nint main(void){return 0;}\n"),
            ("no_final_newline", "#include <stdio.h>\nint main(void){return 0;}"),
            ("empty", ""),
            ("only_comments", "// just a comment\n/* and a block */\n"),
            (
                "crlf",
                "#include <stdio.h>\r\nint main(void)\r\n{\r\n    return 0;\r\n}\r\n",
            ),
            ("multiline_macro", "#define A(x) \\\n    ((x) + 1)\n"),
            ("blank_lines", "int f(void)\n{\n\n\n    return 0;\n\n}\n"),
        ],
    )
    def test_c_roundtrip(self, name, source):
        artifact = _obfuscate_c(source)
        assert _restore_c(artifact) == source, name

    @pytest.mark.parametrize(
        "name,source",
        [
            ("normal", "x = 1\nprint(x)\n"),
            ("no_final_newline", "x = 1\nprint(x)"),
            ("empty", ""),
            ("only_comment", "# just a comment\n"),
            ("docstring", '"""doc"""\ndef f():\n    return 1\n'),
            ("crlf", "x = 1\r\nprint(x)\r\n"),
            ("blank_lines", "def f():\n\n\n    return 1\n\n\n"),
        ],
    )
    def test_python_roundtrip(self, name, source):
        _, restored = _roundtrip_python(source)
        assert restored == source, name


class TestPasswordSemantics:
    """An empty password must not silently downgrade to plaintext."""

    def test_empty_password_is_rejected_by_cipher(self):
        with pytest.raises(ValueError, match="Password cannot be empty"):
            make_cipher("stream", "")

    def test_none_password_is_rejected_by_stream_cipher(self):
        with pytest.raises(ValueError, match="requires a password"):
            make_cipher("stream", None)

    def test_empty_password_reaches_encryption_when_cipher_is_explicit(self):
        """`cipher=stream` plus `password=""` must fail, not produce plaintext."""
        obfuscator = PythonObfuscator(MappingManager(), NameGenerator(), "t.py")
        with pytest.raises(ValueError, match="Password cannot be empty"):
            obfuscator.obfuscate("x = 1\n", encryption_key="", cipher="stream")


class TestMalformedPayloadsAreReported:
    """Silently skipping a bad payload desynchronises the layout queue."""

    def test_c_corrupt_chunk_payload_raises(self):
        source = "#include <stdio.h>\nint main(void){return 0;}\n"
        artifact = _obfuscate_c(source)
        lines = artifact.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("/* @mistode:chunk:"):
                lines[i] = "/* @mistode:chunk:!!!!not-base64!!!! */"
                break
        with pytest.raises(ValueError, match="Malformed chunk payload"):
            _restore_c("\n".join(lines))

    def test_untokenisable_code_is_reported_as_such(self):
        """A parse failure must not masquerade as a missing chunk marker.

        Tokenising up front keeps the two diagnostics distinct: otherwise the
        truncated token stream looks like layout records went missing.
        """
        layouts = base64.b64encode(
            zlib.compress(json.dumps([{"p": ""}, {"p": "\n"}]).encode())
        ).decode()
        metadata = base64.b64encode(
            zlib.compress(json.dumps({"identifier_mapping": {}}).encode())
        ).decode()
        artifact = f"#@mistode:chunk:{layouts}\ndef f(:\n#@mistode:metadata:{metadata}"
        with pytest.raises(ValueError, match="does not tokenise"):
            PythonObfuscator(MappingManager(), NameGenerator(), "t.py").restore(
                None, artifact
            )

    def test_unterminated_string_reports_tokenise_failure(self):
        """An unreadable file must not be reported as having no metadata.

        An unterminated string swallows the footer, so a reader that treats
        TokenError as "no marker found" would blame a missing footer.
        """
        metadata = base64.b64encode(
            zlib.compress(json.dumps({"identifier_mapping": {"a": "b"}}).encode())
        ).decode()
        artifact = f'x = """unterminated\n#@mistode:metadata:{metadata}\n'
        with pytest.raises(ValueError, match="does not tokenise"):
            PythonObfuscator(MappingManager(), NameGenerator(), "t.py").restore(
                None, artifact
            )

    def test_python_corrupt_chunk_payload_raises(self):
        source = "x = 1\nprint(x)\n"
        artifact, _ = _roundtrip_python(source)
        lines = artifact.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("#@mistode:chunk:"):
                lines[i] = "#@mistode:chunk:!!!!not-base64!!!!"
                break
        with pytest.raises(ValueError, match="Malformed chunk payload"):
            PythonObfuscator(MappingManager(), NameGenerator(), "t.py").restore(
                None, "\n".join(lines)
            )

    def test_c_metadata_marker_in_string_roundtrips(self):
        """Metadata is read from a comment token, never from string content."""
        source = (
            "#include <stdio.h>\n"
            "int main(void)\n"
            "{\n"
            '    puts("/* @mistode:metadata:AAAA */");\n'
            "    return 0;\n"
            "}\n"
        )
        artifact = _obfuscate_c(source)
        assert _restore_c(artifact) == source

    def test_c_corrupt_metadata_footer_reports_error(self):
        """zlib.error is not a ValueError; it must not escape as a traceback."""
        source = "#include <stdio.h>\nint main(void){return 0;}\n"
        artifact = _obfuscate_c(source)
        broken = artifact.replace("@mistode:metadata:", "@mistode:metadata:!!!", 1)
        with pytest.raises(ValueError, match="Malformed metadata payload"):
            _restore_c(broken)
