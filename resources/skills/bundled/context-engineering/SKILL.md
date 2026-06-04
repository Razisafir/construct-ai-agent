---
name: context-engineering
version: 1.0.0
category: coding
description: Gather, structure, and optimize context before coding to maximize implementation quality
author: Construct AI
tools_needed: [read_file, shell, write_file]
confidence: 0.95
---

# Context Engineering

## Description

Systematically gather, organize, and present relevant context before writing code. This includes understanding existing codebases, dependencies, constraints, and requirements to produce higher-quality implementations with fewer iterations.

## When to Use

- Starting work in an unfamiliar codebase
- The task touches multiple files or modules
- Need to understand existing patterns before adding new code
- Debugging complex issues that span multiple layers
- Reviewing or modifying legacy code

## Steps

### Step 1: Map the Codebase

**Tool:** `shell`
**Parameters:**

```json
{"command": "find /src -type f -name '*.py' | head -50 && echo '---' && tree -L 3 /src", "description": "Map project structure"}
```

**Validation:** You can identify: project structure, main modules, test locations, config files, entry points.

### Step 2: Read Entry Points and Configuration

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/src/main.py"}
```

**Validation:** Understand how the application starts, what frameworks are used, and how components are wired together.

### Step 3: Identify Relevant Code Patterns

**Tool:** `shell`
**Parameters:**

```json
{"command": "grep -r 'class.*Service' /src --include='*.py' | head -20", "description": "Find existing service patterns"}
```

**Validation:** Can describe the architectural pattern (MVC, layered, hexagonal, etc.) and naming conventions.

### Step 4: Read Related Implementation Files

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/src/services/similar_existing_service.py"}
```

**Validation:** Understand existing patterns for error handling, logging, dependency injection, and testing.

### Step 5: Check Dependencies and Constraints

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/pyproject.toml"}
```

**Validation:** Know the dependency versions, Python version constraints, and available libraries.

### Step 6: Document Context Summary

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/context/current-task-context.md",
  "content": "# Context Summary\n\n## Project\n- Name: example-service\n- Framework: FastAPI\n- Pattern: Layered architecture\n\n## Relevant Files\n- /src/services/user_service.py (similar pattern)\n- /src/models/user.py (data model)\n- /src/api/users.py (existing endpoints)\n\n## Patterns Observed\n- Services use @inject for DI\n- Exceptions use custom HTTPException subclasses\n- Tests use pytest-asyncio\n\n## Constraints\n- Python 3.11+\n- SQLAlchemy 2.0\n- Must maintain 90% test coverage\n"
}
```

**Validation:** Context document captures all information needed to implement the task correctly on the first attempt.

### Step 7: Validate Context Completeness

**Tool:** `shell`
**Parameters:**

```json
{"command": "python scripts/validate-context.py --context docs/context/current-task-context.md --task docs/tasks/current-task.md", "description": "Validate context covers task needs"}
```

**Validation:** Every requirement in the task has supporting context. No blind spots in understanding.

## Examples

### Example 1: Adding a Feature to a FastAPI App

**Input:** "Add user profile upload functionality."

**Process:**

1. Map codebase: Found /src/api/, /src/services/, /src/models/
2. Read main.py: FastAPI with dependency injection
3. Find patterns: Existing file upload in /src/services/document_service.py
4. Read similar: Document upload uses S3, validates MIME types
5. Check deps: boto3 installed, PIL available for image processing
6. Document: Context summary with patterns and constraints
7. Implement: Profile upload following existing patterns

**Output:** Feature implemented matching existing patterns, with proper error handling and tests.

### Example 2: Debugging a Race Condition

**Input:** "Fix intermittent test failures in payment processing."

**Process:**

1. Map codebase: Found /src/payments/, /tests/integration/
2. Read entry: Async FastAPI with background tasks
3. Find patterns: PaymentService uses async/await throughout
4. Read related: OrderService handles similar concurrency
5. Check deps: asyncio, aiohttp, redis for locking
6. Document: Context with concurrency patterns and shared resources
7. Identify: Missing distributed lock on payment status update

**Output:** Root cause identified and fixed with proper locking mechanism.

### Example 3: Refactoring Legacy Code

**Input:** "Refactor the reporting module."

**Process:**

1. Map codebase: /src/reporting/ - 15 files, 3000+ lines
2. Read entry: Flask app with direct SQL queries
3. Find patterns: No ORM, raw SQL throughout, no tests
4. Read related: Newer modules use SQLAlchemy with repositories
5. Check deps: SQLAlchemy 2.0 available but unused in reporting
6. Document: Migration plan from raw SQL to ORM with test strategy
7. Execute: Incremental refactor per the plan

**Output:** Systematic refactor with preserved behavior and added test coverage.

## Best Practices

- **Read before writing.** Always understand existing code before modifying it.
- **Follow existing patterns.** Match the style and patterns of the surrounding codebase.
- **Document your findings.** Write down context to avoid re-reading files.
- **Start with tests.** Read existing tests to understand expected behavior.
- **Check git history.** `git log --oneline -- path/` reveals recent changes and rationale.
- **Identify stakeholders.** Know who owns the code and who to consult.
- **Map data flows.** Trace how data moves through the system for your use case.
- **Note edge cases.** Document special cases and error scenarios found in existing code.