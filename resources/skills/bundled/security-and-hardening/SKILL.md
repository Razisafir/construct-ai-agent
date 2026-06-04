---
name: security-and-hardening
version: 1.0.0
category: security
description: Apply security best practices, scan for vulnerabilities, and harden applications
author: Construct AI
tools_needed: [shell, read_file, write_file, edit_file]
confidence: 0.95
---

# Security and Hardening

## Description

Systematically identify and remediate security vulnerabilities in code, dependencies, and infrastructure. Apply defense-in-depth principles including input validation, secure defaults, least privilege, and comprehensive logging.

## When to Use

- Before production deployment
- After adding authentication or authorization features
- When handling sensitive data (PII, financial, health)
- Following security incidents or vulnerability disclosures
- Regular security audits (quarterly recommended)
- When adding file uploads, user input, or external integrations

## Steps

### Step 1: Dependency Vulnerability Scan

**Tool:** `shell`
**Parameters:**

```json
{"command": "safety check --json --full-report > safety-report.json 2>&1 || true", "description": "Scan Python dependencies for known vulnerabilities"}
```

**Also run:**

```json
{"command": "pip-audit --desc --format=json > pip-audit-report.json 2>&1 || true", "description": "Alternative dependency vulnerability scan"}
```

**Validation:** All high and critical severity vulnerabilities identified. Document each with CVE ID.

### Step 2: Static Security Analysis

**Tool:** `shell`
**Parameters:**

```json
{"command": "bandit -r src/ -f json -o bandit-report.json", "description": "Run static security analysis"}
```

**Validation:** No high-severity issues. Medium issues reviewed and either fixed or accepted with documented risk.

### Step 3: Review Authentication and Authorization

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/src/auth/authentication.py"}
```

**Validation:** Checklist:

- [ ] Passwords hashed with bcrypt/argon2 (not MD5/SHA1)
- [ ] JWT tokens have expiration
- [ ] Refresh token rotation implemented
- [ ] Session management is server-side validated
- [ ] Rate limiting on login endpoints
- [ ] Proper CORS configuration
- [ ] Secure cookie flags (HttpOnly, Secure, SameSite)

### Step 4: Input Validation and Sanitization

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/src/api/validators.py",
  "old_string": "def process_user_input(data):\n    return db.query(f\"SELECT * FROM users WHERE name = '{data['name']}'\")",
  "new_string": "from pydantic import BaseModel, validator\nimport re\n\nclass UserInput(BaseModel):\n    name: str\n    email: str\n    \n    @validator('name')\n    def validate_name(cls, v):\n        if not re.match(r'^[\\w\\s-]{1,100}$', v):\n            raise ValueError('Invalid name format')\n        return v.strip()\n\ndef process_user_input(data: UserInput):\n    return db.execute(\n        'SELECT * FROM users WHERE name = :name',\n        {'name': data.name}\n    )"
}
```

**Validation:** All user inputs are validated with schemas. No SQL injection possible. All queries use parameterized statements.

### Step 5: Secure Configuration Review

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/.env.example"}
```

**Validation:** Checklist:

- [ ] No secrets in code or config files
- [ ] DEBUG=False in production
- [ ] Strong random SECRET_KEY
- [ ] HTTPS enforced (HSTS headers)
- [ ] Database uses SSL connection
- [ ] Logging doesn't include sensitive data

### Step 6: Implement Security Headers

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/middleware/security_headers.py",
  "content": "from fastapi import Request, Response\nfrom starlette.middleware.base import BaseHTTPMiddleware\n\nclass SecurityHeadersMiddleware(BaseHTTPMiddleware):\n    async def dispatch(self, request: Request, call_next):\n        response = await call_next(request)\n        response.headers['X-Content-Type-Options'] = 'nosniff'\n        response.headers['X-Frame-Options'] = 'DENY'\n        response.headers['X-XSS-Protection'] = '1; mode=block'\n        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'\n        response.headers['Content-Security-Policy'] = \"default-src 'self'\"\n        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'\n        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'\n        return response\n"
}
```

**Validation:** Security headers present on all responses. Verified with `curl -I`.

### Step 7: Run Penetration Tests

**Tool:** `shell`
**Parameters:**

```json
{"command": "nmap -sV --script=http-enum localhost -p 8000", "description": "Basic port and service scanning"}
```

**Also:**

```json
{"command": "python -m pytest tests/security/ -v -k 'sql_injection or xss or csrf or auth_bypass'", "description": "Run security-focused tests"}
```

**Validation:** All security tests pass. No exposed services or endpoints.

### Step 8: Document Security Measures

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/security/security-checklist.md",
  "content": "# Security Checklist Results\n\n## Date: 2024-01-15\n\n## Dependency Scan\n- [x] No critical vulnerabilities\n- [x] 2 medium CVEs patched (see #123, #124)\n\n## Static Analysis\n- [x] Bandit: 0 high, 0 medium issues\n\n## Auth/AuthZ\n- [x] Password hashing: bcrypt (cost=12)\n- [x] JWT expiry: 15 minutes\n- [x] Rate limiting: 5 attempts per minute on login\n\n## Input Validation\n- [x] All endpoints use Pydantic validators\n- [x] SQL parameterized queries throughout\n- [x] File upload: MIME type + size validation\n\n## Headers\n- [x] All 7 security headers implemented\n\n## Secrets\n- [x] No secrets in code\n- [x] Secrets in environment variables\n- [x] Secret rotation policy documented\n"
}
```

**Validation:** Document is complete and reviewed by security team.

## Examples

### Example 1: Securing a Web API

**Input:** "Audit and harden our REST API before production launch."

**Process:**

1. Dependencies: Found 3 CVEs in `requests` and `jinja2` — upgrade both
2. Bandit: Found hardcoded API key in `config.py` — move to env var
3. Auth: JWT expiration was 7 days — reduce to 15 minutes with refresh tokens
4. Input: Add Pydantic validators to all endpoints, parameterize all SQL
5. Config: Enable HTTPS-only, secure cookies, DEBUG=False
6. Headers: Add SecurityHeadersMiddleware with all recommended headers
7. Pen tests: SQL injection tests pass, XSS tests pass, auth bypass blocked
8. Document: Complete security checklist with sign-off

**Output:** Production-ready API with defense-in-depth security.

### Example 2: Securing File Uploads

**Input:** "Secure the file upload feature."

**Process:**

1. Dependencies: Image processing lib up to date
2. Bandit: No issues in upload code
3. Auth: Upload endpoint requires authentication
4. Input: Validate MIME type (magic numbers, not extension), max 5MB, scan with ClamAV
5. Config: Store uploads outside web root, random filenames
6. Headers: Content-Disposition: attachment for downloads
7. Pen tests: Path traversal blocked, executable upload blocked
8. Document: Upload security measures documented

**Output:** Secure file upload with multi-layer validation.

### Example 3: Post-Incident Hardening

**Input:** "Strengthen security after a data exposure incident."

**Process:**

1. Dependencies: Full audit, upgrade 12 packages with known CVEs
2. Bandit: Found 2 SQL injection risks — immediate fix
3. Auth: Add MFA requirement for admin accounts, audit all API keys
4. Input: Add output encoding for all user-generated content
5. Config: Rotate all secrets, enable audit logging
6. Headers: Add CSP with strict policies
7. Pen tests: Full penetration test by external team
8. Document: Incident report, remediation log, updated policies

**Output:** Comprehensive security overhaul with documented improvements.

## Best Practices

- **Defense in depth.** No single security measure is enough; layer protections.
- **Never trust user input.** Validate everything at the boundary.
- **Principle of least privilege.** Grant minimum permissions necessary.
- **Secure by default.** The safest configuration should be the default.
- **Fail securely.** When something breaks, it should fail to a secure state.
- **Keep secrets secret.** No secrets in code, logs, or error messages.
- **Stay updated.** Monitor CVEs for dependencies; patch promptly.
- **Log security events.** Failed logins, permission denials, anomalies.
- **Use standard libraries.** Don't roll your own crypto or auth.
- **Regular audits.** Schedule quarterly security reviews.