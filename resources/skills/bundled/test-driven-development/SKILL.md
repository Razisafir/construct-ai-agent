---
name: test-driven-development
version: 1.0.0
category: testing
description: Write tests before implementation, following the red-green-refactor cycle
author: Construct AI
tools_needed: [write_file, shell, read_file, edit_file]
confidence: 0.95
---

# Test-Driven Development

## Description

Write tests before writing implementation code, following the Red-Green-Refactor cycle. Tests define the behavior, implementation makes tests pass, and refactoring improves code quality while maintaining test coverage.

## When to Use

- Implementing business logic with clear requirements
- Fixing bugs (write failing test first, then fix)
- Adding features to well-tested codebases
- Algorithm implementation
- API endpoint development
- Any code that benefits from precise behavioral specification

## Steps

### Step 1: Write a Failing Test (Red)

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/tests/test_calculator.py",
  "content": "import pytest\nfrom src.calculator import Calculator\n\nclass TestCalculator:\n    def test_add_two_positive_numbers(self):\n        calc = Calculator()\n        result = calc.add(2, 3)\n        assert result == 5\n\n    def test_add_negative_numbers(self):\n        calc = Calculator()\n        assert calc.add(-2, -3) == -5\n\n    def test_add_mixed_signs(self):\n        calc = Calculator()\n        assert calc.add(-2, 3) == 1\n"
}
```

**Validation:** Test fails with clear error (import error or AssertionError). Run `pytest` to confirm red state.

### Step 2: Run the Test to Confirm It Fails

**Tool:** `shell`
**Parameters:**

```json
{"command": "pytest tests/test_calculator.py -v", "description": "Run tests to confirm red state"}
```

**Validation:** Output shows FAIL or ERROR. The failure is expected and clearly related to missing implementation.

### Step 3: Write Minimum Implementation (Green)

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/calculator.py",
  "content": "class Calculator:\n    \"\"\"A simple calculator class.\"\"\"\n    \n    def add(self, a: int, b: int) -> int:\n        \"\"\"Add two numbers.\"\"\"\n        return a + b\n"
}
```

**Validation:** Implementation is the simplest possible code that makes all tests pass. No premature optimization.

### Step 4: Run Tests to Confirm Green

**Tool:** `shell`
**Parameters:**

```json
{"command": "pytest tests/test_calculator.py -v", "description": "Run tests to confirm green state"}
```

**Validation:** All tests pass (green). If not, iterate on implementation until they do.

### Step 5: Refactor While Keeping Tests Green

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/src/calculator.py",
  "old_string": "class Calculator:\n    \"\"\"A simple calculator class.\"\"\"\n    \n    def add(self, a: int, b: int) -> int:\n        \"\"\"Add two numbers.\"\"\"\n        return a + b",
  "new_string": "class Calculator:\n    \"\"\"A calculator supporting basic arithmetic operations.\"\"\"\n    \n    def add(self, a: int | float, b: int | float) -> int | float:\n        \"\"\"Add two numbers together.\n        \n        Args:\n            a: First operand\n            b: Second operand\n            \n        Returns:\n            The sum of a and b\n        \"\"\"\n        return a + b"
}
```

**Validation:** Tests still pass after refactoring. Code quality improved (naming, types, docs).

### Step 6: Write Next Test (Red Again)

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/tests/test_calculator.py",
  "old_string": "    def test_add_mixed_signs(self):\n        calc = Calculator()\n        assert calc.add(-2, 3) == 1",
  "new_string": "    def test_add_mixed_signs(self):\n        calc = Calculator()\n        assert calc.add(-2, 3) == 1\n\n    def test_add_with_floats(self):\n        calc = Calculator()\n        assert calc.add(2.5, 3.1) == pytest.approx(5.6)\n\n    def test_add_non_numeric_raises(self):\n        calc = Calculator()\n        with pytest.raises(TypeError):\n            calc.add('2', 3)"
}
```

**Validation:** New test fails (red). Existing tests still pass (no regression).

### Step 7: Implement and Verify

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/src/calculator.py",
  "old_string": "        return a + b",
  "new_string": "        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):\n            raise TypeError('Operands must be numeric')\n        return a + b"
}
```

**Validation:** All tests pass including new ones. Run full suite to check for regressions.

### Step 8: Run Full Test Suite

**Tool:** `shell`
**Parameters:**

```json
{"command": "pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=90", "description": "Run full test suite with coverage"}
```

**Validation:** All tests pass. Coverage meets the threshold. No regressions.

## Examples

### Example 1: Password Validator

**Input:** "Implement a password validation function."

**Process:**

1. Red: Tests for min length, uppercase, lowercase, digit, special char
2. Confirm: All tests fail (no implementation)
3. Green: Simple implementation checking all criteria
4. Refactor: Extract validation rules into configurable list
5. Red: Test for empty password, None input
6. Green: Add guards for edge cases
7. Verify: 100% coverage, all edge cases handled

**Output:** Robust password validator with comprehensive test coverage.

### Example 2: Shopping Cart

**Input:** "Build a shopping cart with add, remove, total."

**Process:**

1. Red: Tests for add item, remove item, calculate total, empty cart
2. Confirm: All fail
3. Green: Dict-based cart implementation
4. Refactor: Extract Item class, add quantity support
5. Red: Tests for quantity update, item not found, negative quantities
6. Green: Handle all edge cases
7. Verify: Full coverage, no regressions

**Output:** Well-tested shopping cart with proper edge case handling.

### Example 3: API Rate Limiter

**Input:** "Implement a sliding window rate limiter."

**Process:**

1. Red: Tests for within limit, at limit, over limit, window sliding
2. Confirm: All fail
3. Green: Basic sliding window with timestamp tracking
4. Refactor: Extract Window class, optimize with deque
5. Red: Tests for concurrent requests, different keys, cleanup
6. Green: Thread-safe implementation with TTL cleanup
7. Verify: All tests pass, coverage ≥ 95%

**Output:** Thread-safe rate limiter with proven correctness.

## Best Practices

- **Red first.** Never write implementation before a failing test.
- **Obvious implementation.** Write the simplest code that passes; optimize in refactor.
- **One concept per test.** Each test should verify one specific behavior.
- **AAA pattern.** Arrange (setup), Act (execute), Assert (verify).
- **Fast feedback.** Tests should run in under 1 second for rapid cycling.
- **Refactor aggressively.** Green tests give confidence to clean up code.
- **No skipping.** Don't mark tests as skip unless there's a documented reason.
- **Test behavior, not implementation.** Tests should pass even if internals change.