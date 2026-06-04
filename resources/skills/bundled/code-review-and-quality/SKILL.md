---
name: code-review-and-quality
version: 1.0.0
category: coding
description: Review code for correctness, security, performance, and maintainability with structured feedback
author: Construct AI
tools_needed: [read_file, shell, write_file]
confidence: 0.95
---

# Code Review and Quality

## Description

Systematic code review process that evaluates code across multiple dimensions: correctness, security, performance, test coverage, maintainability, and adherence to team standards. Provides structured, actionable feedback.

## When to Use

- Reviewing pull requests from team members
- Conducting pre-commit self-review
- Auditing code for security or compliance
- Onboarding review for new team members
- Refactoring review to ensure quality is maintained

## Steps

### Step 1: Understand the Context

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/docs/pr-description.md"}
```

**Validation:** Understand: what problem this PR solves, why this approach was chosen, what files changed, any trade-offs discussed.

### Step 2: Review Test Coverage

**Tool:** `shell`
**Parameters:**

```json
{"command": "pytest --cov=src --cov-report=term-missing --cov-fail-under=80 tests/", "description": "Check test coverage"}
```

**Validation:** Coverage is ≥ 80%. New code has tests. Edge cases are covered.

### Step 3: Check for Security Issues

**Tool:** `shell`
**Parameters:**

```json
{"command": "bandit -r src/ -f json -o bandit-report.json", "description": "Run security scan"}
```

**Validation:** No high or medium severity issues. SQL injection, XSS, hardcoded secrets checked.

**Also check:**

```json
{"command": "git diff HEAD~1 | grep -E '(password|secret|token|key|api_key)' || true", "description": "Check for hardcoded secrets in diff"}
```

### Step 4: Review Code Structure and Patterns

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/src/services/new_feature.py"}
```

**Validation:** Checklist:

- [ ] Follows existing architectural patterns
- [ ] Functions are small and focused (< 50 lines)
- [ ] Naming is clear and consistent
- [ ] No code duplication (DRY)
- [ ] Proper error handling
- [ ] Type hints throughout
- [ ] Documentation for public APIs

### Step 5: Verify Performance Implications

**Tool:** `shell`
**Parameters:**

```json
{"command": "python -m cProfile -s cumulative src/benchmark_new_code.py", "description": "Profile performance of new code"}
```

**Validation:** No N+1 queries. No unnecessary memory allocation. Time complexity is appropriate.

### Step 6: Check for Maintainability

**Tool:** `shell`
**Parameters:**

```json
{"command": "radon cc src/ -a -nc && radon mi src/ -nc", "description": "Check cyclomatic complexity and maintainability"}
```

**Validation:** Cyclomatic complexity < 10 per function. Maintainability index > 80.

### Step 7: Write Structured Review

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/reviews/review-{pr-number}.md",
  "content": "# Code Review: PR #{number}\n\n## Summary\nLGTM with minor suggestions.\n\n## Checklist\n- [x] Tests pass and coverage adequate\n- [x] No security issues\n- [x] Follows coding standards\n- [x] Documentation updated\n\n## Suggestions\n1. Extract the validation logic into a separate function (complexity: 12)\n2. Add a comment explaining the retry logic\n3. Consider using `functools.lru_cache` for the repeated DB lookup\n\n## Required Changes\nNone\n\n## Questions\n1. Why was `threading.Lock` chosen over `asyncio.Lock` in the async function?\n"
}
```

**Validation:** Review is specific, actionable, and respectful. Distinguishes required changes from suggestions.

## Examples

### Example 1: Reviewing a New API Endpoint

**Input:** "Review PR adding user search endpoint."

**Process:**

1. Context: Adds `/api/v1/users/search` with full-text search
2. Tests: 85% coverage, missing test for SQL injection attempt
3. Security: Bandit clean, but raw SQL in query — verify parameterized
4. Structure: Service function is 80 lines — suggest splitting
5. Performance: Full-text search uses GIN index — confirmed in migration
6. Maintainability: Complexity 8, MI 85 — acceptable
7. Review: Approve with suggestions for test addition and function split

**Output:** Approved PR with specific improvement suggestions.

### Example 2: Reviewing a Refactor

**Input:** "Review PR refactoring the payment module."

**Process:**

1. Context: Extracts PaymentService from monolithic OrderService
2. Tests: Existing tests updated, 2 new integration tests added
3. Security: No changes to security-sensitive code
4. Structure: Clean separation of concerns, good interfaces
5. Performance: No measurable change in benchmarks
6. Maintainability: Complexity reduced from 25 to 8 in main function
7. Review: Approve, praise the complexity reduction

**Output:** Approved PR with positive feedback on maintainability improvement.

### Example 3: Security-Focused Review

**Input:** "Review PR adding file upload functionality."

**Process:**

1. Context: Adds image upload for user avatars
2. Tests: Upload success/failure covered
3. Security: Bandit flags `eval()` in filename processing — CRITICAL
4. Structure: Standard multipart handling
5. Performance: File size limit enforced (5MB)
6. Maintainability: Good, but security issue must be fixed
7. Review: Request changes — remove `eval()`, add MIME type validation

**Output:** PR blocked until critical security issue is resolved.

## Best Practices

- **Automate the boring stuff.** Use linters, formatters, and security scanners first.
- **Review within 24 hours.** Slow reviews block progress and cause merge conflicts.
- **Be specific.** 'This is bad' is useless; 'Extract lines 45-60 into a function named X' is actionable.
- **Distinguish required vs. optional.** Label feedback as 'required', 'suggestion', or 'question'.
- **Praise good work.** Highlight excellent patterns, not just issues.
- **Ask questions.** 'Why did you choose X?' is better than 'Don't use X'.
- **Review your own code first.** Self-review catches 50% of issues before others see them.
- **Check the diff, not the file.** Focus on what changed, not the entire file.
- **Verify manually when needed.** Automated checks don't catch everything; run the code locally.
- **Follow up.** Check that requested changes were actually made.