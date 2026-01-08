# Mistode Examples

This directory contains example code to demonstrate Mistode's obfuscation capabilities.

## Examples

### 1. Python Calculator (`calculator.py`)

A simple calculator module demonstrating:

- Function and class definitions
- Parameter and variable obfuscation
- Preservation of imported modules (`math`, `datetime`)
- Preservation of built-in functions (`print`, `round`, `len`)

**Try it:**

```bash
# Obfuscate with statistics
mistode o calculator.py --stats

# Restore
mistode r calculator.obf.py

# Compare
diff calculator.py calculator.res.py
```

### 2. C Calculator (`calculator.c`)

A simple C program demonstrating:

- Function declarations and definitions
- Variable and struct member obfuscation
- Comment scrambling
- Preservation of preprocessor directives
- Preservation of standard library functions

**Try it:**

```bash
# Obfuscate with statistics
mistode o calculator.c --stats

# Verify it still compiles
gcc calculator.obf.c -o calculator_obf -lm
./calculator_obf

# Restore
mistode r calculator.obf.c

# Compare
diff calculator.c calculator.res.c
```

## Quick Start

1. **Basic obfuscation:**

   ```bash
   mistode o calculator.py
   ```

2. **With custom token style:**

   ```bash
   mistode o calculator.py --style random --length 20
   ```

3. **With statistics:**

   ```bash
   mistode o calculator.py --stats
   ```

4. **Save key file explicitly:**

   ```bash
   mistode o calculator.py --key my_key.json
   ```

5. **Restore:**

   ```bash
   # With embedded metadata (no key needed)
   mistode r calculator.obf.py

   # With explicit key file
   mistode r calculator.obf.py --key my_key.json
   ```

## What Gets Obfuscated?

### Python

✅ Obfuscated:

- User-defined function names
- User-defined class names
- Parameter names
- Local variable names
- Docstrings (replaced with hash)

❌ Preserved:

- Imported module names (`math`, `os`, etc.)
- Imported function names (`datetime.now`, etc.)
- Built-in functions (`print`, `len`, `range`, etc.)
- Built-in methods (`str.format`, `list.append`, etc.)
- Standard library member access

### C

✅ Obfuscated:

- User-defined function names
- User-defined variable names
- User-defined struct/enum/typedef names
- Comments (scrambled)

❌ Preserved:

- Keywords (`if`, `while`, `return`, etc.)
- Preprocessor directives (`#include`, `#define`, etc.)
- Standard library functions (`printf`, `malloc`, etc.)
- String literals

## Tips

1. **Always test the obfuscated code** to ensure it still works correctly
2. **Use `--stats`** to see what was obfuscated
3. **Embedded metadata** allows restoration without keeping key files
4. **Use `--seed`** for reproducible obfuscation (useful for testing)
5. **Compare restored vs original** with `diff` to verify lossless restoration
