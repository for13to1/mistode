# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Obfuscated code raised `NameError` at runtime in two common shapes.**
  Class-body names were only protected once traversal reached the `class`
  statement, so a module-level reference visited earlier was renamed while the
  class-body definition was not. Match capture bindings (`case [a, b]`,
  `case {"k": v}`, `case [first, *rest]`, guards such as `case n if n > 0`)
  had no replacement site at all, because they bind through `MatchAs` /
  `MatchStar` / `MatchMapping` rather than an `ast.Name`. Both are now
  protected before any replacement is registered.
- **Source text that looks like a chunk marker is no longer treated as one.**
  A string literal containing `#@mistode:chunk:` or `#@mistode:metadata:`
  (C: the `/* ... */` forms) was consumed as layout data, which either aborted
  restoration or silently corrupted the output. Markers are now recognised
  only when the lexer reports a comment token, so string content stays program
  data.
- **Malformed payloads are reported instead of skipped.** A corrupt payload
  used to be dropped silently, desynchronising every following line. Chunk and
  metadata payloads are now validated (strict base64, zlib, and the expected
  JSON shape) and any failure names the stage that failed.
- **Inserted or removed chunk markers are detected.** Restoration verifies
  that every code token consumes exactly one layout record and that at most
  one trailing record remains. A *single* inserted or deleted record leaves a
  count a legitimate artifact can also have, so the metadata now records the
  exact number of records emitted and restoration compares it. Artifacts from
  earlier versions lack the field and fall back to the pairing checks.
- **`--password ""` no longer silently downgrades to plaintext.** An empty
  string was treated as "no password", producing an unencrypted artifact and
  exiting 0. It is now a usage error. The same applies to `password` in
  `pyproject.toml`.
- **`--cipher stream` without a password is a usage error** instead of
  silently producing plaintext payloads.
- **A wrong or missing `--password` reports an integrity failure** instead of
  claiming the file is not an artifact. Payloads from Mistode <= 0.1.3 (no
  nonce or tag) are reported as unauthenticatable rather than as a misleading
  integrity error.
- **Damaged artifacts are reported by cause, not by symptom.** Input that
  cannot be tokenised now says `does not tokenise` instead of blaming a
  missing metadata footer or claiming the file is not an artifact (including
  with `--key`, where metadata extraction is skipped). Input carrying no
  layout records at all now says `File does not appear to be obfuscated`
  instead of blaming a chunk marker that never existed. Previously the first
  case silently returned an empty string.
- A marker that shares a line with code containing a colon no longer yields a
  truncated payload.
- `--key` no longer writes an empty mapping for Python files, and an empty key
  no longer suppresses the fallback to embedded metadata (the previous
  behaviour printed `OK` while restoring nothing).
- `PythonObfuscator.restore()` no longer empties the output when the artifact
  has no embedded metadata (metadata stripping matched the bare `#@mistode:`
  prefix, hitting the first chunk at offset 0).
- Star imports are now resolved for absolute (`from utils import *`) and
  package (`from . import *`) forms, not only relative `from .mod import *`.
  Previously the target module's names were not protected, so the same
  function got two different obfuscated names and the project raised
  `NameError`.
- Cross-file import and symbol analysis now reads files with their detected
  encoding; UTF-8-only reads silently skipped GBK/Big5 files and broke
  cross-file references.
- Directory restore now mirrors non-source assets back, so a restored project
  is complete.
- Syntax errors in Python sources produce a friendly message instead of a raw
  traceback.
- **C output is no longer broken by tokenisation and spacing bugs.**
  Multi-character operators (`++`, `->`, `<<`, `&&`, ...) are single tokens
  (`a++` was re-emitted as `a+ +`); unary and binary `+`/`-` stay distinct
  (`a + ++b` no longer becomes `a+++b`); a space is kept before a following
  literal (`"%" PRIu64`, `#define MSG "hello"`); hex floats (`0x1.8p3`),
  C++ raw strings (`R"(...)"`) and character constants (`'a'`) are single
  tokens. Character constants previously had their inner letter renamed,
  turning `'a'` into a multi-character constant.
- C obfuscation verifies its own output by re-tokenising it and comparing
  against the source, so a spacing bug fails loudly instead of producing
  silently different behaviour.
- Identifiers on preprocessor directive lines (`#define`, `#ifdef` targets,
  macro parameters) are no longer renamed: they are contracts the preprocessor
  resolves. A file using token pasting (`a##b`) is left unrenamed, since
  pasting can synthesise any identifier at expansion time.
- C external-symbol detection unions `gcc`/`nm` output with the heuristic
  scan. `nm -u` cannot see typedefs (`size_t`, `FILE`) or macros (`stderr`,
  `NULL`), so on machines with gcc installed those names were renamed and the
  output failed to compile.
- C restore tokenises the whole cleaned stream instead of one line at a time.
  Tokens spanning lines (multi-line raw strings, continuations) previously
  split into fragments and corrupted the rest of the file.
- C `typedef struct { ... } Alias;` now records `Alias` as the alias, and
  typedef aliases count as definitions. Shared types in headers keep one name
  across translation units instead of failing with `unknown type name`.
- `#include "..."` is tokenised as a directive, so `include` no longer leaks
  into the external-symbol set.
- Obfuscating large files is linear again: the layout engine split the source
  once per token, making a 9,600-line file take ~12s (now ~0.3s).

### Added

- **Configurable payload cipher** (`--cipher` / `[tool.mistode] cipher`):
  - `stream` (default when a password is given): authenticated stream cipher
    from stdlib primitives - `scrypt` key derivation, SHA-256 CTR keystream,
    HMAC-SHA256 tag (encrypt-then-MAC).
  - `none`: plain base64 payloads.
  - The nonce is derived per payload (SIV-style), so distinct payloads never
    share a keystream while identical input still produces identical output.
  - Works for both Python and C; C previously ignored `--password` entirely.
- **Project (directory) mode**: `mistode o <dir>` obfuscates a whole project
  into a mirrored tree keeping original filenames, and `mistode r <dir>`
  restores it byte-identically. Names imported via `from mod import name`
  (Python) and symbols shared across compilation units (C) keep their names in
  every file.
- **Non-source assets are mirrored by default** (`--assets copy|skip|list`):
  templates, data files and configs are copied so the obfuscated project stays
  runnable. Credential-looking files (`.env`, `*.pem`, `*.key`) are copied by
  default; `--assets-skip-secrets` leaves them out.
- `--aggressive-methods` now also applies in single-file mode (it was only
  read in directory mode).

### Changed

- Python `main` is always preserved, so `console_scripts` entries and
  `python -m` keep working on obfuscated code.
- Project-mode restore rejects `--key` with an explicit error instead of
  silently ignoring it; obfuscation writes a combined key for auditing.
- Cross-file attribute collection now records every `ast.Attribute` (including
  chained accesses such as `sub.mod.timeout()`), not only single-level `a.b`.
  This trades a slightly lower rename rate for not breaking working code.
- Generated tokens are validated with `keyword.iskeyword()` (README previously
  claimed this but the check did not exist).
- C chunk markers use block comments (`/* @mistode:chunk: ... */`) and carry a
  trailing backslash inside multi-line macros, so macro bodies are no longer
  swallowed by the preprocessor.

### Internal

- `mistode.payload` holds the payload wire format and the error builders shared
  by the Python and C readers, so both report decoding failures identically.
- `CObfuscator.obfuscate()` accepts `source_dir`, passed to `gcc` as `-I` so
  `#include "local.h"` resolves during symbol probing.
- `project.py` holds project scanning, asset mirroring and cross-file analysis.
- `tests/test_regressions.py` covers the defects above, plus 14 legitimate
  edge cases (no final newline, empty file, comments only, CRLF, multi-line
  macros, blank lines, docstrings) that must keep restoring byte-identically.
- Ruff's `B` (bugbear), `A` (builtin shadowing) and `RUF100` (stale `noqa`)
  rule sets are enabled and clean. Exceptions raised inside `except` blocks now
  chain (`raise ... from`) instead of discarding the original error.
- C token groups are named (`ident`, `literal`, `number`, ...) so adding a
  pattern alternative cannot silently shift group indices.
- The seven PEP 758 bare `except A, B:` clauses use the explicit parenthesised
  form; ruff targets py313 so the formatter preserves it.

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
