# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability, please report it via the following methods:

- **Do NOT** report security issues in public Issues.
- Please contact the maintainer via email: <for13to1@outlook.com>

## Response Time

We aim to respond within 48 hours of a report and to provide a fix or plan within 7 days.

## Security Best Practices

### Scope of protection

Mistode raises the cost of reading code; it does not encrypt the program:

- Obfuscated code can still be reverse-engineered.
- String literals, numbers and control flow stay readable. Never embed
  secrets (API keys, passwords, URLs) in source.
- Obfuscation cannot replace authentication or authorization.

### `--password`

`--password` protects the restoration payloads (layout chunks and the
identifier mapping), not the delivered code:

- The artifact runs without it. Without the password the obfuscated source
  is still readable, but the original identifiers, comments and formatting
  cannot be recovered.
- Payloads use scrypt (N=2^14, r=8, p=1), a per-payload nonce and an
  HMAC-SHA256 tag. Known plaintext from one line does not unlock the rest,
  and tampering is detected.
- The KDF salt is fixed (`mistode-kdf-v1`) so identical inputs stay
  reproducible. Precomputation is reusable across installations, so use a
  long, unique, high-entropy passphrase and rotate it per recipient.
- Payloads from Mistode <= 0.1.3 had no nonce or tag and are rejected;
  re-obfuscate with the current release.

### Usage recommendations

1. Test the obfuscated artifact before shipping it.
2. Keep backups of the original source.
3. Keep artifacts and `--key` files out of public repositories; a key file
   is restoration material when no password is used.
4. Re-audit after upgrading: obfuscated output is not stable across versions.
