# Mistode

[![PyPI version](https://img.shields.io/pypi/v/mistode.svg?color=blue)](https://pypi.org/project/mistode/)
[![Python versions](https://img.shields.io/pypi/pyversions/mistode.svg)](https://pypi.org/project/mistode/)
[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Tests](https://github.com/for13to1/mistode/actions/workflows/ci.yml/badge.svg)](https://github.com/for13to1/mistode/actions)
[![Coverage](https://codecov.io/gh/for13to1/mistode/branch/main/graph/badge.svg)](https://codecov.io/gh/for13to1/mistode)

**🌐 Languages:**
[![English](https://img.shields.io/badge/English-README-blue)](README.md)
[![中文](https://img.shields.io/badge/中文-README_ZH-red)](README_ZH.md)

Mistode (Mist Code, pronounced like *miss-told*) is a code obfuscation tool for **Python** and **C** source. It combines AST/regex parsing with a distributed layout engine, making the delivered code hard to read, runnable as-is, and fully restorable with the key.

## Features

- **🛡️ Advanced Obfuscation Engine**:
  - **Randomized Token Generation**: Configurable token length (8-32 chars) and styles (Similar Characters like `Oo01Il` or Random Alphanumeric).
  - **Deduplication & Validation**: tokens are guaranteed collision-free and validated against language keywords.
  - **Seed Support**: Fully reproducible obfuscation with `--seed`.

- **🔐 Key-Gated Restoration** (`--password`):
  - **Authenticated stream cipher** built from the standard library: `scrypt` key stretching, SHA-256 CTR keystream, HMAC-SHA256 tag (encrypt-then-MAC).
  - **No keystream reuse**: the nonce is derived from each payload, so a known plaintext cannot unlock the rest of the file.
  - **Deterministic**: identical input and password produce identical output, so reproducible builds remain possible.
  - **Cipher is configurable**: `--cipher stream` (default) or `--cipher none` (plain base64).

- **🐍 Python Support (v3.14+)**:
  - **AST-Based Precision**: parses the syntax tree so renaming is safe and accurate.
  - **Selective Preservation**: automatically protects imports, built-ins (`print`, `len`), stdlib calls, `__all__` exports, keyword-argument names, `main` (so `console_scripts` and `python -m` keep working) and attribute names.
  - **Docstring Hiding**: replaces docstrings with minimal placeholders, restored losslessly from embedded layout data.

- **🇨 C Support**:
  - **Robust Tokenization**: a regex engine that reliably handles macros, pointers, structs, and both `#include <...>` and `#include "..."`.
  - **Layout Engine**: preserves complex file structures with distributed `/* @mistode:chunk:... */` block-comment markers, which remain valid after line-continuation backslashes in multi-line macros.
  - **Symbol Safety**: automatically preserves keywords, preprocessor directives and standard headers. `gcc`/`nm` probing (with the source directory on the include path) is preferred when available; otherwise a conservative heuristic scanner is used.

- **🔄 Zero-Loss Restoration**:
  - **Distributed Layout Data**: layout data (whitespace, comments, docstrings, original newlines) is compressed into interleaved chunk comments (plain base64 by default, encrypted with `--password`).
  - **Embedded Metadata**: identifier mappings are embedded directly in the file footer. **No key file is required for restoration.**
  - **Bit-Perfect Restore**: restores every byte of the original code, including comments, formatting, CRLF and empty lines.

- **📦 Self-Contained Deliverables**:
  - **Project (directory) mode** mirrors the whole tree, keeping original filenames so imports/includes still resolve.
  - **Non-source files are copied** by default (`--assets copy`), including templates, data files and configs, so the project runs without further setup; `--assets-skip-secrets` skips `.env`, `*.pem` and similar files.

- **⚙️ Modern Tooling**:
  - **Configuration File**: Global defaults via `pyproject.toml` (style, length, seed, cipher, assets...).
  - **Detailed Statistics**: `--stats` reports identifier counts, preserved-name counts and file-size analysis.

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

### 3. Password-Protected Delivery

```bash
# Obfuscate with a delivery key
mistode o app.py --password "$DELIVERY_KEY"

# The artifact runs without the key
python app.obf.py

# Restore from the artifact
mistode r app.obf.py --password "$DELIVERY_KEY"
```

### 4. Project (Directory) Mode

Pass a directory instead of a single file to obfuscate a whole project:

```bash
# Obfuscate src/ into src.obf/ (mirrored tree, original filenames kept
# so imports/includes still resolve; cross-file references are preserved)
mistode o src/

# Run the obfuscated project directly (Python)
python src.obf/app.py

# Or compile it (C)
gcc -Isrc.obf src.obf/main.c src.obf/util.c -o app

# Non-source assets (templates, data, configs) are copied by default so
# the output is runnable; inspect or disable that with:
mistode o src/ --assets list
mistode o src/ --assets skip

# Restore the whole project byte-identically
mistode r src.obf/   # produces src.res/
```

Project mode handles cross-file references automatically: names imported via `from mod import name` (Python) and symbols shared across compilation units (C) are preserved in every file, so the obfuscated project remains runnable and compilable.

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
| `--key` | `-k` | Write/read the identifier mapping as a JSON file (optional; embedded metadata is the default source). |
| `--stats` | | Show detailed statistics after processing. |
| `--style` | | `similar` (default) or `random`. |
| `--length` | `-l` | Token length (8-32). |
| `--seed` | `-s` | Random seed for reproducibility. |
| `--password` | `-p` | Password that gates restoration of encrypted payloads. |
| `--cipher` | | `stream` (default with `--password`) or `none`. |
| `--aggressive-methods` | | Also rename class methods whose receivers are only `self` / the class name. |
| `--assets` | | Whether to copy non-source files: `copy` (default), `skip`, `list`. |
| `--assets-skip-secrets` | | Do not copy `.env`, `*.pem`, `*.key` and similar files. |

### Configuration File (`pyproject.toml`)

Project-wide defaults can be defined in `pyproject.toml`; Mistode searches the current and parent directories.

```toml
[tool.mistode]
style = "similar"          # "similar" (Io01) or "random" (aB3d)
length = 24                # Stronger tokens
stats = true               # Always show stats
seed = 12345               # Deterministic builds
cipher = "stream"          # Payload cipher (requires --password)
assets = "copy"            # Copy non-source files
assets_skip_secrets = false
```

For a detailed guide, see [examples/CONFIG_GUIDE.md](examples/CONFIG_GUIDE.md).

## What Gets Obfuscated?

### Python

| Component | Status | Notes |
| :--- | :---: | :--- |
| **Variable Names** | ✅ | Replaced with tokens |
| **Function/Class Names** | ✅ | Replaced with tokens |
| **Docstrings** | ✅ | Replaced with placeholders (restored losslessly) |
| **`main`** | ❌ | Preserved (entry point for `console_scripts` / `python -m`) |
| **`__all__` exports** | ❌ | Preserved (public API) |
| **Keyword-argument names** | ❌ | Preserved (callers pass them by name) |
| **Attribute names** | ❌ | Preserved (`obj.attr` is never renamed) |
| **Imports** | ❌ | Preserved (`import math`) |
| **Built-ins** | ❌ | Preserved (`print`, `len`) |
| **Stdlib Methods** | ❌ | Preserved (`os.path.join`) |

### C / C++

| Component | Status | Notes |
| :--- | :---: | :--- |
| **Functions** | ✅ | User-defined only |
| **Variables/Structs** | ✅ | Local and Global |
| **Comments** | ✅ | Hidden in obfuscated output (restored losslessly) |
| **Multi-line macros** | ✅ | Chunk markers use block comments so `\` continuations survive |
| **Keywords** | ❌ | Preserved (`if`, `while`) |
| **Preprocessor** | ❌ | Preserved (`#include`, `#define`, macro names) |
| **Std Lib** | ❌ | Preserved (`printf`, `malloc`) |

## Restoration Mechanics

Restoration data travels inside the artifact; the password is the only external secret.

1. **Distributed Layout Data (Primary)**: Layout data (whitespace, comments, docstrings, original newlines) is compressed and injected as comments throughout the file (`#@mistode:chunk:` / `/* @mistode:chunk: */` for C). This is what makes **100% bit-perfect restoration** possible.

2. **Embedded Mappings (Secondary)**: The renaming map is compressed into the file footer (`#@mistode:metadata:`).

3. **Password (Key)**: With `--password`, both payload kinds are stored as `secure_chunk` / `secure_metadata`: scrypt-derived key, per-payload nonce, HMAC tag. A missing or wrong password fails explicitly.

4. **Key File (Optional)**: `--key` writes the identifier mapping to JSON. Useful for auditing or restoring when the embedded metadata was stripped; it is not required for the normal workflow.

## Known Limitations

- **Dynamic access is not tracked**: names accessed via strings (`globals()[...]`, `setattr`, `getattr(obj, "name")`, pickling) cannot be renamed consistently. Such patterns are the standard limitation of identifier-renaming obfuscators.
- **External references are the public contract**: names exported via `__all__` and names used across files (imported or called from other modules) are preserved, not obfuscated.
- **C heuristic mode**: without `gcc`/`nm` on `PATH`, external symbol detection falls back to a conservative heuristic scanner. On machines where `gcc` is available, its `nm -u` output is unioned with that scan, so more names are treated as external and fewer are renamed.
- **Obfuscation is not end-to-end secrecy**: string literals, numeric constants and control flow stay readable. Obfuscation raises the cost of understanding the code; it does not hide business logic completely.
- **`--password` protects the restoration data, not the code**: an attacker without it can still read the obfuscated source, just not restore it. Use a long, unique passphrase; `scrypt` raises the cost of offline guessing but cannot rescue a weak one.
- **Encrypted output is still plain `.py`/`.c`**: the password protects restoration, not execution.
- **Docstrings are removed from the artifact**: they are stored in the restoration payload, so `__doc__` is empty at runtime and `help()` / Sphinx / `doctest` see no documentation until the file is restored.
- **`--cipher stream` requires `--password`**: a missing password is an
  error, not a silent downgrade to plaintext.
- **KDF salt is fixed** (`mistode-kdf-v1`): the same passphrase derives the same key everywhere. Required for reproducible builds; the trade-off is that precomputation transfers across installations, so passphrase strength matters more.
- **Legacy payloads**: files encrypted by Mistode <= 0.1.3 (no nonce/tag) fail authentication with an explicit error; re-obfuscate them with the current release.
- **Token pasting disables renaming**: a file using `##` is left unrenamed, because the preprocessor can synthesise any identifier.
- **Rename rate is limited**: dynamic features (attribute access, star imports, keyword arguments, reflection) make many names external contracts. On this project's own source, ~45% of eligible names are renamed in single-file mode and ~36% in project mode; real-world code with more cross-module surface is lower.
- **`--aggressive-methods` is unsafe for libraries**: it renames class methods whose receivers are provably local (`self`/class name). External callers reach methods by name, so libraries can break; use it only for self-contained code.
- **`--key` is ignored in project mode for restore**: project artifacts carry per-file metadata; restore from it directly (a combined key is written on obfuscation for auditing, but restore rejects `--key` to avoid ambiguous per-file mappings).

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

This project is licensed under the [GPLv3 License](LICENSE).
