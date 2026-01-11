import ast

import pytest

from mistode.core import MappingManager, NameGenerator
from mistode.python import PythonObfuscator


class TestIndentationRepro:
    def test_nested_indentation_reconstruction(self):
        """Reproduce IndentationError with nested structures and dedents."""
        source = """
def level1():
    x = 1
    if x:
        y = 2
        def level2():
            return y
        return level2()
    else:
        return 0

class MyClass:
    def method(self):
        pass
"""
        mm = MappingManager()
        gen = NameGenerator()
        obfuscator = PythonObfuscator(mm, gen, "test.py")

        # Obfuscate
        obfuscated = obfuscator.obfuscate(source)

        print(f"Obfuscated Code:\n{obfuscated}")

        # Check syntax validity
        try:
            ast.parse(obfuscated)
        except IndentationError as e:
            pytest.fail(f"IndentationError in obfuscated code: {e}")
        except SyntaxError as e:
            pytest.fail(f"SyntaxError in obfuscated code: {e}")

        # Verify restoration
        restored = obfuscator.restore(None, obfuscated)
        assert restored.strip() == source.strip()
