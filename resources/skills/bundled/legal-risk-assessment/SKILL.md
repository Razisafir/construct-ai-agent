---
name: legal-risk-assessment
description: Scans code for legal risks - license conflicts, GDPR violations, copyright issues
category: security
version: 1.0.0
author: Construct
---

# Legal Risk Assessment

## Overview

The **Legal Risk Assessment** skill performs a comprehensive scan of source code and project artifacts to identify potential legal and compliance risks. It detects software license conflicts, data privacy regulation violations (GDPR, CCPA, LGPD), missing copyright headers, unauthorized third-party code usage, and insecure data handling patterns. This skill is essential for open-source projects, commercial software, and any codebase redistributed to third parties.

## Checks Performed

- **Dependency Licenses**: Scans `package.json`, `requirements.txt`, `Cargo.toml`, `go.mod`, `pom.xml` for licenses with conflicting obligations (GPL, AGPL, SSPL, proprietary)
- **Data Handling**: Identifies PII collection, storage, and processing patterns that may violate privacy laws
- **User Consent Flows**: Validates cookie consent, terms of service acceptance, and data processing agreements
- **Copyright Headers**: Verifies source files contain proper copyright notices and license headers
- **Third-Party Code**: Detects vendored, copied, or adapted code without attribution
- **Export Compliance**: Flags cryptographic implementations subject to export control regulations
- **Trademark Infringement**: Identifies unauthorized use of protected brand names in identifiers

## Execution Steps

1. **Collect Project Metadata**
   - Read `package.json`, `pyproject.toml`, `LICENSE`, `NOTICE`, `COPYING` files
   - Enumerate all source files and their extensions
   - Identify the primary declared license of the project

2. **Scan Dependency Licenses**
   - Run `npm license-checker`, `pip-licenses`, `cargo-license`, or `go-licenses`
   - Classify each dependency as Permissive (MIT, Apache-2.0, BSD), Weak Copyleft (MPL, LGPL), or Strong Copyleft (GPL, AGPL)
   - Flag any dependency with an incompatible license relative to the project's primary license

3. **Analyze Data Handling Patterns**
   - Search source code for regex patterns matching email, phone, SSN, IP address, credit card storage
   - Detect database queries that read or write PII without encryption annotations
   - Flag hardcoded API keys, secrets, or credentials as potential data leak vectors

4. **Validate User Consent Mechanisms**
   - Check frontend code for cookie consent banners and opt-in/opt-out flows
   - Verify terms of service or privacy policy links are present and accessible
   - Ensure GDPR-required data processing consent records are referenced in code

5. **Verify Copyright Headers**
   - Scan all source files for copyright notices matching the project's declared license
   - Flag files missing headers or containing headers from other projects
   - Generate a report of files that need header updates

6. **Detect Third-Party Code**
   - Compare source files against known open-source code fingerprints
   - Flag files with high similarity to external repositories without attribution comments
   - Review vendored dependencies for license file inclusion

7. **Assess Export Compliance**
   - Identify cryptographic algorithm implementations (AES, RSA, ECC)
   - Flag custom crypto that may fall under export control classifications
   - Verify OpenSSL or libsodium linking with proper license notices

8. **Generate Risk Report**
   - Compile findings into a structured severity matrix (Critical, High, Medium, Low)
   - Provide remediation recommendations for each flagged item
   - Output machine-readable `legal-risk-report.json` and human-readable `LEGAL_RISKS.md`

## Examples

### Example 1: Scanning a Node.js Project

**Input:**
```bash
/legal-risk-assessment --path ./my-project --format json
```

**Execution:**
```bash
cd ./my-project
npx license-checker --summary
```

**Output:**
```json
{
  "project": "my-project",
  "primary_license": "MIT",
  "risks": [
    {
      "severity": "critical",
      "type": "license_conflict",
      "message": "Dependency 'left-pad' is licensed under GPL-3.0, which is incompatible with project MIT license",
      "dependency": "left-pad@1.3.0",
      "remediation": "Replace with MIT-licensed alternative or relicense project"
    },
    {
      "severity": "high",
      "type": "missing_copyright_header",
      "message": "23 of 45 source files are missing copyright headers",
      "files": ["src/utils.js", "src/auth.js"],
      "remediation": "Add standard copyright header to all source files"
    },
    {
      "severity": "medium",
      "type": "data_handling",
      "message": "PII (email addresses) stored in localStorage without encryption",
      "file": "src/components/LoginForm.vue",
      "remediation": "Encrypt PII at rest or move to secure HTTP-only cookies"
    }
  ]
}
```

### Example 2: Python GDPR Compliance Check

**Input:**
```python
# Code snippet under analysis
user_data = {
    "email": request.form["email"],
    "ssn": request.form["social_security"],
    "ip": request.remote_addr
}
db.execute(f"INSERT INTO users VALUES ({user_data})")
```

**Output:**
```markdown
## GDPR Violations Detected

1. **Unencrypted PII Storage** (CRITICAL)
   - SSN stored in plaintext in database
   - No encryption-at-rest detected
   - **Fix**: Use AES-256 encryption for sensitive fields

2. **SQL Injection Risk** (HIGH)
   - Raw f-string used in SQL query
   - **Fix**: Use parameterized queries

3. **Missing Consent Log** (HIGH)
   - No consent recording for data processing
   - **Fix**: Implement consent audit trail

4. **Data Retention Policy** (MEDIUM)
   - No automatic purge of IP addresses after 30 days
   - **Fix**: Add TTL to IP address fields
```

### Example 3: Multi-License Conflict Resolution

**Input:**
```
Project: Proprietary SaaS platform
Dependencies found:
- react@18.2.0 (MIT)
- gpl-library@2.1.0 (GPL-2.0)
- internal-toolkit (Proprietary)
- mongodb@6.0 (SSPL)
```

**Output:**
```
╔══════════════════════════════════════════════════════════════╗
║           LEGAL RISK ASSESSMENT REPORT                        ║
╠══════════════════════════════════════════════════════════════╣
║  Risk Level: CRITICAL                                         ║
║  License Compatibility: FAIL                                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                               ║
║  CONFLICTS:                                                   ║
║  1. gpl-library (GPL-2.0) → Requires full source disclosure  ║
║     for proprietary distribution. INCOMPATIBLE.               ║
║                                                               ║
║  2. mongodb (SSPL) → Requires releasing ALL source code      ║
║     as SSPL if offering as a service. INCOMPATIBLE.           ║
║                                                               ║
║  RECOMMENDATIONS:                                             ║
║  - Replace gpl-library with MIT/Apache-2.0 alternative        ║
║  - Replace MongoDB with PostgreSQL (PostgreSQL License)       ║
║  - Or relicense entire project under GPL-2.0                  ║
║                                                               ║
╚══════════════════════════════════════════════════════════════╝
```

## Validation Criteria

- [ ] All direct and transitive dependency licenses are identified and classified
- [ ] No Strong Copyleft license is present in a project with a permissive or proprietary license
- [ ] Every source file contains a valid copyright header matching the project's declared license
- [ ] No PII is stored or transmitted without encryption
- [ ] User consent mechanisms are present and GDPR-compliant
- [ ] All third-party code includes proper attribution
- [ ] Risk report is generated with severity levels and actionable remediation steps
- [ ] No custom cryptographic implementations are present without legal review
- [ ] CI/CD pipeline integration passes (breaks build on critical legal risks)

## Best Practices

- Run this assessment **before every release** and on every dependency update
- Integrate license scanning into CI/CD pipelines with `--failOn` flags for copyleft licenses
- Maintain a `LICENSES.md` or `THIRD_PARTY_NOTICES` file that is auto-generated from scan results
- Use `SPDX` identifiers in all source file headers for machine-readable compliance
- Encrypt all PII at rest and in transit; never log sensitive data
- Implement a consent management platform (CMP) for cookie and data processing consent
- Review legal risks with your organization's legal counsel before shipping production code
- Keep a record of all past risk reports to track remediation progress over time

## Tools Required

| Tool | Purpose |
|------|---------|
| `license-checker` (npm) / `pip-licenses` / `cargo-license` / `go-licenses` | Dependency license scanning |
| `fossa-cli` or `snyk` | Automated license and vulnerability scanning |
| `grep` / `ripgrep` | Pattern matching for PII and copyright headers |
| `spdx-license-list` | SPDX license identifier validation |
| `git log` | Attribution and author history verification |
| `openssl` | Cryptographic implementation detection |

## Related Skills

- `repo-audit` — General repository health check including code quality and security
- `competitor-analysis` — Analyze competitor codebases for legal and architectural patterns
- `security-scan` — Deep security vulnerability scanning beyond legal scope
