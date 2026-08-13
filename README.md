# Mistode

[![PyPI version](https://img.shields.io/pypi/v/mistode.svg?color=blue)](https://pypi.org/project/mistode/)
[![Python versions](https://img.shields.io/pypi/pyversions/mistode.svg)](https://pypi.org/project/mistode/)
[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Tests](https://github.com/for13to1/mistode/actions/workflows/ci.yml/badge.svg)](https://github.com/for13to1/mistode/actions)
[![Coverage](https://codecov.io/gh/for13to1/mistode/branch/main/graph/badge.svg)](https://codecov.io/gh/for13to1/mistode)

**🌐 Languages:**
[![English](https://img.shields.io/badge/English-README-blue)](README.md)
[![中文](https://img.shields.io/badge/中文-README_ZH-red)](README_ZH.md)

Mistode (Mist Code, pronounced like *miss-told*) is a lightweight, advanced code obfuscation tool protecting **Python** and **C** source code. It combines robust AST/Regex parsing with a distributed layout engine to ensure code is unreadable yet fully functional and perfectly restorable.

## Features

- **🛡️ Advanced Obfuscation Engine**:
  - **Encrypted Token Generation**: Configurable token length (8-32 chars) and styles (Similar Characters like `Oo01Il` or Random Alphanumeric).
  - **Smart Deduplication & Validation**: Ensures no collisions and validates generated tokens against language keywords.
  - **Seed Support**: Fully reproducible obfuscation with `--seed`.

- **🐍 Python Support (v3.14+)**:
  - **AST-Based Precision**: Parses the Abstract Syntax Tree for safe and accurate transformation.
  - **Smart Preservation**: Automatically protects imports, built-ins (`print`, `len`), and standard library calls.
  - **Docstring Hiding**: Replaces docstrings with minimal placeholders (restored losslessly from embedded layout data).

- **🇨 C Support**:
  - **Robust Tokenization**: Regex-based engine safely handling macros, pointers, and structs.
  - **Layout Engine**: Preserves complex file structures using distributed `// @mistode:chunk:` markers.
  - **Symbol Safety**: Automatically preserves keywords, preprocessor directives, and standard headers.

- **🔄 Zero-Loss Restoration**:
  - **Distributed Layout Data**: Layout data (whitespace, comments, and
    string contents) is compressed and distributed throughout the
    obfuscated file as comments (base64 by default, encrypted with
    `--password`).
  - **Embedded Metadata**: Identifier mappings are embedded directly in the file footer. **No key file is required for restoration.**
  - **Bit-Perfect Restore**: Restores every byte of the original code, including comments, formatting, and empty lines.

- **⚙️ Modern Tooling**:
  - **Configuration File**: Global defaults via `pyproject.toml`.
  - **Detailed Statistics**: `--stats` flag provides identifier counts, preserved-name counts, and file-size analysis.

## Installation

> [!IMPORTANT]
> Mistode requires **Python 3.14** or higher.

```bash
pip install mistode
```

## Quick Start

### 1. Python Example

```bash
# Obfuscate 'app.py' (generates app.obf.py)
mistode o app.py --stats

# Restore to original (generates app.res.py)
# No key file needed - uses embedded metadata!
mistode r app.obf.py

# Verify match
diff app.py app.res.py
```

### 2. C Example

```bash
# Obfuscate 'main.c' (generates main.obf.c)
mistode o main.c --stats

# Compile and run obfuscated code
gcc main.obf.c -o main_obf
./main_obf

# Restore
mistode r main.obf.c
```

## Usage Guide

### Command Line Interface

```bash
# General Syntax
mistode [command] [file] [options]

# Commands
o, obf, obfuscate   Obfuscate a file
r, res, restore     Restore a file
```

### Common Options

| Option | Alias | Description |
| :--- | :--- | :--- |
| `--out` | `-o` | Specify output filename. |
| `--key` | `-k` | Specify key file path (optional, as metadata is embedded). |
| `--stats` | | Show detailed statistics after processing. |
| `--style` | | `similar` (default) or `random`. |
| `--length` | `-l` | Token length (8-32). |
| `--seed` | `-s` | Random seed for reproducibility. |
| `--password` | `-p` | Password for encryption/decryption. |

### Configuration File (`pyproject.toml`)

You can define project-wide defaults in `pyproject.toml`. Mistode automatically looks for this file in the current and parent directories.

```toml
[tool.mistode]
style = "similar"    # "similar" (Io01) or "random" (aB3d)
length = 24          # Stronger tokens
stats = true         # Always show stats
seed = 12345         # Deterministic builds
```

For a detailed guide, see [examples/CONFIG_GUIDE.md](examples/CONFIG_GUIDE.md).

## What Gets Obfuscated?

### Python

| Component | Status | Notes |
| :--- | :---: | :--- |
| **Variable Names** | ✅ | Replaced with tokens |
| **Function/Class Names** | ✅ | Replaced with tokens |
| **Docstrings** | ✅ | Replaced with placeholders (restored losslessly) |
| **Imports** | ❌ | Preserved (`import math`) |
| **Built-ins** | ❌ | Preserved (`print`, `len`) |
| **Stdlib Methods** | ❌ | Preserved (`os.path.join`) |

### C / C++

| Component | Status | Notes |
| :--- | :---: | :--- |
| **Functions** | ✅ | User-defined only |
| **Variables/Structs** | ✅ | Local and Global |
| **Comments** | ✅ | Hidden in obfuscated output (restored losslessly) |
| **Keywords** | ❌ | Preserved (`if`, `while`) |
| **Preprocessor** | ❌ | Preserved (`#include`, `#define`, macro names) |
| **Std Lib** | ❌ | Preserved (`printf`, `malloc`) |

## Restoration Mechanics

Mistode uses a **dual-layer restoration system** to guarantee safety:

1. **Distributed Layout Data (Primary)**:
    Layout data (whitespace, comments, and string contents) is compressed and injected as comments (e.g., `#@mistode:chunk:...`) throughout the file. This allows **100% bit-perfect restoration**.

2. **Embedded Mappings (Secondary)**:
    The renaming map is compressed and embedded in the file footer (`#@mistode:metadata:`). If chunks are damaged, this allows functional restoration.

3. **Key File (Optional)**:
    You can explicitly save the mapping to a JSON file with `--key`, but it is not required for standard workflows.

## Known Limitations

- **Dynamic access is not tracked**: names accessed via strings
  (`globals()[...]`, `setattr`, `getattr(obj, "name")`, pickling)
  cannot be renamed consistently. Such patterns are the standard
  limitation of identifier-renaming obfuscators.
- **External references are the public contract**: names exported via
  `__all__` and names used across files (imported or called from other
  modules) are preserved, not obfuscated.
- **C heuristic mode**: without `gcc`/`nm` on `PATH`, external symbol
  detection falls back to a heuristic scanner that is conservative
  (it may obfuscate less, never more than is safe).
- **Obfuscation is not encryption**: embedded metadata and source
  chunks allow full restoration by anyone with the tool. `--password`
  adds obfuscation-grade protection of the embedded data, not
  cryptographic security.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

This project is licensed under the [GPLv3 License](LICENSE).
