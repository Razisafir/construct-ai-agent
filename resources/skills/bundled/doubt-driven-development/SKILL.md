---
name: doubt-driven-development
version: 1.0.0
category: testing
description: Question every assumption, verify with tests, and prove correctness through evidence
author: Construct AI
tools_needed: [write_file, shell, read_file]
confidence: 0.95
---

# Doubt-Driven Development

## Description

A skeptical approach to software development where every assumption is questioned and every claim is verified. Instead of trusting that code works, you actively try to prove it doesn't work by writing targeted tests for edge cases, boundary conditions, and failure modes.

## When to Use

- Code correctness is critical (financial, medical, security)
- Previous bugs have emerged from "obvious" assumptions
- Working with concurrent or distributed systems
- Refactoring code without comprehensive tests
- Code has complex business logic with many edge cases

## Steps

### Step 1: List All Assumptions

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/assumptions/{feature}-assumptions.md",
  "content": "# Assumptions for Feature X\n\n## Explicit Assumptions\n1. Input list is never empty\n2. User ID is always a positive integer\n3. Database connection is always available\n\n## Implicit Assumptions\n1. String encoding is always UTF-8\n2. Clock never goes backwards\n3. Network timeout won't exceed 30s\n"
}
```

**Validation:** At least 5 assumptions identified, mix of explicit and implicit.

### Step 2: Rank Assumptions by Risk

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/assumptions/{feature}-risk-ranking.md",
  "content": "# Risk Ranking (High/Medium/Low)\n\n## HIGH RISK\n- Database connection availability (system-wide impact)\n- Clock going backwards (distributed systems)\n\n## MEDIUM RISK\n- Input list empty (edge case in production)\n- String encoding (depends on upstream)\n\n## LOW RISK\n- User ID positive (enforced by DB constraint)\n"
}
```

**Validation:** Each assumption has a clear risk level and rationale.

### Step 3: Write Tests to Challenge Each Assumption

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/tests/test_assumptions.py",
  "content": "import pytest\nfrom src.processor import process_items\n\ndef test_empty_list_should_raise_or_handle():\n    \"\"\"Challenge: Input list is never empty.\"\"\"\n    with pytest.raises(ValueError):\n        process_items([])\n\ndef test_user_id_zero():\n    \"\"\"Challenge: User ID is always positive.\"\"\"\n    result = process_items([1], user_id=0)\n    assert result is not None  # Should handle gracefully\n\ndef test_user_id_negative():\n    \"\"\"Challenge: User ID is always positive.\"\"\"\n    result = process_items([1], user_id=-1)\n    assert result is not None\n\ndef test_database_connection_failure():\n    \"\"\"Challenge: DB connection is always available.\"\"\"\n    with mock.patch('src.processor.get_db', side_effect=ConnectionError):\n        with pytest.raises(ServiceUnavailable):\n            process_items([1])\n\ndef test_malformed_utf8_input():\n    \"\"\"Challenge: String encoding is always UTF-8.\"\"\"\n    bad_bytes = b'\\xff\\xfe'\n    result = process_items([bad_bytes])\n    assert result is not None  # Should not crash\n"
}
```

**Validation:** Each test directly targets a listed assumption. Tests include both happy and failure paths.

### Step 4: Run Assumption-Challenging Tests

**Tool:** `shell`
**Parameters:**

```json
{"command": "pytest tests/test_assumptions.py -v --tb=short 2>&1 | tee test_results.log", "description": "Run assumption-challenging tests"}
```

**Validation:** Results logged. Any failing assumptions are documented as bugs or requirements gaps.

### Step 5: Fix or Document Violations

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/src/processor.py",
  "old_string": "def process_items(items, user_id):\n    \"\"\"Process a list of items.\"\"\"\n    return [item * 2 for item in items]",
  "new_string": "def process_items(items, user_id):\n    \"\"\"Process a list of items.\"\"\"\n    if not items:\n        raise ValueError('Items list cannot be empty')\n    if user_id is None or user_id < 0:\n        raise ValueError('User ID must be a non-negative integer')\n    return [item * 2 for item in items]"
}
```

**Validation:** All previously failing tests now pass. Behavior is well-defined for all edge cases.

### Step 6: Add Fuzz Tests for Residual Doubt

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/tests/test_fuzz.py",
  "content": "import pytest\nfrom hypothesis import given, strategies as st\nfrom src.processor import process_items\n\n@given(items=st.lists(st.integers(), min_size=1), user_id=st.integers(min_value=0))\ndef test_process_items_never_crashes(items, user_id):\n    \"\"\"Property: process_items never crashes on valid inputs.\"\"\"\n    result = process_items(items, user_id)\n    assert isinstance(result, list)\n    assert len(result) == len(items)\n"
}
```

**Validation:** Fuzz tests run for at least 100 iterations without failure.

### Step 7: Document Learnings

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/assumptions/{feature}-learnings.md",
  "content": "# Doubt-Driven Learnings\n\n## Assumptions That Were Wrong\n1. Empty list handling - originally undefined, now raises ValueError\n\n## Assumptions That Were Right\n1. User ID positive - DB constraint enforces this\n\n## New Assumptions Discovered\n1. Items must be hashable for caching\n2. Result list order must match input order\n"
}
```

**Validation:** Document captures what was learned, what changed, and new assumptions discovered.

## Examples

### Example 1: Payment Processing Validation

**Input:** "Verify the payment calculation logic."

**Process:**

1. Assumptions: Currency is always USD, amounts are positive, no rounding issues
2. Risk ranking: Currency (HIGH - multi-currency planned), Rounding (HIGH - financial)
3. Tests: Zero amount, negative amount, very large amount, fractional cents, currency conversion
4. Results: Rounding issue found with 3+ decimal places
5. Fix: Use Decimal instead of float, explicit rounding mode
6. Fuzz: Random amounts with property-based testing
7. Learnings: Never use float for money, always specify rounding mode

**Output:** Bulletproof payment calculation with comprehensive edge case coverage.

### Example 2: Concurrent Cache Implementation

**Input:** "Verify the thread-safe cache is actually thread-safe."

**Process:**

1. Assumptions: dict operations are atomic, GIL protects us, no race conditions
2. Risk ranking: Race conditions (HIGH - concurrent access), GIL assumptions (MEDIUM)
3. Tests: High-contention writes, read-during-write, iteration-during-modification
4. Results: Race condition found in `get_or_set` compound operation
5. Fix: Add locks around compound operations, use `threading.Lock`
6. Fuzz: Random concurrent operations with thread pool
7. Learnings: Individual dict ops are atomic, compounds are not

**Output:** Actually thread-safe cache with proven correctness under concurrency.

### Example 3: Date/Time Handling

**Input:** "Verify date range calculations."

**Process:**

1. Assumptions: Timezones don't matter, dates are valid, DST doesn't affect us
2. Risk ranking: Timezones (HIGH - users are global), DST (HIGH - ambiguous times)
3. Tests: DST transitions, leap years, timezone conversions, invalid dates
4. Results: Off-by-one errors during DST transitions
5. Fix: Use timezone-aware datetimes, explicit timezone conversion
6. Fuzz: Random dates across timezone boundaries
7. Learnings: Always use aware datetimes, never naive for user-facing features

**Output:** Robust date handling that correctly manages all timezone edge cases.

## Best Practices

- **Assume nothing.** Every unchecked assumption is a potential bug.
- **Write the test that should fail.** If you can't write a failing test, you don't understand the edge case.
- **Question "obvious" truths.** The most dangerous assumptions are the ones nobody questions.
- **Use property-based testing.** Fuzzing finds edge cases you didn't think of.
- **Document what you learned.** Future developers will have the same doubts; answer them.
- **Start with invariants.** What must always be true? Test those properties.
- **Fail fast, fail loud.** Invalid states should raise exceptions, not silently continue.
- **Test the boundaries.** Every range has minimum, maximum, and just-outside values.