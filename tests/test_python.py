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

"""Python Obfuscator Tests"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from mistode import PythonObfuscator
from mistode.core import MappingManager, NameGenerator


class TestPythonObfuscator:
    """
    Python Obfuscator Test Class
    """

    @pytest.fixture
    def obfuscator(self):
        """
        Create obfuscator fixture
        """
        mm = MappingManager()
        gen = NameGenerator()
        return PythonObfuscator(mm, gen, "test")

    def test_basic_obfuscation(self, obfuscator):
        """
        Test basic obfuscation functionality
        """
        source_code = '''
def hello_world():
    """
    Simple test function
    """
    message = "Hello, World!"
    return message
'''
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify obfuscation result
        assert "hello_world" not in obfuscated
        assert "message" not in obfuscated
        # Verify function name is obfuscated (no longer using v_ prefix)
        assert "def " in obfuscated and "(" in obfuscated
        # Verify new obfuscated name is generated
        lines = obfuscated.split("\n")
        func_line = [line for line in lines if line.startswith("def ")][0]
        func_name = func_line.split("def ")[1].split("(")[0]
        assert len(func_name) >= 8  # Verify token length requirements

    def test_import_preservation(self, obfuscator):
        """
        Test import statement preservation
        """
        source_code = """
import re
from openpyxl.utils import get_column_letter

def test_function():
    return re.sub("pattern", "replacement", "text")
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify import statements are preserved
        assert "import re" in obfuscated
        assert "from openpyxl.utils import get_column_letter" in obfuscated
        assert "re.sub" in obfuscated

    def test_docstring_obfuscation(self, obfuscator):
        """
        Test docstring obfuscation
        """
        source_code = '''
def documented_function():
    """
    This is a detailed docstring
    """
    return True
'''
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify docstring is obfuscated
        assert "This is a detailed docstring" not in obfuscated
        # assert "Obfuscated Docstring" in obfuscated  <-- Removed as we now use empty string/layout

    def test_builtin_methods_preservation(self, obfuscator):
        """
        Test builtin methods preservation
        """
        source_code = '''
def process_string(text):
    """
    Process string
    """
    return text.strip().upper().replace(" ", "_")
'''
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify builtin methods are preserved
        assert ".strip()" in obfuscated
        assert ".upper()" in obfuscated
        assert ".replace(" in obfuscated

    def test_obfuscate_restore_cycle(self, obfuscator, tmp_path):
        """
        Test obfuscate and restore cycle
        """
        source_code = '''
def complex_function(param1, param2):
    """
    Complex test function
    """
    result = param1 + param2
    return result * 2
'''
        # Create temporary mapping file
        mapping_file = tmp_path / "test_mapping.json"

        # Obfuscate and save mapping file
        obfuscated_code = obfuscator.obfuscate(source_code, str(mapping_file))

        # Restore
        restored = obfuscator.restore(
            str(mapping_file), obfuscated_code=obfuscated_code
        )

        # Verify restored code is identical to original (ignoring leading/trailing
        # whitespace)
        assert restored.strip() == source_code.strip()

    def test_class_obfuscation(self, obfuscator):
        """
        Test class definition obfuscation
        """
        source_code = """
class MyClass:
    def __init__(self):
        self.my_attribute = 42

    def my_method(self, param1):
        return param1 + self.my_attribute

class AnotherClass(BaseClass):
    pass
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify class name is obfuscated
        assert "class MyClass" not in obfuscated
        assert "class AnotherClass" not in obfuscated
        # Verify basic structure preservation
        assert "class " in obfuscated
        assert "def " in obfuscated

    def test_lambda_preservation(self, obfuscator):
        """
        Test lambda expression preservation
        """
        source_code = """
my_lambda = lambda x: x * 2
result = list(map(lambda x: x + 1, [1, 2, 3]))
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify lambda expression preservation
        assert "lambda" in obfuscated
        assert "map" in obfuscated

    def test_decorator_preservation(self, obfuscator):
        """
        Test decorator preservation
        """
        source_code = """
def my_decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@my_decorator
def decorated_function():
    return "decorated"
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify decorator syntax preservation
        assert "@" in obfuscated
        assert "decorated_function" not in obfuscated

    def test_exception_handling(self, obfuscator):
        """
        Test exception handling
        """
        source_code = """
def risky_function():
    try:
        result = dangerous_call()
        return result
    except ValueError as e:
        error_handler(e)
        return None
    finally:
        cleanup()
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify exception handling keywords preservation
        assert "try:" in obfuscated
        assert "except" in obfuscated
        assert "finally:" in obfuscated

    def test_with_statement(self, obfuscator):
        """
        Test with statement
        """
        source_code = """
def file_handler():
    with open("file.txt", "r") as f:
        content = f.read()
    return content
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify with statement preservation
        assert "with " in obfuscated
        assert "as " in obfuscated

    def test_list_comprehension(self, obfuscator):
        """
        Test list comprehension
        """
        source_code = """
def process_list():
    numbers = [1, 2, 3, 4, 5]
    squares = [x ** 2 for x in numbers if x > 2]
    return squares
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify list comprehension preservation
        assert "[" in obfuscated
        assert "for " in obfuscated
        assert "in " in obfuscated

    def test_generator_expression(self, obfuscator):
        """
        Test generator expression
        """
        source_code = """
def process_generator():
    numbers = range(10)
    gen = (x * 2 for x in numbers if x % 2 == 0)
    return list(gen)
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify generator expression preservation
        assert "(" in obfuscated
        assert "for " in obfuscated

    def test_nested_functions(self, obfuscator):
        """
        Test nested functions
        """
        source_code = """
def outer_function(x):
    def inner_function(y):
        return x + y
    return inner_function(10)
"""
        obfuscated = obfuscator.obfuscate(source_code)

        assert "def " in obfuscated
        assert "return " in obfuscated

    def test_async_await(self, obfuscator):
        """
        Test async/await
        """
        source_code = """
async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
    return data
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify async syntax preservation
        assert "async def" in obfuscated
        assert "await " in obfuscated

    def test_type_hints(self, obfuscator):
        """
        Test type hints
        """
        source_code = """
def process_data(items: list[str], count: int = 10) -> dict[str, int]:
    result = {}
    for i in range(count):
        result[f"item_{i}"] = items[i] if i < len(items) else None
    return result
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify type hints preservation
        assert ":" in obfuscated
        assert "list[str]" in obfuscated or "list" in obfuscated

    def test_f_string(self, obfuscator):
        """
        Test f-string
        """
        source_code = """
def format_message(name: str, age: int) -> str:
    message = f"Hello, {name}! You are {age} years old."
    return message
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify f-string preservation
        assert 'f"' in obfuscated or "f'" in obfuscated

    def test_multiline_string(self, obfuscator):
        """
        Test multiline string
        """
        source_code = '''
def get_description():
    description = """Test content"""
    return description.strip()
'''
        obfuscated = obfuscator.obfuscate(source_code)

        assert "strip()" in obfuscated

    def test_global_variables(self, obfuscator):
        """
        Test global variables
        """
        source_code = """
global_counter = 0

def increment():
    global global_counter
    global_counter += 1
    return global_counter
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify global keyword preservation
        assert "global" in obfuscated

    def test_property_decorator(self, obfuscator):
        """
        Test property decorator
        """
        source_code = """
class Temperature:
    def __init__(self, celsius):
        self._celsius = celsius

    @property
    def fahrenheit(self):
        return self._celsius * 9 / 5 + 32

    @fahrenheit.setter
    def fahrenheit(self, value):
        self._celsius = (value - 32) * 5 / 9
"""
        obfuscated = obfuscator.obfuscate(source_code)

        assert "@property" in obfuscated
        assert "@" in obfuscated and ".setter" in obfuscated

    def test_staticmethod_classmethod(self, obfuscator):
        """
        Test staticmethod and classmethod
        """
        source_code = """
class Calculator:
    @staticmethod
    def add(a, b):
        return a + b

    @classmethod
    def create_double(cls, value):
        return cls(value * 2)
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify decorators preservation
        assert "@staticmethod" in obfuscated
        assert "@classmethod" in obfuscated

    def test_dict_unpacking(self, obfuscator):
        """
        Test dict unpacking
        """
        source_code = """
def merge_dicts(dict1, dict2):
    merged = {**dict1, **dict2}
    return merged
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify unpacking syntax preservation
        assert "**dict1" in obfuscated or "**" in obfuscated

    def test_walrus_operator(self, obfuscator):
        """
        Test walrus operator
        """
        source_code = """
def process_data(data):
    if (n := len(data)) > 0:
        print(f"Processing {n} items")
    return n
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify walrus operator preservation
        assert ":=" in obfuscated

    def test_match_statement(self, obfuscator):
        """
        Test match statement
        """
        source_code = """
def process_status(status):
    match status:
        case 200:
            return "OK"
        case 404:
            return "Not Found"
        case _:
            return "Unknown"
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify match statement preservation
        assert "match " in obfuscated
        assert "case " in obfuscated

    def test_all_exports_preserved(self, obfuscator):
        """
        Names declared in `__all__` are the module's public contract and
        must not be obfuscated, so `from module import *` keeps working.
        """
        source_code = """
def public_api():
    return 42

__all__ = ["public_api"]
"""
        obfuscated = obfuscator.obfuscate(source_code)

        assert "__all__" in obfuscated
        assert "public_api" in obfuscated

        # The obfuscated module must still support star-import of the export
        ns = {}
        exec(compile(obfuscated, "<obf>", "exec"), ns)
        assert ns["__all__"] == ["public_api"]
        assert "public_api" in ns

    def test_keyword_argument_execution(self, obfuscator):
        """
        Test keyword argument execution
        """
        source_code = """
def greet(name, greeting="Hello"):
    return f"{greeting}, {name}"

def main():
    # Call with keyword argument that matches parameter name
    msg = greet("World", greeting="Hi")
    return msg

result = main()
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Execute obfuscated code
        loc = {}
        exec(obfuscated, loc)
        # Check if any variable holds the result (since 'result' variable name
        # is obfuscated)
        assert "Hi, World" in loc.values()

    def test_lossless_restoration(self, obfuscator):
        """
        Test that restoration is lossless (identical to original source code).
        """
        # Complex source with specific formatting, comments, and structure
        source_code = """
import os

# Top level comment
def complex_formatting(  param1  ):
    '''
    Docstring with
    multiple lines
    '''
    x = 1  # Inline comment
    
    if x:
        print( "  Spacing inside string  " )
    
    return x
"""
        obfuscated = obfuscator.obfuscate(source_code)

        # Verify source chunks are present
        assert "#@mistode:chunk:" in obfuscated

        # Restore
        restored = obfuscator.restore("", obfuscated_code=obfuscated)

        # Verify lossless identity
        assert restored == source_code
