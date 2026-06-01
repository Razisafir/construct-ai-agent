---
name: spec-driven-development
version: 1.0.0
category: coding
description: Write comprehensive specifications before implementation, then verify code against the spec throughout the development lifecycle
author: Construct AI
tools_needed: [write_file, read_file, shell]
confidence: 0.95
---

# Spec-Driven Development

## Description

Spec-Driven Development (SDD) is a methodology where you write a detailed technical specification before writing any implementation code. The spec defines requirements, interfaces, data models, error handling, and acceptance criteria. Code is then implemented to match the spec exactly, with continuous verification at each step.

## When to Use

- Starting a new feature or module from scratch
- The problem domain is complex or has many edge cases
- Multiple stakeholders need to agree on behavior before implementation
- Building APIs, libraries, or protocols that other systems will depend on
- Refactoring legacy code where behavior must be preserved exactly

## Steps

### Step 1: Gather Requirements

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/path/to/requirements.md"}
```

**Validation:** Confirm you have a clear understanding of:

- Functional requirements (what the system should do)
- Non-functional requirements (performance, security, scalability)
- Constraints (tech stack, budget, timeline)
- Stakeholders and their needs

**Output:** A requirements summary document.

### Step 2: Write the Technical Specification

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/specs/{feature-name}-spec.md",
  "content": "# Feature Spec: {Feature Name}\n\n## Overview\n...\n\n## API Interface\n...\n\n## Data Model\n...\n\n## Error Handling\n...\n\n## Acceptance Criteria\n...\n"
}
```

**Validation:** The spec must include:

- [ ] Overview and goals
- [ ] API signatures or interface definitions
- [ ] Data models and schemas
- [ ] Error cases and handling strategy
- [ ] Acceptance criteria with measurable outcomes
- [ ] Dependencies and assumptions

### Step 3: Create the Spec Verification Script

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/scripts/verify-spec.py",
  "content": "#!/usr/bin/env python3\n\"\"\"Verify implementation against spec.\"\"\"\nimport ast\nimport sys\n\ndef verify_api_signatures(file_path: str, expected_signatures: dict) -> bool:\n    \"\"\"Check that implemented functions match spec signatures.\"\"\"\n    with open(file_path) as f:\n        tree = ast.parse(f.read())\n    found = {node.name: len(node.args.args) for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}\n    for name, expected in expected_signatures.items():\n        if name not in found:\n            print(f'FAIL: Function {name} not found')\n            return False\n    return True\n"
}
```

**Validation:** Script runs without errors and can parse a Python file.

### Step 4: Implement Against the Spec

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/{module}/implement.py",
  "content": "# Implementation follows spec line-by-line\n# See /docs/specs/{feature-name}-spec.md for reference\n"
}
```

**Validation:** Every function in the spec has a corresponding implementation. Every acceptance criterion is addressed.

### Step 5: Run Spec Verification

**Tool:** `shell`
**Parameters:**

```json
{"command": "python scripts/verify-spec.py --spec docs/specs/feature-spec.md --src src/module/", "description": "Run spec verification"}
```

**Validation:** Verification script reports 100% spec coverage. Any divergence is documented and approved.

### Step 6: Acceptance Testing

**Tool:** `shell`
**Parameters:**

```json
{"command": "python -m pytest tests/acceptance/ -v --spec-coverage", "description": "Run acceptance tests against spec"}
```

**Validation:** All acceptance criteria pass. Edge cases from the spec are covered.

## Examples

### Example 1: API Endpoint Specification

**Input:** "Build a user authentication endpoint."

**Process:**

1. Write spec defining POST /api/v1/auth, request/response schemas, error codes (400, 401, 429), rate limiting
2. Implement the endpoint following the spec exactly
3. Run verification to confirm all error codes are handled
4. Acceptance test with valid/invalid credentials, rate limit exceeded

**Output:** A fully specified and verified authentication endpoint with OpenAPI documentation.

### Example 2: Data Pipeline Module

**Input:** "Create a CSV to Parquet conversion pipeline."

**Process:**

1. Write spec defining input validation, schema inference, type mapping, error handling for malformed rows
2. Implement each stage matching the spec's data flow diagram
3. Verify all specified error cases (missing file, bad encoding, type mismatch)
4. Acceptance test with 1GB CSV, malformed rows, schema conflicts

**Output:** A production-ready data pipeline with documented behavior for every edge case.

### Example 3: Refactoring with Spec Preservation

**Input:** "Refactor the legacy payment module."

**Process:**

1. Read existing code and write a spec documenting current behavior (including bugs to preserve)
2. Mark intentional improvements separately from preserved behavior
3. Refactor implementation, verifying against the spec at each step
4. Confirm all existing tests still pass

**Output:** Clean refactored code with a specification documenting exactly what changed and what was preserved.

## Best Practices

- **Spec first, code second.** Never start implementation before the spec is complete and reviewed.
- **Make specs measurable.** Every acceptance criterion should be verifiable by a test.
- **Version your specs.** Keep specs in version control alongside code; update both together.
- **Specs are contracts.** Treat the spec as a binding agreement between stakeholders and implementers.
- **Use the spec to say no.** When scope creep arises, refer to the spec and require formal updates.
- **Automate verification.** Write scripts that compare implementation against spec automatically.
- **Keep specs living documents.** Update specs when requirements change, never let them drift from reality.