---
name: repo-audit
description: Comprehensive repository health check covering code quality, security, documentation, test coverage, and dependencies
category: devops
version: 1.0.0
author: Construct
---

# Repository Audit

## Overview

The **Repository Audit** skill performs a comprehensive health check of a software repository across five critical dimensions: code quality, security posture, documentation completeness, test coverage, and dependency hygiene. It analyzes the codebase structure, detects anti-patterns, identifies security vulnerabilities, evaluates documentation quality, measures test coverage, and assesses dependency freshness and license compatibility. The output is a detailed audit report with severity ratings and actionable remediation steps.

## Checks Performed

- **Code Quality**: Linting errors, code complexity, duplication, formatting consistency, type safety
- **Security**: Vulnerable dependencies, secret leakage, insecure configurations, CWE detection
- **Documentation**: README completeness, API docs, inline comments, changelog currency, ADR presence
- **Test Coverage**: Line coverage, branch coverage, test reliability, mutation score, flaky test detection
- **Dependency Health**: Outdated packages, unused dependencies, license conflicts, supply chain risks
- **Repository Hygiene**: Git history quality, commit message standards, branch protection, CI/CD health
- **Performance**: Bundle size, import tree analysis, resource leak patterns, N+1 query detection
- **Accessibility**: ARIA compliance, color contrast, keyboard navigation (for frontend projects)

## Execution Steps

1. **Inventory Repository Structure**
   - Catalog all source files by language and purpose (`scc` or `cloc`)
   - Identify configuration files, CI/CD pipelines, and build scripts
   - Map directory structure against language-specific conventions
   - Detect monorepo vs. polyrepo patterns and workspace configuration

2. **Analyze Code Quality**
   - Run language-specific linters (`eslint`, `pylint`, `clippy`, `golangci-lint`)
   - Calculate cyclomatic complexity per function (threshold: >10 = warning, >15 = critical)
   - Detect code duplication with `jscpd`, `pmd`, or `simian`
   - Check formatting compliance with `prettier`, `black`, `rustfmt`, `gofmt`
   - Verify type coverage for TypeScript/Python projects

3. **Perform Security Scan**
   - Scan dependencies for known CVEs using `snyk`, `npm audit`, `pip-audit`, `cargo audit`
   - Detect secret leakage with `gitleaks`, `truffleHog`, or `git-secrets`
   - Check for hardcoded credentials, API keys, and tokens in source
   - Identify insecure coding patterns (SQL injection, XSS, unsafe deserialization)
   - Verify security headers and TLS configuration for web projects

4. **Evaluate Documentation**
   - Check README for required sections: installation, usage, API reference, contributing, license
   - Verify inline documentation ratio (target: >30% of public APIs)
   - Check changelog currency (latest entry within 3 months for active projects)
   - Detect stale or TODO comments older than 6 months
   - Verify architectural decision records (ADRs) are present for major decisions

5. **Measure Test Coverage**
   - Run test suite and collect line coverage, branch coverage, function coverage
   - Identify files with 0% coverage or <50% coverage
   - Detect flaky tests (tests that fail intermittently without code changes)
   - Calculate test-to-code ratio (target: >1:1 for unit tests)
   - Check for missing test categories: unit, integration, e2e, contract, performance

6. **Audit Dependencies**
   - Check for outdated packages (patch, minor, major version behind)
   - Identify unused dependencies with `depcheck` or `knip`
   - Verify all dependency licenses are compatible with project license
   - Assess dependency health: download trends, maintenance status, open issue ratio
   - Detect overly broad version constraints that increase supply chain risk

7. **Assess Repository Hygiene**
   - Check Git history for large files (>10MB) that should be in LFS
   - Verify `.gitignore` completeness for the technology stack
   - Check branch protection rules and required review policies
   - Verify CI/CD pipeline success rate over last 30 days
   - Check for stale branches and open pull request age

8. **Generate Audit Report**
   - Compile all findings into a severity matrix (Critical, High, Medium, Low, Info)
   - Calculate overall repository health score (0-100)
   - Provide remediation steps prioritized by impact and effort
   - Output: `repo-audit-report.md` with executive summary and detailed appendices

## Examples

### Example 1: Full Audit of a Node.js Project

**Input:**
```bash
/repo-audit --path ./my-api-service --tech nodejs --detail full
```

**Execution:**
```bash
cd ./my-api-service

# Structure inventory
scc --format json .

# Code quality
npx eslint . --format json > eslint-report.json
npx jscpd .
npx prettier --check "src/**/*.js"

# Security
npm audit --json
npx gitleaks detect --source . -v
npx snyk test --json

# Documentation
node -e "const fs=require('fs'); const readme=fs.readFileSync('README.md','utf8'); console.log('README length:',readme.length,'sections:',(readme.match(/^##/gm)||[]).length);"

# Test coverage
npm test -- --coverage --coverageReporters=json

# Dependencies
npx npm-check-updates
npx depcheck --json
```

**Output:**
```json
{
  "audit": "repo-audit-report",
  "repository": "my-api-service",
  "date": "2024-01-15T10:00:00Z",
  "health_score": 67,
  "summary": {
    "critical": 2,
    "high": 4,
    "medium": 8,
    "low": 12,
    "info": 5
  },
  "findings": [
    {
      "severity": "critical",
      "category": "security",
      "check": "secret-leakage",
      "message": "AWS access key found in commit history (file: config/aws.js, commit: a1b2c3d)",
      "tool": "gitleaks",
      "remediation": "Rotate the exposed key immediately, remove from history with git-filter-repo, add to .gitignore"
    },
    {
      "severity": "critical",
      "category": "dependencies",
      "check": "vulnerable-package",
      "message": "jsonwebtoken@8.5.1 has CVE-2022-23529 (signature verification bypass)",
      "tool": "npm audit",
      "remediation": "Upgrade to jsonwebtoken@9.0.0+ immediately"
    },
    {
      "severity": "high",
      "category": "code-quality",
      "check": "complexity",
      "message": "src/auth.js:authenticate() has cyclomatic complexity of 24",
      "tool": "eslint",
      "remediation": "Refactor into smaller functions; extract validation, token parsing, and error handling"
    },
    {
      "severity": "high",
      "category": "test-coverage",
      "check": "low-coverage",
      "message": "Line coverage is 43% (target: 80%)",
      "tool": "jest",
      "remediation": "Add unit tests for: src/auth.js, src/middleware.js, src/utils/validators.js"
    },
    {
      "severity": "medium",
      "category": "documentation",
      "check": "stale-changelog",
      "message": "CHANGELOG.md last updated 5 months ago",
      "remediation": "Update changelog with all changes since last release; consider automating with standard-version"
    }
  ],
  "metrics": {
    "code_quality": {
      "eslint_errors": 23,
      "eslint_warnings": 67,
      "duplication_percent": 4.2,
      "formatting_violations": 12,
      "max_complexity": 24,
      "avg_complexity": 5.3
    },
    "security": {
      "secrets_found": 1,
      "cve_count": 3,
      "insecure_patterns": 2,
      "dependency_vulns": 5
    },
    "documentation": {
      "readme_completeness": 75,
      "inline_doc_ratio": 22,
      "changelog_currency_days": 152,
      "stale_todo_comments": 8
    },
    "test_coverage": {
      "line_coverage": 43.2,
      "branch_coverage": 31.8,
      "function_coverage": 56.1,
      "test_count": 34,
      "flaky_tests": 2
    },
    "dependencies": {
      "total": 47,
      "outdated_major": 5,
      "outdated_minor": 12,
      "outdated_patch": 3,
      "unused": 4,
      "license_risks": 0
    }
  }
}
```

### Example 2: Python Library Health Check

**Input:**
```bash
/repo-audit --path ./dataflow-lib --tech python --focus dependencies,tests
```

**Output:**
```markdown
# Repository Audit Report: dataflow-lib

## Focus Areas: Dependencies, Test Coverage

### Dependency Health Score: 72/100

| Package | Current | Latest | Status | Risk |
|---------|---------|--------|--------|------|
| pandas | 1.5.3 | 2.1.4 | 2 major behind | MEDIUM |
| numpy | 1.24.0 | 1.26.2 | 2 minor behind | LOW |
| requests | 2.28.0 | 2.31.0 | 1 minor behind | LOW |
| pydantic | 1.10.0 | 2.5.0 | 1 major behind | **HIGH** |
| click | 8.1.0 | 8.1.7 | 1 patch behind | INFO |

**CRITICAL**: Pydantic v1 → v2 migration required. This is a breaking change
that affects all model definitions. Migration guide: docs.pydantic.dev/latest/migration/

### Unused Dependencies (found by depcheck)
- `colorama` — imported in 0 files, remove from requirements.txt
- `pyyaml` — only used in tests, move to dev-dependencies

### Test Coverage Score: 58/100

```
Name                          Stmts   Miss Branch BrPart   Cover
----------------------------------------------------------------
src/dataflow/__init__.py          5      0      -      -   100%
src/dataflow/core.py            234     89     56     12    62%
src/dataflow/pipeline.py        189     78     42      8    59%
src/dataflow/connectors.py      156    156     24      0     0% ← CRITICAL
src/dataflow/exceptions.py       12      0      -      -   100%
----------------------------------------------------------------
TOTAL                           596    323    122     20    46%
```

**Action Required**: `connectors.py` has 0% coverage — add unit tests for all
connector classes before next release.
```

### Example 3: CI/CD Pipeline Health Dashboard

**Input:**
```bash
/repo-audit --path ./platform-monorepo --tech nodejs,python,go --focus hygiene
```

**Output:**
```
╔════════════════════════════════════════════════════════════════╗
║           REPOSITORY HYGIENE DASHBOARD                        ║
║           platform-monorepo — 2024-01-15                       ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  Overall Health: ████████░░ 78/100                            ║
║                                                                ║
║  Git Hygiene                                                   ║
║  ├── Commit message format    ██████████ 95%                  ║
║  ├── Branch naming            ██████████ 92%                  ║
║  ├── Large files in history   █████████░░ 1 issue             ║
║  │   ⚠  14MB video in commit 3f2a1b — add to git-lfs        ║
║  └── .gitignore completeness  ████████░░ 80%                  ║
║      ⚠  Missing: .env.local, *.pyc, __pycache__/             ║
║                                                                ║
║  CI/CD Health (Last 30 Days)                                   ║
║  ├── Pipeline success rate    ████████░░ 87%                  ║
║  │   ⚠  12 failed out of 92 runs                             ║
║  ├── Avg build time           4m 32s (target: <5m) ✓         ║
║  ├── Flaky test rate          ███████░░░ 6%                   ║
║  │   ⚠  3 tests fail intermittently                          ║
║  └── Required reviews         ✓ Enabled on main               ║
║                                                                ║
║  Pull Request Health                                           ║
║  ├── Avg PR age               2.3 days ✓                      ║
║  ├── Stale PRs (>14 days)     4 ⚠                            ║
║  ├── Avg review time          6 hours ✓                       ║
║  └── Merge conflict rate      8% ✓                            ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

## Validation Criteria

- [ ] Repository structure is fully inventoried with file counts by language
- [ ] Code quality metrics include lint errors, complexity, duplication, and formatting
- [ ] Security scan covers secrets, CVEs, insecure patterns, and misconfigurations
- [ ] Documentation score evaluates README, inline docs, changelog, and ADRs
- [ ] Test coverage includes line, branch, and function metrics with targets
- [ ] Dependency audit identifies outdated, unused, and vulnerable packages
- [ ] Repository hygiene checks Git history, CI/CD health, and branch protection
- [ ] All findings are categorized by severity with specific remediation steps
- [ ] Overall health score (0-100) is calculated and explained
- [ ] Report identifies the top 3 priorities for improvement

## Best Practices

- Run repository audits **before every major release** and **monthly** for active projects
- Integrate all checks into CI/CD pipelines with **non-blocking warnings** and **blocking gates** for critical issues
- Set **coverage thresholds** that fail builds when coverage drops below targets
- Use **pre-commit hooks** for linting, formatting, and secret detection to catch issues early
- Maintain a **backlog of audit findings** tracked as GitHub/Jira issues with severity labels
- Rotate secrets **immediately** upon detection — never wait for the next release cycle
- Update dependencies on a **regular schedule** (e.g., weekly patch, monthly minor, quarterly major)
- Document **architecture decisions** as ADRs in a dedicated `docs/adr/` directory
- Keep the README updated with every feature change — treat it as a first-class deliverable
- Use **dependabot** or **renovate** for automated dependency update PRs
- Archive or delete stale branches older than 3 months to keep the repository clean
- Monitor CI/CD pipeline success rates — sustained drops below 90% indicate systemic issues

## Tools Required

| Tool | Purpose |
|------|---------|
| `scc` / `cloc` | Source code metrics and language detection |
| `eslint` / `pylint` / `clippy` / `golangci-lint` | Static code analysis |
| `jscpd` / `simian` | Code duplication detection |
| `npm audit` / `pip-audit` / `cargo audit` / `snyk` | Dependency vulnerability scanning |
| `gitleaks` / `truffleHog` | Secret detection in Git history |
| `prettier` / `black` / `rustfmt` | Code formatting verification |
| `jest` / `pytest` / `cargo test` / `go test` | Test execution and coverage collection |
| `depcheck` / `knip` | Unused dependency detection |
| `npm-check-updates` / `pip list --outdated` | Outdated dependency detection |
| `git` | Repository history and hygiene analysis |
| `jq` | JSON report processing |

## Related Skills

- `legal-risk-assessment` — License conflict and legal risk deep-dive
- `security-scan` — Dedicated security vulnerability assessment
- `competitor-analysis` — Compare repository health against competitors
