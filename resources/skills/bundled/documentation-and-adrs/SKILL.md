---
name: documentation-and-adrs
version: 1.0.0
category: research
description: Write comprehensive documentation and architecture decision records
author: Construct AI
tools_needed: [write_file, read_file, shell]
confidence: 0.95
---

# Documentation and ADRs

## Description

Write clear, comprehensive technical documentation and Architecture Decision Records (ADRs) that capture context, decisions, and consequences. Good documentation reduces onboarding time, prevents repeated mistakes, and preserves institutional knowledge.

## When to Use

- Onboarding new team members
- Making significant architectural decisions
- Documenting APIs, systems, or processes
- Capturing lessons learned from incidents
- Creating runbooks for operations
- Writing README files for projects or modules

## Steps

### Step 1: Identify Documentation Needs

**Tool:** `shell`
**Parameters:**

```json
{"command": "find /src -type f -name '*.py' | xargs grep -L 'docstring' | wc -l && echo 'files missing docstrings'", "description": "Assess documentation gaps"}
```

**Validation:** Documentation gaps identified: missing README, undocumented modules, no ADRs, missing API docs.

### Step 2: Write the README

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/README.md",
  "content": "# Project Name\n\n## Overview\nBrief description of what this project does and its purpose.\n\n## Quick Start\n```bash\n# Clone\ngit clone https://github.com/org/project.git\ncd project\n\n# Install\npip install -e '.[dev]'\n\n# Run tests\npytest\n\n# Start\npython -m src.main\n```\n\n## Architecture\nHigh-level architecture description with diagram link.\n\n## Development\nSee [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow.\n\n## API Documentation\nSee [docs/api/README.md](docs/api/README.md) for API reference.\n\n## License\n[MIT](LICENSE)\n"
}
```

**Validation:** README includes: overview, quick start, architecture link, dev guide, API docs, license.

### Step 3: Document Module with Docstrings

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/src/services/user_service.py",
  "old_string": "def create_user(data):\n    user = User(**data)\n    db.add(user)\n    db.commit()\n    return user",
  "new_string": "def create_user(data: UserCreate) -> User:\n    \"\"\"Create a new user in the system.\n    \n    Args:\n        data: User creation data including email and password.\n        \n    Returns:\n        The newly created User instance.\n        \n    Raises:\n        DuplicateEmailError: If a user with the given email already exists.\n        ValidationError: If the provided data fails validation.\n        \n    Example:\n        >>> user = create_user(UserCreate(email='new@example.com', password='secure123'))\n        >>> user.email\n        'new@example.com'\n    \"\"\"\n    user = User(**data.model_dump())\n    db.add(user)\n    db.commit()\n    return user"
}
```

**Validation:** All public functions have docstrings with args, returns, raises, and examples.

### Step 4: Write an Architecture Decision Record

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/adrs/001-use-postgresql-as-primary-database.md",
  "content": "# ADR 001: Use PostgreSQL as Primary Database\n\n## Status\nAccepted\n\n## Context\nWe need to choose a primary database for our application. Requirements:\n- ACID transactions for financial data\n- Complex querying capabilities\n- JSON support for flexible schemas\n- Production-proven with strong community\n\n## Decision\nWe will use PostgreSQL 15 as our primary database.\n\n## Consequences\n\n### Positive\n- Full ACID compliance\n- Excellent query optimization\n- Rich data types (JSONB, arrays, ranges)\n- Strong consistency guarantees\n- Extensive tooling and monitoring\n\n### Negative\- Operational overhead compared to managed alternatives\n- Scaling writes requires sharding or read replicas\n- Team needs PostgreSQL expertise\n\n## Alternatives Considered\n- **MySQL**: Good option but lacks some advanced features\n- **MongoDB**: Flexible schema but weaker consistency guarantees\n- **SQLite**: Not suitable for concurrent web workloads\n\n## Decision Date\n2024-01-15\n\n## Decided By\nTeam consensus (Alice, Bob, Carol)\n"
}
```

**Validation:** ADR includes: status, context, decision, consequences (positive/negative), alternatives, date, deciders.

### Step 5: Generate API Documentation

**Tool:** `shell`
**Parameters:**

```json
{"command": "pdoc --output-dir docs/api src/", "description": "Generate API docs from docstrings"}
```

**Validation:** API docs generated for all public modules. Cross-references work correctly.

### Step 6: Create Operational Runbooks

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/runbooks/database-failover.md",
  "content": "# Runbook: Database Failover\n\n## Trigger\n- Database primary is unresponsive\n- Replication lag > 30 seconds\n- Disk space > 90% on primary\n\n## Steps\n1. **Verify the issue**\n   ```bash\n   pg_isready -h primary.db.internal\n   ```\n\n2. **Promote replica**\n   ```bash\n   pg_ctl promote -D /var/lib/postgresql/replica\n   ```\n\n3. **Update connection strings**\n   ```bash\n   kubectl set configmap app-config DB_HOST=replica.db.internal\n   ```\n\n4. **Verify application health**\n   ```bash\n   curl https://app.internal/health\n   ```\n\n5. **Notify team**\n   Post in #incidents Slack channel\n\n## Rollback\nTo revert to original primary:\n```bash\n# Rebuild primary as replica, then switch back\n```\n\n## Post-Incident\n- [ ] Write incident report\n- [ ] Schedule post-mortem\n- [ ] Update runbook if needed\n"
}
```

**Validation:** Runbook includes: trigger conditions, numbered steps with commands, rollback procedure, post-incident checklist.

### Step 7: Validate Documentation

**Tool:** `shell`
**Parameters:**

```json
{"command": "markdown-link-check docs/**/*.md && python -m doctest src/services/*.py -v", "description": "Check links and doctest examples"}
```

**Validation:** All links valid. Doctest examples pass. No broken references.

## Examples

### Example 1: New Service Documentation

**Input:** "Document a new microservice."

**Process:**

1. Needs: README, API docs, architecture diagram, deployment guide
2. README: Overview, quick start, architecture, development guide
3. Docstrings: All public functions documented
4. ADR: Why microservices over monolith (ADR 003)
5. API docs: Auto-generated from FastAPI OpenAPI spec
6. Runbook: Common issues and troubleshooting
7. Validate: All links work, doctests pass

**Output:** Complete documentation package for the new service.

### Example 2: Incident Retrospective ADR

**Input:** "Document lessons learned from an outage."

**Process:**

1. Needs: Timeline, root cause, impact, remediation, prevention
2. README: Reference to incident in operational docs
3. Docstrings: N/A (not code related)
4. ADR: Decision to add circuit breaker pattern (ADR 007)
5. API docs: N/A
6. Runbook: Updated with new failure mode and response
7. Validate: Links verified, reviewed by team

**Output:** Incident captured as ADR with preventive measures documented.

### Example 3: API Versioning Documentation

**Input:** "Document API versioning strategy."

**Process:**

1. Needs: Versioning approach, migration guides, changelog
2. README: API section with versioning overview
3. Docstrings: Version decorators documented
4. ADR: Why URL versioning over header versioning (ADR 005)
5. API docs: All versions documented with examples
6. Runbook: How to sunset an API version
7. Validate: Cross-references between docs verified

**Output:** Comprehensive API versioning documentation.

## Best Practices

- **Write for your future self.** Document what you'd need to know if you joined the team today.
- **ADRs are forever.** Once accepted, ADRs are immutable. Supersede with a new ADR if needed.
- **Code and docs together.** Update documentation in the same PR as code changes.
- **Examples are essential.** Every docstring should have a usage example.
- **Keep READMEs scannable.** Use headers, lists, and code blocks. No walls of text.
- **Document the why, not just the what.** Explain rationale, not just mechanics.
- **Runbooks are tested.** Periodically walk through runbooks to ensure they're current.
- **Link everything.** Cross-reference related docs, ADRs, and code.
- **Review docs like code.** Documentation should be reviewed in PRs.
- **Avoid documentation drift.** Stale docs are worse than no docs. Keep them current.