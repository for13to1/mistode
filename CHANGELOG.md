# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
