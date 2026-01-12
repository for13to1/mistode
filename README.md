# Mistode

[![PyPI version](https://img.shields.io/pypi/v/mistode.svg?color=blue)](https://pypi.org/project/mistode/)
[![Python versions](https://img.shields.io/pypi/pyversions/mistode.svg)](https://pypi.org/project/mistode/)
[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Tests](https://github.com/for13to1/mistode/actions/workflows/ci.yml/badge.svg)](https://github.com/for13to1/mistode/actions)
[![Coverage](https://codecov.io/gh/for13to1/mistode/branch/main/graph/badge.svg)](https://codecov.io/gh/for13to1/mistode)

**🌐 Languages:**
[![English](https://img.shields.io/badge/English-README-blue)](README.md)
[![中文](https://img.shields.io/badge/中文-README_ZH-red)](README_ZH.md)

Mistode (Mist Code, pronounced like "Miss Told") is a lightweight code obfuscation tool supporting Python and C. It focuses on making code difficult to read while maintaining functional integrity.

## Features

- **Encrypted Token Generator**: Highly customizable encrypted token generation supporting various configurations:
  - **Random Seed**: Supports setting a random seed to ensure reproducibility.
  - **Length Control**: Custom token length, range [8, 32] characters.
  - **Style Configuration**: Supports two obfuscation styles:
    - **Similar Character Style**: Uses visually similar character groups to enhance obfuscation (e.g., `Oo0`, `iIlL1`, `b6B8`, `Zz2`, `Ss5`).
    - **Random Character Style**: Uses random alphanumeric combinations.
  - **Smart Deduplication**: Automatically maintains a set of generated tokens to avoid duplicates.
- **Python Support**:
  - **AST Parsing**: Accurate obfuscation based on Abstract Syntax Trees, ensuring complete preservation of code format.
  - **Smart Identifier Classification**: Automatically identifies and preserves imported modules, functions, and built-in methods.
  - **Docstring Obfuscation**: Replaces docstrings with hash values.
  - **Fully Reversible**: Supports full restoration using generated key files or embedded metadata.
  - **Lossless Restoration**: Achieves lossless consistency with the original file (preserving all comments and formatting) via distributed annotated injection of source chunks.
- **C Support**:
  - **Fast Tokenization**: Uses robust regular expression tokenizers.
  - **Layout Engine**: Uses `// @mistode:chunk:` metadata to preserve code structure.
  - **Compilation Safety**: Preserves keywords, preprocessor directives, and external symbols.
  - **Lossless Restoration**: Achieves lossless consistency with the original file via distributed layout chunks.

## Installation

```shell
pip install mistode
```

## Usage

### Simple Usage (Default Settings)

```shell
# Obfuscate (generates input.obf.py and input.map.json)
mistode o input.py

# Restore (automatically detects input.map.json if naming matches)
# Generates input.res.py
mistode r input.obf.py
```

### Full Usage

```shell
# Obfuscate with explicit options
mistode obfuscate input.py --out output.py --key mapping.json

# Restore with explicit options
mistode restore output.py --out restored.py --key mapping.json
```

### Configuration File

You can set default options in `pyproject.toml` to avoid repeating the same arguments:

```toml
[tool.mistode]
style = "similar"    # Default obfuscation style ("similar" or "random")
length = 16          # Default token length (8-32)
stats = true         # Always show statistics
# seed = 42          # Optional: set a default seed for reproducibility
```

**How it works**:

- Mistode automatically searches for `pyproject.toml` in the current directory and parent directories
- If found, settings from `[tool.mistode]` are used as defaults
- Command-line arguments always override configuration file settings

**Example**:

```bash
# With the config above, these are equivalent:
mistode o input.py
mistode o input.py --style similar --length 16 --stats

# Override config with command-line args:
mistode o input.py --style random --length 20
```

For a complete guide, see [`examples/CONFIG_GUIDE.md`](examples/CONFIG_GUIDE.md).

## Advanced Features

### Smart Identifier Recognition for Python Obfuscation

Mistode intelligently identifies and avoids obfuscating the following types of identifiers:

- **Built-in Modules**: `re`, `os`, `sys`, `json`, `math`, etc.
- **Built-in Functions**: `print`, `len`, `range`, `str`, `int`, etc.
- **Imported Functions**: Functions imported via `import` and `from ... import` statements.
- **Built-in Methods**: `re.sub`, `str.strip`, `list.append`, etc.

### Example

**Original Code**:

```python
import re
from openpyxl.utils import get_column_letter, column_index_from_string

def shift_column_letter(base_column, offset):
    """Calculate the shifted column letter based on the given column letter and offset"""
    base_idx = column_index_from_string(base_column)
    target_idx = base_idx + offset
    return get_column_letter(target_idx)
```

**Obfuscated Code**:

```python
import re
from openpyxl.utils import get_column_letter, column_index_from_string

#@mistode:chunk:eJzjSklNU8hIzcnJ11BQyEvMTVVQ0LTiU...
def Oo0iIlL1b6B8Zz2Ss5(Oo0iIlL1b6B8Zz2Ss6, Oo0iIlL1b6B8Zz2Ss7):
    """Obfuscated docstring: e2d30883ac53"""
#@mistode:chunk:aVaCikKXmAdOkoVEO01SopaCoogFWAiQo...
    Oo0iIlL1b6B8Zz2Ss8 = column_index_from_string(Oo0iIlL1b6B8Zz2Ss6)
    Oo0iIlL1b6B8Zz2Ss9 = Oo0iIlL1b6B8Zz2Ss8 + Oo0iIlL1b6B8Zz2Ss7
    return get_column_letter(Oo0iIlL1b6B8Zz2Ss9)
#@mistode:metadata:eJxVk1Fr3DAMx79K...
```

### Embedded Metadata & Distributed Source

Mistode uses a two-layer restoration mechanism:

1. **Distributed Source Chunks (`#@mistode:chunk:` or `// @mistode:chunk:`)**: The original source code is compressed, encoded, and injected as chunks before each line of the obfuscated code. Restoration prioritizes these chunks to reconstruct the original code, achieving **lossless restoration** (including all comments, empty lines, and formatting).
2. **Embedded Metadata (`#@mistode:metadata:`)**: Contains the identifier mapping table as a backup restoration method.

This means you can perfectly restore the original code even without keeping the key file.

```python
# ... Obfuscated Code ...
#@mistode:chunk:eJzjSk... (Distributed Source Chunk)
# ...
#@mistode:metadata:eJxVk1... (Base64 Encoded Mapping)
```

If no key file is provided, the restore command automatically detects and uses this metadata.

## Project Structure

```shell
mistode/
├── src/
│   └── mistode/
│       ├── __init__.py      # Package Initialization
│       ├── cli.py           # Command Line Interface
│       ├── python.py        # Python Obfuscator (mistode.python)
│       ├── c.py             # C Obfuscator (mistode.c)
│       └── core.py          # Core Functionality (mistode.core)
├── tests/                   # Tests Directory
│   ├── __init__.py
│   ├── test_python.py       # Python Obfuscator Tests
│   ├── test_c.py            # C Obfuscator Tests
│   ├── test_cli.py          # CLI Tests (Integration)
│   ├── test_cli_unit.py     # CLI Tests (Unit)
│   └── test_core.py         # Core Functionality Tests
├── pyproject.toml           # Project Configuration
└── README.md                # Project Documentation
```

## Development

### Running Tests

```shell
python -m pytest tests/
```

### Building the Package

```shell
pip install build
python -m build
```
