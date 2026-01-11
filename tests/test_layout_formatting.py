import ast

import pytest

from mistode.core import MappingManager, NameGenerator
from mistode.python import PythonObfuscator


class TestFormatting:
    def test_formatting_compactness(self):
        """Verify that obfuscated code is compact but valid (e.g. no space in np.tanh, space in from . import)."""
        source = """
import numpy as np
from . import module
def func():
    return np.tanh(1.0)
"""
        mm = MappingManager()
        gen = NameGenerator()
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        # Obfuscate
        obfuscated = obfuscator.obfuscate(source)

        # Check specific formatting in obfuscated output
        # np.tanh should be compact if np and tanh are valid tokens
        # Note: 'np' and 'tanh' might be renamed?
        # If renamed to A and B: A.B(1.0) without spaces.

        # We can disable renaming for this test or just check the structure?
        # Let's check that there are NO " . " patterns generally,
        # except for "from . "

        # Regex check? Or simple string find
        if " . " in obfuscated.replace("from . ", "MATCH"):
            pytest.fail(f"Found unexpected spacing around dot: {obfuscated}")

        # Verify valid python syntax
        try:
            ast.parse(obfuscated)
        except SyntaxError:
            pytest.fail(
                "Obfuscated code has invalid syntax (likely due to missing space in 'from .')"
            )

        # Verify restoration
        restored = obfuscator.restore(None, obfuscated)
        assert restored.strip() == source.strip()
