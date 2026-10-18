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


import pytest

from mistode import c


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
    from mistode.core import MappingManager, NameGenerator

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
    from mistode.core import MappingManager, NameGenerator

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
    from mistode.core import MappingManager, NameGenerator

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
    from mistode.core import MappingManager, NameGenerator

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

    from mistode.core import MappingManager, NameGenerator

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

    from mistode.core import MappingManager, NameGenerator

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

    from mistode.core import MappingManager, NameGenerator

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

    from mistode.core import MappingManager, NameGenerator

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

    from mistode.core import MappingManager, NameGenerator

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

    from mistode.core import MappingManager, NameGenerator

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

    from mistode.core import MappingManager, NameGenerator

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

    from mistode.core import MappingManager, NameGenerator

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

    from mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)

    obfuscated = obfuscator.obfuscate(code)

    assert "#define" in obfuscated
    assert "((" in obfuscated


def test_c_obfuscator_preserves_macro_names():
    """
    Regression: macro names following `#define` must not be obfuscated,
    matching the documented 'Preprocessor Preserved' guarantee.
    """
    code = """
#define MAX_SIZE 100
#define PI 3.14159
#define SQUARE(x) ((x) * (x))

int main() {
    int result = SQUARE(5);
    return MAX_SIZE;
}
"""

    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    assert "#define MAX_SIZE 100" in obfuscated
    assert "#define PI 3.14159" in obfuscated
    assert "#define SQUARE" in obfuscated
    # Use sites stay consistent with the preserved macro names
    assert "SQUARE(5)" in obfuscated
    assert "MAX_SIZE" in obfuscated


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

    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)

    # Force use of scanner directly to test the logic
    externals = obfuscator._simple_scanner(code)

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

    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)

    # Obfuscate
    obfuscated = obfuscator.obfuscate(code)

    # Assert obfuscation happened
    assert "val" not in obfuscated
    assert "@mistode:chunk:" in obfuscated

    # Restore
    restored = obfuscator.restore(obfuscated)

    # Assert lossless identity
    assert restored == code


def test_c_obfuscator_numeric_literals_intact():
    """
    Regression: numeric literals must survive as single tokens.
    Previously each digit was split by the single-char fallback branch,
    corrupting e.g. 3.14159 into '3.1 4 1 5 9'.
    """
    code = """
int main() {
    double pi = 3.14159265358979323846;
    int counter = 100;
    int hex_val = 0xFF;
    double sci = 1.5e-3;
    long big = 123456789L;
    unsigned mask = 0b1010;
    return 0;
}
"""

    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    assert "3.14159265358979323846" in obfuscated
    assert "100" in obfuscated
    assert "0xFF" in obfuscated
    assert "1.5e-3" in obfuscated
    assert "123456789L" in obfuscated
    assert "0b1010" in obfuscated


def test_c_obfuscator_cross_instance_restore():
    """
    Regression: restoration must work across processes via embedded
    metadata (fresh MappingManager), not only when the same instance
    still holds the in-memory mapping.
    """
    code = """
#include <stdio.h>

#define PI 3.14159

int main() {
    int counter = 100;
    double area = PI * 2.5;
    printf("%d %f", counter, area);
    return 0;
}
"""

    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    # Obfuscate with a fresh manager (simulates one process/run)
    obfuscator = c.CObfuscator(MappingManager(), NameGenerator())
    obfuscated = obfuscator.obfuscate(code)

    # Metadata must be embedded for key-file-free restoration
    assert "/* @mistode:metadata:" in obfuscated

    # Restore with a *different* fresh manager (simulates a new process/run)
    restored = c.CObfuscator(MappingManager(), NameGenerator()).restore(obfuscated)

    assert restored == code


def test_c_obfuscator_missing_mapping_raises():
    """
    Restoration without any mapping (no metadata, no key) must fail
    loudly instead of silently returning obfuscated names.
    """
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    obfuscator = c.CObfuscator(MappingManager(), NameGenerator())
    obfuscated = obfuscator.obfuscate("int main() { return 0; }")
    # Strip the embedded metadata to simulate a damaged/lost file footer
    obfuscated = obfuscated.split("/* @mistode:metadata:")[0]

    with pytest.raises(ValueError):
        c.CObfuscator(MappingManager(), NameGenerator()).restore(obfuscated)


def test_c_obfuscator_typedef_and_user_types():
    """
    Declarations using user-defined types (struct/typedef aliases) must be
    recognized as definitions so their variables get obfuscated consistently.
    """
    code = """
typedef struct Point Point;
typedef int my_int;
typedef char *string_t;

int main() {
    struct Point p;
    Point q;
    my_int count = 3;
    string_t msg = "hi";
    return 0;
}
"""

    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)

    # Exercise the heuristic scanner directly (gcc/nm would bypass it)
    externals = obfuscator._simple_scanner(code)

    # p/q/count/msg are declared with user-defined types, so they must be
    # classified as defined (internal) symbols, not external ones.
    for name in ("p", "q", "count", "msg"):
        assert name not in externals


def test_c_obfuscator_heuristic_fallback_without_gcc(monkeypatch):
    """
    Regression: when gcc/nm are unavailable, external symbol detection must
    fall back to the heuristic scanner instead of crashing or obfuscating
    external symbols.
    """
    code = """
#include <stdio.h>

int my_func(int a) {
    return a * 2;
}

int main() {
    printf("%d", my_func(10));
    return 0;
}
"""

    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    # Force the heuristic path by pretending gcc/nm are not available
    monkeypatch.setattr(c.shutil, "which", lambda _name: None)

    mm = MappingManager()
    gen = NameGenerator()
    obfuscator = c.CObfuscator(mm, gen)
    obfuscated = obfuscator.obfuscate(code)

    # printf is external (from stdio) and must be preserved
    assert "printf" in obfuscated
    # main is reserved and preserved
    assert "main" in obfuscated
    # my_func is defined and should be obfuscated
    assert "my_func" not in obfuscated


MULTILINE_MACRO_SRC = """\
#include <stdio.h>

#define SWAP(a, b) do { \\
    int tmp = (a); \\
    (a) = (b); \\
    (b) = tmp; \\
} while (0)

int main(void) {
    int x = 1, y = 2;
    SWAP(x, y);
    printf("%d %d\\n", x, y);
    return 0;
}
"""


def test_c_multiline_macro_restores_and_compiles(tmp_path):
    """Chunk comments must not break macro bodies continued with `\\`."""
    import shutil
    import subprocess

    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    obfuscator = c.CObfuscator(MappingManager(), NameGenerator(), "macro.c")
    obfuscated = obfuscator.obfuscate(MULTILINE_MACRO_SRC)

    # Block comments keep the macro valid; `//` would be spliced into the
    # logical line after a continuation backslash.
    assert "/* @mistode:chunk:" in obfuscated

    restored = c.CObfuscator(MappingManager(), NameGenerator(), "macro.c").restore(
        obfuscated
    )
    assert restored == MULTILINE_MACRO_SRC

    if shutil.which("gcc") is None:
        pytest.skip("gcc not available")
    src = tmp_path / "macro.obf.c"
    src.write_text(obfuscated, encoding="utf-8")
    binary = tmp_path / "macro.out"
    compiled = subprocess.run(
        ["gcc", str(src), "-o", str(binary)], capture_output=True, text=True
    )
    assert compiled.returncode == 0, compiled.stderr
    run = subprocess.run([str(binary)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "2 1"


def test_c_quoted_include_is_not_a_symbol():
    """`#include "local.h"` must be one directive token, not `include`."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    code = '#include "local.h"\n#include <stdio.h>\nint main(void){return 0;}\n'
    obfuscator = c.CObfuscator(MappingManager(), NameGenerator(), "inc.c")
    externals = obfuscator._identify_external_symbols(code)
    assert "include" not in externals


def test_c_quoted_include_preserves_header_name():
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    code = '#include "my_header.h"\nint compute(int v){return v;}\n'
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "inc.c").obfuscate(
        code
    )
    assert '#include"my_header.h"' in obfuscated or '#include "my_header.h"' in (
        obfuscated
    )


class TestCPassword:
    """C payloads must honour --password like Python ones."""

    SRC = "#include <stdio.h>\nint compute(int v){return v * 2;}\n"

    def test_roundtrip(self):
        from mistode import c
        from mistode.core import MappingManager, NameGenerator

        obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "p.c").obfuscate(
            self.SRC, encryption_key="s3cret"
        )
        assert "/* @mistode:secure_chunk:" in obfuscated
        assert "/* @mistode:chunk:" not in obfuscated

        restored = c.CObfuscator(MappingManager(), NameGenerator(), "p.c").restore(
            obfuscated, encryption_key="s3cret"
        )
        assert restored == self.SRC

    def test_wrong_password_is_rejected(self):
        from mistode import c
        from mistode.core import MappingManager, NameGenerator

        obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "p.c").obfuscate(
            self.SRC, encryption_key="right"
        )
        with pytest.raises(ValueError, match="Integrity check failed"):
            c.CObfuscator(MappingManager(), NameGenerator(), "p.c").restore(
                obfuscated, encryption_key="wrong"
            )

    def test_missing_password_is_rejected(self):
        from mistode import c
        from mistode.core import MappingManager, NameGenerator

        obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "p.c").obfuscate(
            self.SRC, encryption_key="right"
        )
        with pytest.raises(ValueError, match="File is encrypted"):
            c.CObfuscator(MappingManager(), NameGenerator(), "p.c").restore(obfuscated)


def test_c_typedef_struct_alias_is_collected():
    """`typedef struct { ... } Point;` must yield Point, not a member."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    obfuscator = c.CObfuscator(MappingManager(), NameGenerator(), "t.c")
    code = "typedef struct { int x; int y; } MyPoint;\n"
    sig = [m for m in obfuscator._tokenize(code) if m.group(0).strip()]

    assert obfuscator._collect_user_types(sig) == {"MyPoint"}
    # The alias is defined here, so declarations like `MyPoint p;` are not
    # mistaken for external symbols.
    assert "MyPoint" in obfuscator._scan_defined_symbols(code)


def test_c_typedef_struct_survives_project_mode(tmp_path):
    """Shared typedef'd types must keep one name across files."""
    from mistode.cli import Command, ObfuscationService, Options

    proj = tmp_path / "proj"
    (proj / "inc").mkdir(parents=True)
    (proj / "inc" / "types.h").write_text(
        "typedef struct { int x; int y; } MyPoint;\nint area(MyPoint p);\n",
        encoding="utf-8",
    )
    (proj / "a.c").write_text(
        '#include "types.h"\nint area(MyPoint p){return p.x*p.y;}\n',
        encoding="utf-8",
    )
    (proj / "b.c").write_text(
        '#include "types.h"\nint main(void){MyPoint p={2,3};return area(p);}\n',
        encoding="utf-8",
    )

    out = tmp_path / "proj.obf"
    ObfuscationService(
        Options(command=Command.OBFUSCATE, input_file=proj, output_file=out)
    ).execute()

    header = (out / "inc" / "types.h").read_text(encoding="utf-8")
    a_source = (out / "a.c").read_text(encoding="utf-8")
    assert "MyPoint" in header
    assert "MyPoint" in a_source


def test_c_char_literals_are_not_renamed():
    """`'a'` must stay a character constant, not become an identifier."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    code = (
        "#include <stdio.h>\n"
        "int main(void){\n"
        "    char a = 'a';\n"
        "    if (a == 'a') { printf(\"PASS\\n\"); return 0; }\n"
        "    return 1;\n"
        "}\n"
    )
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "char.c").obfuscate(
        code
    )
    # The variable is renamed, the constant is untouched.
    assert "'a'" in obfuscated
    assert "char a = " not in obfuscated


@pytest.mark.parametrize("literal", ["'a'", "'\\n'", "'\\''", "L'w'", "u8'z'", '"str"'])
def test_c_literals_are_single_tokens(literal):
    from mistode import c

    tokens = [
        m.group(0) for m in c.CObfuscator.TOKEN_PATTERN.finditer(f"x = {literal};")
    ]
    assert literal in tokens


def test_c_hex_float_literals_are_single_tokens():
    """`0x1.8p3` must stay one token; `p3` is not an identifier."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    code = "double d = 0x1.8p3;\ndouble e = 0x1p-5;\n"
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "hex.c").obfuscate(
        code
    )
    assert "0x1.8p3" in obfuscated
    assert "0x1p-5" in obfuscated


@pytest.mark.parametrize(
    "literal",
    ['R"(raw "quoted" ) text)"', 'R"xx(has ) and " inside)xx"', 'R"(plain)"'],
)
def test_cpp_raw_strings_are_single_tokens(literal):
    from mistode import c

    tokens = [
        m.group(0) for m in c.CObfuscator.TOKEN_PATTERN.finditer(f"x = {literal};")
    ]
    assert literal in tokens


MULTILINE_RAW_SRC = """\
#include <stdio.h>
int main(void) {
    const char *s = R"(hello
world)";
    printf("%s\\n", s);
    return 0;
}
"""


def test_c_multiline_raw_string_is_lossless():
    """Tokens spanning lines must not desync the layout queue on restore."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    obfuscator = c.CObfuscator(MappingManager(), NameGenerator(), "raw.cpp")
    obfuscated = obfuscator.obfuscate(MULTILINE_RAW_SRC)
    restored = c.CObfuscator(MappingManager(), NameGenerator(), "raw.cpp").restore(
        obfuscated
    )
    assert restored == MULTILINE_RAW_SRC


def test_c_backslash_continued_string_is_lossless():
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    source = (
        "#include <stdio.h>\n"
        "int main(void) {\n"
        '    const char *s = "hello \\\n'
        'world";\n'
        '    printf("%s\\n", s);\n'
        "    return 0;\n"
        "}\n"
    )
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "ml.c").obfuscate(
        source
    )
    restored = c.CObfuscator(MappingManager(), NameGenerator(), "ml.c").restore(
        obfuscated
    )
    assert restored == source


def test_c_string_macro_keeps_separating_space():
    """`#define MSG "hello"` must not become `#define MSG"hello"`."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    source = "#define MSG \"hello\"\n#define CH 'x'\nint main(void){return 0;}\n"
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "m.c").obfuscate(
        source
    )
    assert '#define MSG "hello"' in obfuscated
    assert "#define CH 'x'" in obfuscated
    assert '#define MSG"hello"' not in obfuscated


def test_c_stdlib_typedefs_and_macros_survive_gcc_path(monkeypatch):
    """`nm -u` cannot see typedefs/macros; they must stay protected."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    code = (
        "#include <stdio.h>\n"
        "#include <stddef.h>\n"
        "int main(void){\n"
        "    size_t len = 10;\n"
        '    FILE *f = fopen("/dev/null", "r");\n'
        '    if (!f) { fprintf(stderr, "e"); return 1; }\n'
        '    printf("%zu", len);\n'
        "    return 0;\n"
        "}\n"
    )
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "s.c").obfuscate(code)
    for name in ("size_t", "FILE", "stderr", "fopen", "printf"):
        assert name in obfuscated, f"{name} must be preserved"


@pytest.mark.parametrize(
    "left,right",
    [
        ("a /", "*b"),  # would open a block comment
        ("+", "+"),  # `a + +1` would become `a++1`
        ("-", "-"),  # `a - -1` would become `a--1`
        ('"%"', "PRIu64"),  # would become "%"PRIu64
    ],
)
def test_c_adjacent_tokens_do_not_fuse(left, right):
    """Tokens that would fuse into comments or ++/-- must stay separated."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    obf = c.CObfuscator(MappingManager(), NameGenerator(), "sp.c")
    assert obf._needs_space(left, right) is True


def test_c_preprocessor_identifiers_are_preserved():
    """`#define` targets and macro parameters are preprocessor contracts."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    source = (
        "#include <stdio.h>\n"
        "#define STR(x) #x\n"
        "#define MAX 100\n"
        "#ifdef DEBUG\n"
        "#define LEVEL 2\n"
        "#endif\n"
        "int main(void){ return MAX; }\n"
    )
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "p.c").obfuscate(
        source
    )
    for name in ("STR", "MAX", "DEBUG", "LEVEL", "x"):
        assert name in obfuscated, f"{name} must be preserved"


def test_c_token_pasting_disables_renaming():
    """`a##b` can synthesise any name, so the file is left unrenamed."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    source = (
        "#include <stdio.h>\n"
        "#define CAT(a,b) a##b\n"
        'int main(void){ int foobar = 7; printf("%d", CAT(foo,bar)); return 0; }\n'
    )
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "t.c").obfuscate(
        source
    )
    assert "foobar" in obfuscated
    assert "CAT(foo,bar)" in obfuscated


def test_c_without_token_pasting_still_renames():
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    source = "int compute(int value){int tmp=value*2;return tmp;}\n"
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "n.c").obfuscate(
        source
    )
    assert "compute" not in obfuscated
    assert "value" not in obfuscated


def test_c_macro_param_shadowing_local_var():
    """宏参数与变量同名时，宏定义内部的参数名不得被改名，避免 #x 产物损坏。"""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    source = (
        "#define TO_STR(x) #x\n"
        "int x = 5;\n"
        "#ifdef DEBUG\n"
        "int flag = 1;\n"
        "#endif\n"
        "int main(void) { return x; }\n"
    )
    obf = c.CObfuscator(MappingManager(), NameGenerator(), "sh.c").obfuscate(source)
    assert "#define TO_STR(x) #x" in obf or "#define TO_STR(x)#x" in obf
    assert "#ifdef DEBUG" in obf
    restored = c.CObfuscator(MappingManager(), NameGenerator(), "sh.c").restore(obf)
    assert restored == source


def test_c_hashhash_in_comments_or_strings_does_not_disable_obfuscation():
    """注释或字符串中的 ## 不能导致整个文件的混淆功能停用。"""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    source = (
        "// Section ##1\n"
        "int calculate(int value) {\n"
        '    printf("Item ##1: %d\\n", value);\n'
        "    return value * 2;\n"
        "}\n"
    )
    obf = c.CObfuscator(MappingManager(), NameGenerator(), "hh.c").obfuscate(source)
    assert "calculate" not in obf
    assert "value" not in obf
    restored = c.CObfuscator(MappingManager(), NameGenerator(), "hh.c").restore(obf)
    assert restored == source


def test_c_increment_operators_stay_intact():
    """`a++` must stay one token, not become `a+ +`."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    source = (
        "#include <stdio.h>\n"
        "int main(void){\n"
        "    int a = 1, b = 2;\n"
        "    a++;\n"
        "    int c = a+++b;\n"
        '    printf("%d %d %d\\n", a, b, c);\n'
        "    return 0;\n"
        "}\n"
    )
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "i.c").obfuscate(
        source
    )
    assert "++;" in obfuscated
    assert "+ +;" not in obfuscated
    restored = c.CObfuscator(MappingManager(), NameGenerator(), "i.c").restore(
        obfuscated
    )
    assert restored == source


@pytest.mark.parametrize(
    "op",
    [
        "++",
        "--",
        "->",
        "<<=",
        ">>=",
        "<<",
        ">>",
        "<=",
        ">=",
        "==",
        "!=",
        "&&",
        "||",
        "+=",
        "-=",
        "*=",
        "/=",
        "%=",
        "&=",
        "|=",
        "^=",
        "::",
    ],
)
def test_c_multi_char_operators_are_single_tokens(op):
    from mistode import c

    tokens = [m.group("op") for m in c.CObfuscator.TOKEN_PATTERN.finditer(f"a {op} b")]
    assert op in tokens


@pytest.mark.parametrize(
    "expr,setup,expected",
    [
        ("a + ++b", "int a=1,b=2;", "+ ++"),
        ("a - --b", "int a=10,b=3;", "- --"),
        ("a++ + b", "int a=1,b=2;", "+++"),
        ("a + +1", "int a=1;", "+ +"),
        ("a++", "int a=1;", "++;"),
    ],
)
def test_c_unary_and_binary_operators_stay_distinct(expr, setup, expected):
    """Re-lexing must not change the expression (`a + ++b` vs `a+++b`)."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    source = f"int main(void){{ {setup} int r = {expr}; return r; }}\n"
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "u.c").obfuscate(
        source
    )
    assert expected in obfuscated
    restored = c.CObfuscator(MappingManager(), NameGenerator(), "u.c").restore(
        obfuscated
    )
    assert restored == source


def test_c_rejects_output_with_changed_token_stream():
    """A spacing bug that merges tokens must fail loudly, not emit bad C."""
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    obfuscator = c.CObfuscator(MappingManager(), NameGenerator(), "v.c")
    source = "int main(void){ int a=1,b=2; int r=a + ++b; return r; }\n"
    broken = "int main(void){int a=1,b=2;int r=a+++b;return r;}\n"
    with pytest.raises(ValueError, match="Refusing to emit C output"):
        obfuscator._verify_token_stream(source, broken)


def test_c_token_stream_survives_tricky_spacing():
    from mistode import c
    from mistode.core import MappingManager, NameGenerator

    source = (
        "#include <stdio.h>\n"
        '#define MSG "hi"\n'
        "int main(void){ int a=1,b=2; a++; int c=a+++b; int d=a + ++b;"
        " int e=a / *(&b); int f=a - -1;"
        ' printf("%d %d %d %d %d %s\\n",a,b,c,d,e,MSG); return 0; }\n'
    )
    # obfuscate() runs the validator internally.
    obfuscated = c.CObfuscator(MappingManager(), NameGenerator(), "v.c").obfuscate(
        source
    )
    restored = c.CObfuscator(MappingManager(), NameGenerator(), "v.c").restore(
        obfuscated
    )
    assert restored == source


@pytest.mark.parametrize("prefix", ["", "u8", "L", "u", "U"])
def test_c_raw_string_prefixes_are_single_tokens(prefix):
    from mistode import c

    literal = f'{prefix}R"(raw)"'
    tokens = [m.group(0) for m in c.CObfuscator.TOKEN_PATTERN.finditer(f"x={literal};")]
    assert literal in tokens
