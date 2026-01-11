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


from src.mistode import c


def test_c_obfuscator_basic():
    """
    Test C obfuscator basic functionality
    """
    code = """
#include <stdio.h>

int main() {
    int hello_variable = 42;
    char world_string[] = "test";
    printf("hello world\\n");
    return 0;
}
"""

    # Create C obfuscator instance
    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # Verify variable names are obfuscated (string content should be preserved)
    assert "hello_variable" not in obfuscated
    assert "world_string" not in obfuscated

    # Verify string content preservation (content within strings should not be
    # obfuscated)
    assert "hello world" in obfuscated

    # Verify basic structure preservation
    assert "#include" in obfuscated
    assert "int" in obfuscated
    assert "main" in obfuscated
    assert "printf" in obfuscated  # Standard library functions should be preserved


def test_c_obfuscator_variables():
    """
    Test C variable obfuscation
    """
    code = """
#include <stdio.h>

int main() {
    int my_variable = 42;
    char my_string[] = "test";
    float my_float = 3.14;

    printf("Value: %d\\n", my_variable);
    return 0;
}
"""

    # Create C obfuscator instance
    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # Verify variable names are obfuscated
    assert "my_variable" not in obfuscated
    assert "my_string" not in obfuscated
    assert "my_float" not in obfuscated

    # Verify basic structure preservation
    assert "int" in obfuscated
    assert "main" in obfuscated


def test_c_obfuscator_functions():
    """
    Test C function obfuscation
    """
    code = """
#include <stdio.h>

int calculate_sum(int a, int b) {
    return a + b;
}

void print_message(const char* msg) {
    printf("Message: %s\\n", msg);
}

int main() {
    int result = calculate_sum(10, 20);
    print_message("Hello");
    return 0;
}
"""

    # Create C obfuscator instance
    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # Verify function names are obfuscated
    assert "calculate_sum" not in obfuscated
    assert "print_message" not in obfuscated

    # Verify basic structure preservation
    assert "int" in obfuscated
    assert "main" in obfuscated


def test_c_obfuscator_comments():
    """
    Test C comment handling
    """
    code = """
#include <stdio.h>

// This is a comment
int main() {
    /* Multi-line
       comment here */
    printf("test");
    return 0;
}
"""

    # Create C obfuscator instance
    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # Verify comments are obfuscated
    assert "// This is a comment" not in obfuscated
    assert "/* Multi-line" not in obfuscated
    assert "comment here */" not in obfuscated


def test_c_obfuscator_keywords():
    """
    Test C keyword preservation
    """
    code = """
int main() {
    int x = 10;
    if (x > 5) {
        return 1;
    }
    return 0;
}
"""

    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # Verify keywords are preserved
    assert "int" in obfuscated
    assert "if" in obfuscated
    assert "return" in obfuscated


def test_c_obfuscator_restore():
    """
    Test C code restoration
    """
    code = """
#include <stdio.h>

int calculate(int a, int b) {
    return a + b;
}

int main() {
    int result = calculate(10, 20);
    printf("Result: %d\\n", result);
    return 0;
}
"""

    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)

    # Obfuscate
    obfuscated = obfuscator.obfuscate(code)

    # Restore
    restored = obfuscator.restore(obfuscated)

    # Verify keywords are preserved after restoration
    assert "calculate" in restored
    assert "int" in restored
    assert "return" in restored


def test_c_obfuscator_string_literals():
    """
    Test C string literal preservation
    """
    code = """
#include <stdio.h>

int main() {
    char* msg = "Hello, World!";
    printf("%s\\n", msg);
    return 0;
}
"""

    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # Verify string content preservation
    assert 'char* msg = "Hello, World!"' in obfuscated or "Hello, World!" in obfuscated
    assert "%s" in obfuscated


def test_c_obfuscator_preprocessor():
    """
    Test C preprocessor directives
    """
    code = """
#include <stdio.h>
#include <stdlib.h>

#define MAX_SIZE 100

int main() {
    return 0;
}
"""

    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # Verify preprocessor directives preservation
    assert "#include" in obfuscated
    assert "#define" in obfuscated


def test_c_obfuscator_multiple_variables():
    """
    Test C multiple variable obfuscation
    """
    code = """
int main() {
    int var1 = 1;
    int var2 = 2;
    int var3 = 3;
    int sum = var1 + var2 + var3;
    return sum;
}
"""

    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # Verify variable names are obfuscated
    assert "var1" not in obfuscated
    assert "var2" not in obfuscated
    assert "var3" not in obfuscated
    assert "sum" not in obfuscated


def test_c_obfuscator_struct():
    """
    Test C struct handling
    """
    code = """
struct Person {
    char name[50];
    int age;
    float salary;
};

int main() {
    struct Person p;
    p.age = 25;
    return 0;
}
"""

    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # Verify struct member names are obfuscated
    assert "name" not in obfuscated or obfuscated.count("name") < 2
    assert "age" not in obfuscated or obfuscated.count("age") < 2
    assert "salary" not in obfuscated or obfuscated.count("salary") < 2


def test_c_obfuscator_function_pointers():
    """
    Test C function pointer handling
    """
    code = """
int add(int a, int b) {
    return a + b;
}

int main() {
    int (*func)(int, int) = add;
    int result = func(1, 2);
    return result;
}
"""

    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # Verify function names are obfuscated
    assert "add" not in obfuscated
    # Verify basic structure preservation
    assert "int" in obfuscated
    assert "return" in obfuscated


def test_c_obfuscator_nested_functions():
    """
    Test C nested code blocks
    """
    code = """
int main() {
    int x = 10;
    {
        int nested_y = 20;
        x = x + nested_y;
    }
    return x;
}
"""

    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # Verify variable names are obfuscated
    import re

    assert not re.search(r"\bint x\b", obfuscated)
    assert not re.search(r"\breturn x\b", obfuscated)
    assert "nested_y" not in obfuscated


def test_c_obfuscator_macros():
    """
    Test C macro definition obfuscation
    """
    code = """
#define SQUARE(x) ((x) * (x))
#define PI 3.14159

int main() {
    int result = SQUARE(5);
    return 0;
}
"""

    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)

    obfuscated = obfuscator.obfuscate(code)

    assert "#define" in obfuscated
    assert "((" in obfuscated


def test_c_obfuscator_heuristic_scanner():
    """
    Test the parsing heuristic for identifying defined vs external symbols
    """
    code = """
    #include <stdio.h>
    
    // External declaration (used but not defined with body in this file)
    void external_log(char* msg); 

    // Defined function
    int my_add(int a, int b) { 
        // local 'a' and 'b' are defined args
        external_log("adding");
        return a + b;
    }

    int main() {
        // defined local
        int res = my_add(1, 2);
        printf("%d", res); // external printf
        return 0;
    }
    """

    from src.mistode import c
    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)

    # Force use of scanner directly to test the logic
    externals = obfuscator._scan_for_external_symbols(code)

    # 'printf' is used and not defined -> External
    assert "printf" in externals

    # 'external_log' is declared/used but has no body -> External
    assert "external_log" in externals

    # 'my_add' is defined with body -> Internal
    assert "my_add" not in externals

    # 'main' is defined with body -> Internal
    assert "main" not in externals

    # 'res' is defined as 'int res =' -> Internal
    assert "res" not in externals


def test_c_obfuscator_lossless_restore():
    """
    Test that restoration is lossless (identical to original source code).
    """
    # Includes unconventional spacing and comments to verify lossless accuracy
    code = """
#include <stdio.h>

// Weirdly formatted comment
    
int    main(  ) {
    int   val = 123; /* Inline comment */
    printf("Value: %d\\n", val);
    return 0;
}
"""

    from src.mistode import c
    from src.mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)

    # Obfuscate
    obfuscated = obfuscator.obfuscate(code)

    # Assert obfuscation happened
    assert "val" not in obfuscated
    assert "// @mistode:chunk:" in obfuscated

    # Restore
    restored = obfuscator.restore(obfuscated)

    # Assert lossless identity
    assert restored == code
