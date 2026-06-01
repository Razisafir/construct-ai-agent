---
name: performance-optimization
version: 1.0.0
category: devops
description: Profile, benchmark, and optimize code for speed, memory, and scalability
author: Construct AI
tools_needed: [shell, read_file, write_file, edit_file]
confidence: 0.95
---

# Performance Optimization

## Description

Systematically identify performance bottlenecks through profiling and benchmarking, then apply targeted optimizations. Covers CPU profiling, memory optimization, database query tuning, caching strategies, and load testing.

## When to Use

- Response times exceed SLA thresholds
- Memory usage grows unbounded
- Database queries are slow (> 100ms)
- High CPU usage under load
- Preparing for scale (launch, traffic spike)
- After profiling reveals hot paths

## Steps

### Step 1: Establish Baseline

**Tool:** `shell`
**Parameters:**

```json
{"command": "python -m pytest tests/benchmarks/ -v --benchmark-only --benchmark-json=baseline.json", "description": "Run benchmark suite to establish baseline"}
```

**Validation:** Baseline metrics captured: p50, p95, p99 response times, throughput (req/s), memory usage.

### Step 2: Profile to Find Hot Paths

**Tool:** `shell`
**Parameters:**

```json
{"command": "python -m cProfile -s cumtime -o profile.stats src/main.py --duration 60", "description": "CPU profile the application"}
```

**Also profile:**

```json
{"command": "snakeviz profile.stats", "description": "Visualize CPU profile"}
```

**Validation:** Top 5 time-consuming functions identified. Profile confirms where time is spent.

### Step 3: Analyze Memory Usage

**Tool:** `shell`
**Parameters:**

```json
{"command": "python -m memory_profiler src/main.py > memory-profile.txt", "description": "Profile memory usage line by line"}
```

**Also:**

```json
{"command": "python -c "import tracemalloc; tracemalloc.start(); import src.main; print(tracemalloc.get_traced_memory())"", "description": "Check peak memory usage"}
```

**Validation:** Memory hotspots identified. No unbounded growth detected.

### Step 4: Optimize Database Queries

**Tool:** `shell`
**Parameters:**

```json
{"command": "python -m django_extensions shell -c \"from django.db import connection; queries = connection.queries; print(f'Total: {len(queries)} queries, Time: {sum(float(q[\"time\"]) for q in queries)}s')\"", "description": "Count and time database queries"}
```

**Check for N+1:**

```json
{"command": "pytest tests/ -v --durations=10 --capture=no 2>&1 | grep -E '(SELECT|N\+1)' | head -20", "description": "Detect N+1 query patterns"}
```

**Validation:** Query count minimized. N+1 issues eliminated with `select_related`/`prefetch_related` or JOINs.

### Step 5: Implement Caching

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/src/services/data_service.py",
  "old_string": "def get_user_dashboard(user_id):\n    return expensive_computation(user_id)",
  "new_string": "from functools import lru_cache\nfrom redis_cache import redis_cache\n\n@redis_cache(ttl=300)\ndef get_user_dashboard(user_id):\n    return expensive_computation(user_id)\n\n@lru_cache(maxsize=1000)\ndef get_config_setting(key: str) -> str:\n    return db.query(Setting).filter_by(key=key).first().value"
}
```

**Validation:** Cache hit rates monitored. Stale cache issues prevented with proper TTL and invalidation.

### Step 6: Apply Algorithmic Optimizations

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/src/algorithms/search.py",
  "old_string": "def find_duplicates(items):\n    \"\"\"O(n^2) approach.\"\"\"\n    duplicates = []\n    for i, a in enumerate(items):\n        for b in items[i+1:]:\n            if a == b and a not in duplicates:\n                duplicates.append(a)\n    return duplicates",
  "new_string": "def find_duplicates(items):\n    \"\"\"O(n) approach with set.\"\"\"\n    seen = set()\n    duplicates = set()\n    for item in items:\n        if item in seen:\n            duplicates.add(item)\n        seen.add(item)\n    return list(duplicates)"
}
```

**Validation:** Algorithm complexity improved. Correctness verified with existing tests.

### Step 7: Benchmark After Optimization

**Tool:** `shell`
**Parameters:**

```json
{"command": "python -m pytest tests/benchmarks/ -v --benchmark-only --benchmark-json=optimized.json && python scripts/compare-benchmarks.py baseline.json optimized.json", "description": "Compare before and after benchmarks"}
```

**Validation:** Performance improvement measured and documented. Target: ≥ 20% improvement or within SLA.

### Step 8: Load Test

**Tool:** `shell`

```json
{"command": "locust -f tests/load/locustfile.py --host http://localhost:8000 -u 100 -r 10 --run-time 60s --headless", "description": "Load test with 100 concurrent users"}
```

**Validation:** System handles expected load with acceptable latency. No errors under load.

## Examples

### Example 1: API Response Time Optimization

**Input:** "Dashboard API takes 3 seconds to load."

**Process:**

1. Baseline: p50=3000ms, p95=5000ms, 50 DB queries
2. Profile: 80% time in sequential DB queries
3. Memory: Not a bottleneck
4. Queries: N+1 problem — 1 query for users, 49 for related data
5. Fix: `prefetch_related` reduces to 3 queries
6. Algorithm: Not applicable
7. Benchmark: p50=200ms (15x improvement), p95=350ms
8. Load test: 100 req/s with p95 < 500ms

**Output:** Dashboard loads in 200ms, 15x faster.

### Example 2: Memory Leak Fix

**Input:** "Service uses 2GB after 24 hours, starts with 200MB."

**Process:**

1. Baseline: 200MB startup, 2GB after 24h
2. Profile: Not a CPU issue
3. Memory: tracemalloc shows unbounded growth in request cache
4. Queries: Not applicable
5. Fix: Add maxsize and TTL to cache, periodic cleanup
6. Algorithm: Cache eviction policy changed
7. Benchmark: Stable at 250MB over 24h
8. Load test: Memory stable under sustained load

**Output:** Memory usage stabilized, 8x reduction in peak usage.

### Example 3: Report Generation Optimization

**Input:** "Monthly report generation times out after 30 seconds."

**Process:**

1. Baseline: Timeout at 30s, generates 10MB CSV
2. Profile: 90% time in string formatting and CSV writing
3. Memory: 500MB peak due to holding all rows in memory
4. Queries: 1 large query, streaming would help
5. Fix: Stream DB results, use `csv.writer` directly, generator pattern
6. Algorithm: Streaming instead of buffering
7. Benchmark: 5 seconds (6x improvement), memory constant 50MB
8. Load test: Handles concurrent report requests

**Output:** Report generates in 5 seconds with constant memory usage.

## Best Practices

- **Measure first.** Never optimize without profiling first — guesswork wastes time.
- **Optimize hot paths.** 80% of time is spent in 20% of code. Focus there.
- **Benchmark changes.** Every optimization must be measured; some "optimizations" hurt.
- **Cache carefully.** Caching adds complexity; ensure the benefit justifies it.
- **Database first.** Most performance issues are database-related.
- **Avoid premature optimization.** Write clear code first, optimize when needed.
- **Monitor in production.** Real-world performance differs from local benchmarks.
- **Set budgets.** Define performance budgets (e.g., p95 < 200ms) and enforce them in CI.
- **Use the right data structures.** Sets for membership, dicts for lookups, generators for large data.
- **Consider concurrency.** Async I/O or thread pools for I/O-bound work.