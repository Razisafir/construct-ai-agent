---
name: source-driven-development
version: 1.0.0
category: coding
description: Read and understand existing source code first, then extend following established patterns
author: Construct AI
tools_needed: [read_file, shell, write_file, edit_file]
confidence: 0.95
---

# Source-Driven Development

## Description

A methodology centered on deep code reading before any modification. Understand the existing architecture, patterns, and conventions by reading source code, then extend or modify following the established patterns exactly.

## When to Use

- Adding features to an existing, mature codebase
- The codebase has established architectural patterns
- Need to maintain consistency with existing code
- Onboarding to a new project or team
- Fixing bugs in complex, unfamiliar systems

## Steps

### Step 1: Identify the Code Neighborhood

**Tool:** `shell`
**Parameters:**

```json
{"command": "find /src -type f -name '*.py' | xargs grep -l 'User' | head -20", "description": "Find files related to the domain"}
```

**Validation:** Found all files that touch the relevant domain concept or feature area.

### Step 2: Read the Call Stack Top-Down

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/src/api/users.py"}
```

**Validation:** Can trace a request from API endpoint through service layer to data access.

### Step 3: Read the Data Layer

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/src/models/user.py"}
```

**Validation:** Understand data models, relationships, validation rules, and constraints.

### Step 4: Study Business Logic

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/src/services/user_service.py"}
```

**Validation:** Can explain the business rules, validation logic, and error handling strategy.

### Step 5: Analyze Test Patterns

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/tests/services/test_user_service.py"}
```

**Validation:** Understand testing conventions, fixtures, mocking strategy, and coverage expectations.

### Step 6: Implement Following Patterns

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/services/user_profile_service.py",
  "content": "# Follows the exact pattern of user_service.py\n# Same error handling, same logging, same DI pattern\n"
}
```

**Validation:** New code is indistinguishable from existing code in style, structure, and patterns.

### Step 7: Verify Pattern Compliance

**Tool:** `shell`
**Parameters:**

```json
{"command": "flake8 /src/services/user_profile_service.py && mypy /src/services/user_profile_service.py && pytest tests/services/test_user_profile_service.py -v", "description": "Lint, type-check, and test new code"}
```

**Validation:** Code passes all quality checks. Tests follow the same patterns as existing test files.

## Examples

### Example 1: Adding a New API Endpoint

**Input:** "Add a user search endpoint."

**Process:**

1. Find neighborhood: User-related files in /src/api/, /src/services/
2. Read call stack: GET /users/{id} → UserService.get_user() → UserRepository
3. Read data layer: User model with SQLAlchemy, indexes on email
4. Study logic: Existing search in ProductService uses full-text search
5. Analyze tests: Mock repository, test edge cases, 404 handling
6. Implement: UserSearchService following ProductService search pattern
7. Verify: All linters pass, tests follow established patterns

**Output:** New search endpoint consistent with existing code, properly tested.

### Example 2: Extending a Service Class

**Input:** "Add bulk import to the ProductService."

**Process:**

1. Find neighborhood: /src/services/product_service.py and its tests
2. Read call stack: API → ProductService → ProductRepository → DB
3. Read data layer: Product model with validations
4. Study logic: Existing create() method with validation and error handling
5. Analyze tests: Unit tests with mocked repository, integration tests with real DB
6. Implement: bulk_create() following the exact pattern of create()
7. Verify: Tests mirror existing test structure, coverage maintained

**Output:** Bulk import feature that looks like it was written by the original author.

### Example 3: Fixing a Bug in Legacy Code

**Input:** "Fix the memory leak in the report generator."

**Process:**

1. Find neighborhood: /src/reporting/ module
2. Read call stack: ReportController → ReportService → ReportGenerator
3. Read data layer: Large dataset streaming with pagination
4. Study logic: Generator yields rows, but something holds references
5. Analyze tests: No existing tests for large datasets
6. Implement: Fix the leak, add test with large dataset
7. Verify: Memory profile shows stable usage, new test passes

**Output:** Bug fixed with a regression test preventing future memory leaks.

## Best Practices

- **Read 3x before writing 1x.** Thorough reading prevents incorrect assumptions.
- **Match the style exactly.** Use the same naming, spacing, import style, and patterns.
- **Copy-paste-modify.** Start from an existing similar file and adapt it.
- **Respect the architecture.** Don't introduce new patterns when existing ones suffice.
- **Check git blame.** Understanding who wrote the code and when provides context.
- **Read the tests first.** Tests document the intended behavior better than comments.
- **Note the error handling.** Every codebase has its own error handling philosophy.
- **Follow the import conventions.** Match relative vs absolute, grouping, and ordering.