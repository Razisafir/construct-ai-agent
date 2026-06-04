---
name: incremental-implementation
version: 1.0.0
category: coding
description: Build features incrementally with working checkpoints, verifying at each step
author: Construct AI
tools_needed: [write_file, read_file, shell, edit_file]
confidence: 0.95
---

# Incremental Implementation

## Description

Build software one small, verifiable piece at a time. Each increment produces working, testable code. Complex features are decomposed into thin vertical slices that can be independently verified.

## When to Use

- Implementing multi-step features or workflows
- Risk of going down wrong architectural path is high
- Need to demonstrate progress frequently
- Working with unfamiliar APIs or libraries
- Building features that touch multiple layers (DB, API, UI)

## Steps

### Step 1: Identify the Smallest Working Slice

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/increments/slices.md",
  "content": "# Vertical Slices\n\n## Slice 1: Basic Data Flow\n- Database model → Repository → API endpoint\n- Acceptance: Can CREATE via API\n\n## Slice 2: Read Operations\n- Add GET endpoints with filtering\n- Acceptance: Can READ with filters\n\n## Slice 3: Full CRUD\n- UPDATE and DELETE operations\n- Acceptance: Full CRUD works\n"
}
```

**Validation:** Each slice is independently testable and provides user-visible value.

### Step 2: Implement Slice 1

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/models/user.py",
  "content": "from sqlalchemy import Column, Integer, String\nfrom database import Base\n\nclass User(Base):\n    __tablename__ = 'users'\n    id = Column(Integer, primary_key=True)\n    email = Column(String, nullable=False, unique=True)\n"
}
```

**Validation:** Code compiles, tests pass, and the slice's acceptance criteria are met.

### Step 3: Add Tests for Current Slice

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/tests/test_slice_1.py",
  "content": "import pytest\nfrom src.models.user import User\n\ndef test_user_creation():\n    user = User(email='test@example.com')\n    assert user.email == 'test@example.com'\n\ndef test_user_unique_email(db):\n    with pytest.raises(IntegrityError):\n        User.create(email='duplicate@example.com')\n        User.create(email='duplicate@example.com')\n"
}
```

**Validation:** Tests cover the happy path and at least one error case for this slice.

### Step 4: Verify Slice Before Continuing

**Tool:** `shell`
**Parameters:**

```json
{"command": "pytest tests/test_slice_1.py -v --cov=src/models --cov-report=term-missing", "description": "Run tests with coverage for current slice"}
```

**Validation:** All tests pass. Coverage for the slice is ≥ 90%. No regressions in previous slices.

### Step 5: Commit Working State

**Tool:** `shell`
**Parameters:**

```json
{"command": "git add -A && git commit -m 'feat(slice-1): add user model with create endpoint\n\n- Add User SQLAlchemy model\n- Add POST /users endpoint\n- Add validation and error handling\n- Tests: 3/3 passing, 94% coverage'", "description": "Commit working slice"}
```

**Validation:** Commit message describes what and why. Tests pass at this commit.

### Step 6: Implement Next Slice

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/src/api/users.py",
  "old_string": "@router.post('/users')\ndef create_user(...):\n    ...",
  "new_string": "@router.post('/users')\ndef create_user(...):\n    ...\n\n@router.get('/users')\ndef list_users(skip: int = 0, limit: int = 100):\n    ...\n\n@router.get('/users/{user_id}')\ndef get_user(user_id: int):\n    ..."
}
```

**Validation:** New slice builds on previous slices without breaking them. All prior tests still pass.

### Step 7: Final Integration Test

**Tool:** `shell`
**Parameters:**

```json
{"command": "pytest tests/ -v --cov=src --cov-report=html --cov-fail-under=85", "description": "Run full test suite with coverage threshold"}
```

**Validation:** All slices integrate correctly. Overall coverage meets the threshold.

## Examples

### Example 1: E-Commerce Checkout Flow

**Input:** "Build a complete checkout process."

**Process:**

1. Slice 1: Cart display with item list
2. Slice 2: Shipping address form with validation
3. Slice 3: Payment method selection
4. Slice 4: Order confirmation and receipt
5. Each slice adds a working UI component with tests

**Output:** A complete checkout flow built incrementally, each slice independently testable.

### Example 2: Background Job Processor

**Input:** "Build a background job processing system."

**Process:**

1. Slice 1: Job enqueue/dequeue with in-memory queue
2. Slice 2: Worker process that executes jobs
3. Slice 3: Redis-backed queue for persistence
4. Slice 4: Retry logic with exponential backoff
5. Slice 5: Job monitoring dashboard

**Output:** A resilient job processor built layer by layer, each slice production-ready.

### Example 3: Analytics Dashboard

**Input:** "Build an analytics dashboard with charts."

**Process:**

1. Slice 1: Data aggregation query (SQL)
2. Slice 2: API endpoint returning JSON
3. Slice 3: Frontend table display
4. Slice 4: Chart visualization
5. Slice 5: Date range filtering

**Output:** Dashboard built end-to-end incrementally, each slice providing visible progress.

## Best Practices

- **Commit after every slice.** Each increment should be a commit point.
- **Test before proceeding.** Never start the next slice until current tests pass.
- **Vertical over horizontal.** Prefer end-to-end slices over layer-by-layer.
- **Timebox slices.** Each slice should be completable in 1-4 hours.
- **Demonstrate value.** Each slice should show visible progress to stakeholders.
- **Refactor between slices.** Clean up before adding the next increment.
- **Document decisions.** Keep a running log of architectural decisions made per slice.