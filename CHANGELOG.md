# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
