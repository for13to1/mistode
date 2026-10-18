# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Configurable payload cipher** (`--cipher` / `[tool.mistode] cipher`):
  - `stream` (default when a password is given): authenticated stream
    cipher from stdlib primitives - `scrypt` key derivation, SHA-256 CTR
    keystream, HMAC-SHA256 tag (encrypt-then-MAC).
  - `none`: plain base64 payloads.
  - The nonce is derived per payload (SIV-style), so distinct payloads
    never share a keystream while identical input still produces identical
    output (reproducible builds keep working).
  - Works for both Python and C; C previously ignored `--password`
    entirely.
- Project (directory) mode: `mistode o <dir>` obfuscates a whole project
  into a mirrored tree (e.g. `src/` -> `src.obf/`) keeping original
  filenames so imports/includes keep working, and `mistode r <dir>`
  restores it byte-identically
- Cross-file reference preservation in project mode: names imported via
  `from mod import name` (Python) and symbols shared across compilation
  units (C) keep their names in every file
- **Non-source assets are mirrored by default** (`--assets copy|skip|list`):
  templates, data files and configs are copied so the obfuscated project
  stays runnable. Credential-looking files (`.env`, `*.pem`, `*.key`) are
  copied by default; `--assets-skip-secrets` leaves them out.
- `--aggressive-methods` now also applies in single-file mode (it was only
  read in directory mode).
- `project.py`: project scanning, asset mirroring and cross-file analysis
  extracted from the CLI.

### Changed

- Python `main` is always preserved, so `console_scripts` entries and
  `python -m` keep working on obfuscated code.
- Cross-file attribute collection now records every `ast.Attribute`
  (including chained accesses such as `sub.mod.timeout()`), not only
  single-level `a.b`; this trades a slightly lower rename rate for not
  breaking working code.
- C chunk markers use block comments (`/* @mistode:chunk: ... */`) and
  carry a trailing backslash inside multi-line macros, so macro bodies are
  no longer swallowed by the preprocessor.
- `CObfuscator.obfuscate()` accepts `source_dir`, passed to `gcc` as `-I`
  so `#include "local.h"` resolves during symbol probing.
- Project-mode restore rejects `--key` with an explicit error instead of
  silently ignoring it; obfuscation writes a combined key for auditing.
- Generated tokens are validated with `keyword.iskeyword()` (README
  previously claimed this but the check did not exist).
- The seven PEP 758 bare `except A, B:` clauses now use the explicit
  parenthesised form; ruff targets py313 so the formatter preserves it.
  `requires-python` stays at `>=3.14`.

### Fixed

- Multi-character C operators (`++`, `--`, `->`, `<<`, `>>`, `+=`, `&&`,
  `::`, ...) are tokenised as single tokens. Previously `a++` was split into
  `a` `+` `+` and re-emitted as `a+ +`, which does not compile.
- `+`/`-` spacing keeps unary and binary forms distinct: `a + ++b` no longer
  becomes `a+++b`, which C re-lexes as `(a++) + b`.
- C obfuscation now verifies its own output: the emitted code is
  re-tokenised and compared with the source. A spacing bug that merges or
  splits tokens (`a + ++b` -> `a+++b`) fails loudly instead of producing
  silently different behaviour.
- Obfuscating large files is linear again: the layout engine split the
  source once per token, making a 9,600-line file take ~12s (now ~0.3s).
  Identifier definition lookup also uses binary search over token lines.
- `--cipher stream` without `--password` is now a usage error instead of
  silently producing plaintext payloads.
- Payloads from Mistode <= 0.1.3 (no nonce/tag) are reported as such instead
  of failing with a misleading integrity error.
- Encrypted files restored with a mismatched `--cipher` now say so instead
  of claiming no password was given.
- Added compile-and-run end-to-end tests for C (operators, macros, literals,
  stdlib types) that compare the behaviour of original and obfuscated
  binaries.
- Identifiers on preprocessor directive lines (`#define`, `#ifdef` targets,
  macro parameters) are no longer renamed: they are contracts the
  preprocessor resolves, so renaming silently changed behaviour.
- A file using token pasting (`a##b`) is left unrenamed. Pasting can
  synthesise any identifier at expansion time, which static analysis cannot
  predict, so renaming would break the build.
- C external-symbol detection unions `gcc`/`nm` output with the heuristic
  scan. `nm -u` cannot see typedefs (`size_t`, `FILE`) or macros (`stderr`,
  `NULL`) because the preprocessor resolves them, so on machines with gcc
  installed those names were renamed and the output failed to compile.
- C output keeps a space between `+`/`+`, `-`/`-`, `/`/`*`, and between a
  literal and a following identifier, so `a + +1`, `a / *b` and
  `"%" PRIu64` are not rewritten into `a++1`, `a/*b` or `"%"PRIu64`.
- C output keeps a space between a word-like token and a following string
  or character literal, so `#define MSG "hello"` no longer collapses to
  `#define MSG"hello"` (invalid under `-Werror`).
- C restore now tokenises the whole cleaned stream instead of one line at a
  time. Tokens that span lines (multi-line raw strings, backslash
  continuations) previously split into fragments, desynced the layout queue
  and corrupted the rest of the file on restoration.
- C hexadecimal floating constants (`0x1.8p3`) are tokenised as one number;
  previously the `p3` exponent was read as an identifier and renamed, so
  the file failed to compile.
- C++ raw string literals (`R"(...)"`, `R"delim(...)delim"`) are tokenised
  as one literal so their contents are never scanned as code.
- C token groups are now named (`ident`, `literal`, `number`, ...) so adding
  a pattern alternative cannot silently shift group indices.
- C character constants (`'a'`, `'\n'`, `L'w'`, `u8'z'`) are tokenised as
  literals instead of quote + identifier. Previously the inner letter could
  be renamed, turning `'a'` into a multi-character constant: `-Werror`
  builds failed and `if (c == 'a')` silently became always-false.
- Star imports are now resolved for absolute (`from utils import *`) and
  package (`from . import *`) forms, not only relative `from .mod import *`.
  Previously the target module's public names were not protected, so the
  same function got two different obfuscated names and the project raised
  `NameError` at runtime.
- Directory restore now mirrors non-source assets back, so a restored
  project is complete (obfuscation already copied them forward).
- C `typedef struct { ... } Alias;` now records `Alias` (and not a struct
  member) as the alias, and typedef aliases count as definitions. Shared
  types in headers keep one name across translation units instead of
  failing to compile with `unknown type name`.
- Layout restoration re-raises `ValueError` from decryption, so a wrong or
  missing password reports the integrity failure instead of the unrelated
  "file does not appear to be obfuscated" message.
- C restore also skips the `secure_metadata` line explicitly rather than
  relying on it being a trailing comment.
- `PythonObfuscator.restore()` no longer empties the output when the
  artifact has no embedded metadata: metadata stripping now matches the
  exact `#@mistode:metadata:` / `#@mistode:secure_metadata:` markers with
  `rfind`, instead of the bare `#@mistode:` prefix that hit the first chunk
  at offset 0.
- `--key` no longer writes an empty mapping for Python files (the CLI was
  overwriting the mapping the obfuscator had already written), and an
  empty key no longer suppresses fallback to embedded metadata - the
  previous behaviour printed `OK` while restoring nothing.
- `#include "..."` is tokenised as a directive, so `include` no longer
  leaks into the external-symbol set as a bogus symbol.
- Cross-file import/symbol analysis now reads files with their detected
  encoding (previously UTF-8-only reads silently skipped non-UTF-8 files,
  breaking cross-file references in GBK/Big5 projects)
- Syntax errors in Python sources now produce a friendly error message
  instead of a raw traceback

## [0.1.3] - 2026-08-14

### Added

- C obfuscator now recognizes user-defined types (struct/union/enum names
  and typedef aliases) during heuristic external-symbol discovery, so
  declarations like `Point q;` are obfuscated instead of being mistaken
  for external symbols
- CLI end-to-end tests (real subprocess, fresh MappingManager) covering
  Python/C lossless restore and C compilation via gcc
- Layout edge-case tests (nested f-strings, hashes inside strings,
  multiline strings, async/comprehensions, docstring variants) with
  functional-equivalence assertions
- Encryption (`--password`) and `--seed` determinism end-to-end tests

### Changed

- Support non-UTF-8 encodings (GBK, Big5, Shift_JIS, UTF-16/32, BOM):
  encoding is auto-detected, obfuscated output is always UTF-8 (so it
  stays executable/compilable), and restoration writes back in the
  original encoding for byte-identical output
- Preserve CRLF line endings end-to-end for bit-perfect restoration
  (previously `\r` was normalized away on read)
- Preserve names declared in module-level `__all__` so library exports
  survive obfuscation
- Migrate lint/format tooling from black/isort/flake8 to ruff
  (single config, single CI step)
- Modernize typing for the 3.14 floor (built-in generics, `X | None`,
  `tokenize.FSTRING_START/END` without getattr fallback)
- README/README_ZH now describe the actual layout-engine mechanism and
  document known limitations

### Fixed

- C numeric literals were split into per-character tokens (`3.14159`
  became `3.1 4 1 5 9`), making obfuscated C uncompilable; added a
  numeric group to the tokenizer regex
- C restoration across processes failed because the identifier mapping
  was never embedded in the obfuscated output (and the embedded
  metadata was not zlib-decompressed on read); mapping metadata is now
  embedded and parsed correctly
- `--stats` reported 0 identifiers for Python because it read the
  wrong mapping source
- C macro names following `#define` were obfuscated despite the
  documented "Preprocessor Preserved" guarantee
- AST column offsets (UTF-8 byte offsets) are now converted to tokenize
  character offsets, so identifiers after multibyte characters (CJK)
  are renamed consistently
- PEP 263 coding declarations were lost during obfuscation; the
  original encoding is now carried in the metadata
- Empty-but-valid identifier mappings (files with no obfuscatable
  names) no longer fail restoration

## [0.1.2] - 2026-01-12

### Changed

- Drop support for Python < 3.14 (was >=3.10, now >=3.14)
- Enhance token generation robustness and add input validation
  - Enhanced encryption validation with type and length checks
  - Improved name generator collision handling with increased attempts and smart length adjustment
  - Added homograph detection to prevent visually similar character confusion
  - Strengthened boundary condition handling and validation
- Implement layout engine for lossless restoration and improve symbol detection for C code
- Add advanced layout engine and encryption support

## [0.1.1] - 2026-01-08

### Added

- **CLI Improvements**:
  - `--version` flag to display version and Python version information
  - `--stats` flag for detailed obfuscation statistics
    - Shows identifier counts (obfuscated vs preserved)
    - Displays file size changes
    - Indicates restoration method (key file vs embedded metadata)
  - Configuration file support via `pyproject.toml`
    - Set default values for `style`, `length`, `seed`, and `stats`
    - Uses `[tool.mistode]` section
    - Automatically searches current and parent directories

- **Examples Directory**:
  - Added `examples/` with comprehensive sample code
  - Python calculator example (`calculator.py`)
  - C calculator example (`calculator.c`)
  - Detailed usage documentation in `examples/README.md`

- **Documentation**:
  - Created comprehensive example usage guide
  - Added configuration file documentation

### Changed

- **Enhanced Error Messages**:
  - User-friendly error formatting with emoji icons (❌ for errors, 💡 for hints)
  - Specific troubleshooting hints for common issues
  - Better handling of file not found, permission denied, and encoding errors
  - Improved key file error messages with suggestions

### Fixed

- Fixed installation command in `README_ZH.md` (changed from `pip install .` to `pip install mistode`)

## [0.1.0] - 2026-01-08

### Added

- Python code obfuscation with AST-based transformation
  - Variable, function, and class name obfuscation
  - Docstring obfuscation
  - Smart identifier classification (preserves imports and built-ins)
  - **Lossless restoration** via embedded source chunks
  - Embedded metadata support for key-free restoration

- C code obfuscation with regex-based tokenization
  - Identifier renaming (variables, functions, structs)
  - Comment scrambling
  - Dynamic external symbol discovery (using gcc/nm)
  - Heuristic fallback for symbol detection
  - **Lossless restoration** via embedded source chunks
  - Embedded metadata support for key-free restoration

- Name generator with configurable options
  - Two styles: `similar` (visually confusing chars) and `random`
  - Configurable length (8-32 characters)
  - Seed support for reproducibility
  - Smart deduplication

- Command-line interface
  - `obfuscate` (aliases: `o`, `obf`)
  - `restore` (aliases: `r`, `res`)
  - Automatic file naming: `.obf.py/.obf.c` for obfuscated, `.res.py/.res.c` for restored
  - Key file format: `.map.json`
  - Support for explicit `--out` and `--key` arguments

- Comprehensive test suite (121 tests)
- Documentation (README, README_ZH, CONTRIBUTING, SECURITY)
- Support for both Python 3.8+ and C code

### Technical Details

- Lossless restoration uses zlib compression + base64 encoding
- Source chunks distributed as comments (`#@mistode:chunk:` for Python, `// @mistode:chunk:` for C)
- Metadata embedded as `#@mistode:metadata:` or `/* @mistode:metadata: */`
- Two-layer restoration: Priority 1 (source chunks), Priority 2 (metadata mapping)
