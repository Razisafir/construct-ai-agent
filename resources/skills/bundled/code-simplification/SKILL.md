---
name: code-simplification
version: 1.0.0
category: coding
description: Refactor complex code into simpler, more readable, and maintainable forms
author: Construct AI
tools_needed: [read_file, write_file, edit_file, shell]
confidence: 0.95
---

# Code Simplification

## Description

Transform complex, hard-to-understand code into simpler, more readable, and maintainable forms. Reduce cognitive load while preserving behavior. Simpler code has fewer bugs, is easier to test, and is more welcoming to new contributors.

## When to Use

- Code has high cyclomatic complexity (> 10)
- Functions are longer than 50 lines
- Deeply nested conditionals (3+ levels)
- Code has been flagged in review as hard to understand
- Preparing code for team handoff
- Legacy code modernization

## Steps

### Step 1: Measure Complexity

**Tool:** `shell`
**Parameters:**

```json
{"command": "radon cc src/ -a --show-complexity", "description": "Measure cyclomatic complexity"}
```

**Validation:** Identify functions with complexity > 10. Note the worst offenders.

### Step 2: Understand the Current Behavior

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/src/services/complex_service.py"}
```

**Validation:** Can explain what the code does and why. If not, add comments or ask the original author before changing.

### Step 3: Write Characterization Tests

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/tests/test_characterization.py",
  "content": "\"\"\"Tests that document current behavior before refactoring.\"\"\"\nimport pytest\nfrom src.services.complex_service import calculate_price\n\ndef test_standard_customer():\n    assert calculate_price(items=[1, 2], customer_type='standard', region='US') == 30\n\ndef test_vip_customer():\n    assert calculate_price(items=[1, 2], customer_type='vip', region='US') == 24\n\ndef test_international_customer():\n    assert calculate_price(items=[1, 2], customer_type='standard', region='EU') == 33\n\ndef test_empty_cart():\n    assert calculate_price(items=[], customer_type='standard', region='US') == 0\n\ndef test_bulk_discount():\n    assert calculate_price(items=list(range(100)), customer_type='standard', region='US') == 800\n"
}
```

**Validation:** All characterization tests pass against the current code. They document exact current behavior.

### Step 4: Extract Functions and Reduce Nesting

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/src/services/complex_service.py",
  "old_string": "def calculate_price(items, customer_type, region):\n    total = 0\n    for item in items:\n        if item > 0:\n            if customer_type == 'vip':\n                if region == 'US':\n                    total += item * 0.8\n                else:\n                    total += item * 0.8 * 1.1\n            else:\n                if region == 'US':\n                    total += item\n                else:\n                    total += item * 1.1\n    if len(items) > 50:\n        total = total * 0.9\n    return total",
  "new_string": "def _get_base_price(item, region):\n    multiplier = 1.0 if region == 'US' else 1.1\n    return item * multiplier\n\ndef _apply_customer_discount(price, customer_type):\n    discount = 0.8 if customer_type == 'vip' else 1.0\n    return price * discount\n\ndef _apply_bulk_discount(total, item_count):\n    return total * 0.9 if item_count > 50 else total\n\ndef calculate_price(items, customer_type, region):\n    if not items:\n        return 0\n    base_total = sum(_get_base_price(item, region) for item in items if item > 0)\n    discounted = _apply_customer_discount(base_total, customer_type)\n    return _apply_bulk_discount(discounted, len(items))"
}
```

**Validation:** Characterization tests still pass. Complexity reduced from 8 to 1 for main function.

### Step 5: Replace Conditionals with Polymorphism

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/services/pricing_strategy.py",
  "content": "from abc import ABC, abstractmethod\n\nclass PricingStrategy(ABC):\n    @abstractmethod\n    def calculate(self, items, region_multiplier):\n        ...\n\nclass StandardPricing(PricingStrategy):\n    def calculate(self, items, region_multiplier):\n        return sum(item * region_multiplier for item in items)\n\nclass VipPricing(PricingStrategy):\n    def calculate(self, items, region_multiplier):\n        return sum(item * region_multiplier * 0.8 for item in items)\n\ndef get_strategy(customer_type):\n    strategies = {'standard': StandardPricing, 'vip': VipPricing}\n    return strategies.get(customer_type, StandardPricing)()\n"
}
```

**Validation:** Strategy pattern eliminates if/elif chains. Tests still pass.

### Step 6: Remove Duplication

**Tool:** `shell`
**Parameters:**

```json
{"command": "pytest tests/test_characterization.py -v && pylint src/services/complex_service.py --disable=all --enable=R0801", "description": "Verify tests pass and check for duplication"}
```

**Validation:** Tests pass. Pylint shows no duplicate code warnings.

### Step 7: Verify Simplicity Metrics

**Tool:** `shell`
**Parameters:**

```json
{"command": "radon cc src/services/complex_service.py -a --show-complexity && radon mi src/services/complex_service.py", "description": "Verify reduced complexity and improved maintainability"}
```

**Validation:** Complexity reduced by ≥ 50%. Maintainability index improved. All tests pass.

## Examples

### Example 1: Simplifying Nested Conditionals

**Input:** Function with 5-level deep nesting, 80 lines.

**Process:**

1. Measure: Cyclomatic complexity 15
2. Understand: Order processing with validation, discounts, shipping
3. Tests: Write 8 characterization tests covering all branches
4. Extract: Guard clauses for validation, separate functions for discount/shipping
5. Replace: Replace discount if-elif with DiscountStrategy classes
6. Remove: Eliminate duplicated validation logic
7. Verify: Complexity reduced to 4, MI improved from 65 to 85

**Output:** Clean, testable code with 73% complexity reduction.

### Example 2: Converting Callback Hell to Async/Await

**Input:** Deeply nested callback-based async code.

**Process:**

1. Measure: 6 levels of callback nesting
2. Understand: Data loading with sequential dependencies
3. Tests: Characterization tests for the full data flow
4. Extract: Each callback becomes an async function
5. Replace: Callbacks with `await` calls
6. Remove: Error handling duplication in each callback
7. Verify: Flat code structure, same behavior, easier error handling

**Output:** Linear async code that's readable and has centralized error handling.

### Example 3: Simplifying Configuration Parsing

**Input:** 200-line config parser with manual validation.

**Process:**

1. Measure: Complexity 12, 200 lines
2. Understand: Loads config, validates types, applies defaults
3. Tests: Tests for each config type and validation rule
4. Extract: Schema-based validation using pydantic
5. Replace: Manual validation with `ConfigModel.parse_obj()`
6. Remove: 150 lines of hand-written validation code
7. Verify: 50 lines instead of 200, complexity 3, all tests pass

**Output:** Schema-driven config with validation generated from types.

## Best Practices

- **Test first.** Always have characterization tests before simplifying.
- **One refactor at a time.** Make small changes, run tests, commit.
- **Use guard clauses.** Return early to reduce nesting.
- **Extract meaning.** Give extracted functions names that explain the "why".
- **Replace conditionals with polymorphism.** When you have 3+ branches, consider strategies.
- **Delete code.** The best code is no code. Remove unused logic aggressively.
- **Keep it boring.** Simple code should be boring to read. Exciting code is suspicious.
- **Refactor for clarity first.** Optimize for reading, not writing.
- **Avoid premature abstraction.** Don't create a factory factory. Keep it concrete.
- **Measure improvement.** Track complexity and maintainability scores before and after.