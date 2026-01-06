# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability, please report it via the following methods:

- **Do NOT** report security issues in public Issues.
- Please contact the maintainer via email: for13to1@outlook.com

## Response Time

We commit to causing an initial response within 48 hours of receiving a security vulnerability report and providing a solution or update plan within 7 days.

## Security Best Practices

### Limitations of Code Obfuscation

Please note that the code obfuscation provided by Mistode is primarily for protecting intellectual property and **cannot replace encryption or secure coding practices**:

- Obfuscated code can still be reverse-engineered.
- **Sensitive information in string constants will not be obfuscated** (e.g., API keys, passwords, URLs).
- Do not rely on obfuscation to protect sensitive information (e.g., passwords, API keys).
- Obfuscation cannot replace proper authentication and authorization mechanisms.

### Important Security Warning

**String Constant Obfuscation Limitations**:

- The current version only obfuscates identifiers (variable names, function names, class names, etc.).
- **Sensitive information in string constants is not automatically obfuscated**.
- If your code contains sensitive strings (API keys, database passwords, etc.), please handle them manually or use other encryption methods.

### Usage Recommendations

1. **Production Use**: Thoroughly test the obfuscated code before deploying to production.
2. **Backup Original Code**: Always keep a backup of the original code.
3. **Version Control**: Include obfuscated code and mapping files in version control.
4. **Security Audit**: Periodically audit obfuscated code to ensure security.
