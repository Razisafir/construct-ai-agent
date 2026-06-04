---
name: debugging-and-error-recovery
version: 1.0.0
category: coding
description: Systematic debugging methodology with structured error recovery and root cause analysis
author: Construct AI
tools_needed: [read_file, shell, write_file, edit_file]
confidence: 0.95
---

# Debugging and Error Recovery

## Description

A systematic approach to debugging that moves from symptom identification to root cause analysis through structured investigation. Includes logging strategies, diagnostic techniques, and error recovery patterns.

## When to Use

- A bug is reported but the cause is unknown
- Intermittent failures in production
- Performance degradation without clear cause
- Error rates spike after a deployment
- Complex multi-system interaction failures

## Steps

### Step 1: Reproduce the Issue

**Tool:** `shell`
**Parameters:**

```json
{"command": "python scripts/reproduce.py --scenario 'user-login-failure' --user-id 12345 --verbose", "description": "Reproduce the reported issue"}
```

**Validation:** Can consistently reproduce the failure. Document exact steps and environment.

**Output:** Reproduction script with expected vs actual behavior documented.

### Step 2: Gather Diagnostic Information

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/var/log/app/error.log"}
```

**Validation:** Logs contain: timestamp, error message, stack trace, request context, user ID. If not, add logging first.

**Also check:**

```json
{"command": "journalctl -u myapp --since '1 hour ago' | tail -100", "description": "Check system logs for errors"}
```

### Step 3: Formulate Hypotheses

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/debug/hypotheses.md",
  "content": "# Debugging Hypotheses\n\n## Symptom\nUser login fails intermittently (5% of requests)\n\n## Hypotheses (ranked by likelihood)\n1. [HIGH] Database connection pool exhausted under load\n2. [MEDIUM] Race condition in session token generation\n3. [MEDIUM] Third-party auth service timeout\n4. [LOW] Clock skew causing JWT validation failures\n5. [LOW] Memory leak in session store\n\n## Tests for Each\n1. Check connection pool metrics during peak load\n2. Add logging around token generation with timestamps\n3. Monitor auth service response times\n4. Compare server clocks, check NTP sync\n5. Profile memory usage over time\n"
}
```

**Validation:** Each hypothesis is testable and has a defined validation method.

### Step 4: Test Hypotheses Systematically

**Tool:** `shell`
**Parameters:**

```json
{"command": "python scripts/monitor-db-pool.py --duration 300 --output pool-metrics.json", "description": "Monitor DB connection pool metrics"}
```

**Validation:** Data collected supports or refutes the hypothesis. Document results.

### Step 5: Isolate the Root Cause

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/src/services/auth_service.py", "offset": 45, "limit": 30}
```

**Validation:** Found the exact code causing the issue. Can explain the chain from trigger to symptom.

**Root cause documentation:**

```json
{
  "file_path": "/docs/debug/root-cause.md",
  "content": "# Root Cause Analysis\n\n## Cause\nConnection pool max_size=10, but 15 concurrent login requests during peak\ncause pool exhaustion. Subsequent requests timeout after 30s.\n\n## Chain\nPeak traffic → 15 concurrent logins → 10 DB connections taken →\n5 requests wait → 30s timeout → login failure → user sees 'Something went wrong'\n\n## Fix\nIncrease pool max_size to 50, add connection timeout of 5s with proper error message.\n"
}
```

### Step 6: Implement the Fix

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/src/config/database.py",
  "old_string": "pool_size=10, max_overflow=5, pool_timeout=30",
  "new_string": "pool_size=20, max_overflow=30, pool_timeout=5"
}
```

**Validation:** Fix addresses root cause, not just symptom. Change is minimal and focused.

### Step 7: Verify the Fix and Add Regression Test

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/tests/test_connection_pool.py",
  "content": "import pytest\nfrom concurrent.futures import ThreadPoolExecutor\nfrom src.services.auth_service import login\n\ndef test_concurrent_logins_dont_exhaust_pool():\n    \"\"\"Regression test for connection pool exhaustion bug.\"\"\"\n    with ThreadPoolExecutor(max_workers=50) as executor:\n        futures = [executor.submit(login, f'user{i}@test.com', 'pass')\n                   for i in range(50)]\n        results = [f.result(timeout=10) for f in futures]  # Should not timeout\n    assert all(r.success for r in results)\n"
}
```

**Validation:** Test fails on old code, passes on fixed code. Test runs in CI.

### Step 8: Run Full Regression Suite

**Tool:** `shell`
**Parameters:**

```json
{"command": "pytest tests/ -v --cov=src --cov-fail-under=85 -x", "description": "Run full test suite to check for regressions"}
```

**Validation:** All tests pass. No new failures introduced by the fix.

## Examples

### Example 1: Memory Leak in Production

**Input:** "Service memory grows 100MB per hour and gets OOM-killed."

**Process:**

1. Reproduce: Run load test locally, observe memory growth
2. Gather: Heap dumps, object allocation traces
3. Hypotheses: [1] Unclosed DB connections [2] Cached objects growing [3] Circular references
4. Test: tracemalloc shows `UserCache` dict growing unbounded
5. Root cause: Cache has no eviction policy, entries added but never removed
6. Fix: Add TTL and max_size to cache with LRU eviction
7. Verify: Memory stable under load test, regression test added
8. Regression: Full suite passes

**Output:** Fixed memory leak with bounded cache and monitoring.

### Example 2: Race Condition in Payment Processing

**Input:** "Duplicate charges occasionally processed."

**Process:**

1. Reproduce: Run parallel payment requests in test environment
2. Gather: Request logs, database transaction logs
3. Hypotheses: [1] Missing unique constraint [2] Idempotency key not checked atomically [3] Double-submit from UI
4. Test: Two identical requests within 10ms both succeed
5. Root cause: Idempotency check and charge are not in the same transaction
6. Fix: Wrap idempotency check + charge in single DB transaction
7. Verify: Parallel test now shows one success, one idempotent return
8. Regression: Full suite passes

**Output:** Race condition eliminated with atomic idempotency check.

### Example 3: Slow Query After Migration

**Input:** "Dashboard load time increased from 2s to 15s after DB migration."

**Process:**

1. Reproduce: Run dashboard query locally with production-sized dataset
2. Gather: EXPLAIN ANALYZE output, query execution plan
3. Hypotheses: [1] Missing index [2] Changed query pattern [3] Lock contention
4. Test: EXPLAIN shows sequential scan on 10M row table
5. Root cause: Migration dropped index on `created_at` column, new query uses it
6. Fix: Recreate index: `CREATE INDEX CONCURRENTLY idx_orders_created_at ON orders(created_at)`
7. Verify: Query time back to <2s, regression test with EXPLAIN check
8. Regression: Full suite passes

**Output:** Performance restored with proper indexing, migration checklist updated.

## Best Practices

- **Reproduce first.** Never attempt to fix a bug you can't reproduce.
- **One change at a time.** Test one hypothesis before moving to the next.
- **Document everything.** Keep a log of hypotheses, tests, and results.
- **Fix the root cause.** Don't patch symptoms; understand and fix the underlying issue.
- **Add regression tests.** Every bug fix should include a test that would have caught it.
- **Monitor after fix.** Watch metrics post-deployment to confirm the fix worked.
- **Share learnings.** Write a post-mortem for significant bugs.
- **Use structured logging.** Correlation IDs, context, and structured fields make debugging faster.
- **Git bisect.** Use `git bisect` to find the exact commit that introduced a bug.
- **Minimal reproduction.** The smaller the reproduction case, the faster you'll find the cause.