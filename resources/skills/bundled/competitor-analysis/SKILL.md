---
name: competitor-analysis
description: Analyzes competitor codebases or APIs for feature gaps, performance differences, and architectural choices
category: research
version: 1.0.0
author: Construct
---

# Competitor Analysis

## Overview

The **Competitor Analysis** skill systematically evaluates competitor codebases, APIs, and public artifacts to identify feature gaps, performance differentials, architectural patterns, and strategic opportunities. It reverse-engineers public APIs, analyzes open-source repositories, benchmarks execution characteristics, and produces actionable intelligence for product teams. This skill enables data-driven competitive positioning and informed technical decision-making.

## Checks Performed

- **Feature Gap Analysis**: Compares your product's feature set against competitors to identify missing capabilities
- **Performance Benchmarking**: Measures API latency, throughput, and resource utilization relative to competitors
- **Architectural Patterns**: Identifies technology stacks, design patterns, and infrastructure choices used by competitors
- **API Surface Analysis**: Maps competitor API endpoints, data models, authentication mechanisms, and rate limits
- **Documentation Quality**: Evaluates the completeness and developer experience of competitor documentation
- **Community & Ecosystem**: Assesses open-source contributions, plugin ecosystems, and third-party integrations
- **Security Posture**: Analyzes publicly visible security headers, TLS configurations, and vulnerability history
- **Pricing & Packaging**: Correlates technical capabilities with pricing tiers and feature gating strategies

## Execution Steps

1. **Define Competitor Scope**
   - Identify 3-5 direct competitors and 2-3 adjacent players
   - Gather all publicly accessible URLs: GitHub repos, API docs, developer portals
   - Document the analysis timeframe and data sources for reproducibility

2. **Gather Public Artifacts**
   - Clone competitor open-source repositories using `git clone --depth 1`
   - Download public API specifications (OpenAPI/Swagger, GraphQL schemas, gRPC proto files)
   - Collect documentation pages, blog posts, and release notes
   - Archive publicly available SDKs, CLIs, and developer tools

3. **Analyze Technology Stack**
   - Detect primary languages, frameworks, and infrastructure from repository structure
   - Identify dependency management files (`package.json`, `requirements.txt`, `go.mod`, `pom.xml`)
   - Map CI/CD configurations and deployment platforms
   - Catalog third-party services and integrations from configuration files

4. **Map API Surface Area**
   - Parse OpenAPI specs to enumerate endpoints, methods, request/response schemas
   - Identify authentication mechanisms (OAuth 2.0, API keys, JWT, mTLS)
   - Document rate limiting headers and pagination strategies
   - Compare API versioning approaches (URL path, header, content negotiation)

5. **Benchmark Performance**
   - Execute standardized API calls with `curl`/`wrk`/`hey`/`k6` to measure latency
   - Test throughput under concurrent load (10, 100, 1000 concurrent requests)
   - Measure cold-start times for serverless functions if applicable
   - Document geographical performance variance using distributed testing

6. **Evaluate Feature Set**
   - Create a feature matrix comparing your product against each competitor
   - Score features on: availability, maturity (alpha/beta/GA), ease of use, documentation quality
   - Identify features present in competitors but absent in your product (gaps)
   - Identify features your product has that competitors lack (differentiators)

7. **Assess Architecture & Code Quality**
   - Run static analysis tools (`eslint`, `pylint`, `cloc`, `scc`) on cloned repos
   - Evaluate test coverage ratios from CI configuration or coverage reports
   - Analyze commit frequency, contributor count, and issue resolution velocity
   - Review architectural decision records (ADRs) and RFC documents

8. **Synthesize Strategic Report**
   - Compile findings into a structured report with executive summary
   - Prioritize feature gaps by user impact and implementation effort
   - Recommend architectural improvements based on competitor best practices
   - Output: `competitor-analysis-report.md` with actionable product roadmap items

## Examples

### Example 1: API Feature Gap Analysis

**Input:**
```bash
/competitor-analysis --targets api-docs.acme.com,api-docs.globex.com --mode api-compare --product my-api
```

**Execution:**
```bash
# Fetch OpenAPI specs
curl -s https://api-docs.acme.com/openapi.json > acme_spec.json
curl -s https://api-docs.globex.com/swagger.json > globex_spec.json

# Parse and compare
python3 -c "
import json
acme = json.load(open('acme_spec.json'))
globex = json.load(open('globex_spec.json'))
print(f'Acme endpoints: {len(acme[\"paths\"])}')
print(f'Globex endpoints: {len(globex[\"paths\"])}')
"
```

**Output:**
```markdown
## API Feature Gap Analysis

### Endpoint Comparison

| Feature | My API | Acme API | Globex API |
|---------|--------|----------|------------|
| Authentication (OAuth2) | Yes | Yes | Yes |
| Webhooks | Yes | Yes | No |
| Rate Limit Headers | Yes | Yes | Yes |
| Bulk Operations | No | Yes | Yes |
| GraphQL Support | No | No | Yes |
| Real-time Streaming | Yes | No | Yes |
| Multi-region | No | Yes | Yes |

### Critical Gaps Identified

1. **Bulk Operations** (HIGH PRIORITY)
   - Both Acme and Globex support batch create/update/delete
   - Our API requires individual API calls → 10x more requests for bulk workflows
   - **Recommendation**: Implement batch endpoints with transactional semantics

2. **Multi-region Deployment** (MEDIUM PRIORITY)
   - Acme offers 12 regions, Globex offers 8
   - We are single-region with 150ms+ latency for EU/APAC users
   - **Recommendation**: Deploy edge POPs in EU-West and APAC-Southeast

3. **GraphQL Support** (LOW PRIORITY)
   - Only Globex offers GraphQL; REST still dominant
   - **Recommendation**: Evaluate demand before investment
```

### Example 2: Open-Source Repository Benchmark

**Input:**
```bash
/competitor-analysis --repos https://github.com/acme/cache-lib,https://github.com/globex/cache-lib --lang rust
```

**Execution:**
```bash
# Clone and analyze
git clone --depth 1 https://github.com/acme/cache-lib.git /tmp/acme-cache
git clone --depth 1 https://github.com/globex/cache-lib.git /tmp/globex-cache

# Run benchmarks
cd /tmp/acme-cache && cargo bench > acme_bench.txt
cd /tmp/globex-cache && cargo bench > globex_bench.txt

# Count code metrics
scc /tmp/acme-cache /tmp/globex-cache
```

**Output:**
```json
{
  "analysis": "cache-library-benchmark",
  "date": "2024-01-15T09:30:00Z",
  "repositories": {
    "acme-cache-lib": {
      "language": "Rust",
      "loc": 12450,
      "test_coverage": 94.2,
      "benchmarks": {
        "get_latency_p99": "120ns",
        "set_latency_p99": "180ns",
        "concurrent_reads_1000": "2.1M ops/sec",
        "memory_overhead": "12 bytes/entry"
      },
      "dependencies": 8,
      "last_commit": "2024-01-10",
      "contributors": 23
    },
    "globex-cache-lib": {
      "language": "Rust",
      "loc": 32100,
      "test_coverage": 87.5,
      "benchmarks": {
        "get_latency_p99": "85ns",
        "set_latency_p99": "140ns",
        "concurrent_reads_1000": "3.4M ops/sec",
        "memory_overhead": "8 bytes/entry"
      },
      "dependencies": 15,
      "last_commit": "2024-01-14",
      "contributors": 41
    }
  },
  "recommendations": [
    {
      "priority": "high",
      "action": "Adopt lock-free read path similar to globex-cache-lib",
      "expected_improvement": "~40% reduction in get latency"
    },
    {
      "priority": "medium",
      "action": "Reduce memory overhead per entry from 12B to <10B",
      "expected_improvement": "~20% memory savings at scale"
    }
  ]
}
```

### Example 3: Documentation DX Comparison

**Input:**
```bash
/competitor-analysis --docs https://docs.acme.com,https://docs.globex.com,https://docs.initech.com --mode docs
```

**Output:**
```markdown
## Documentation Developer Experience (DX) Scorecard

### Scoring Rubric (1-10)

| Criteria | Acme | Globex | Initech | Our Docs |
|----------|------|--------|---------|----------|
| Quickstart Time (< 5 min) | 9 | 7 | 4 | 6 |
| API Reference Completeness | 10 | 8 | 6 | 7 |
| Code Examples (per endpoint) | 8 | 5 | 2 | 4 |
| Error Handling Documentation | 7 | 6 | 3 | 5 |
| SDK Availability | 9 | 9 | 7 | 8 |
| Interactive Playground | Yes | No | No | Yes |
| Changelog Currency | 9 | 8 | 5 | 7 |
| **Overall DX Score** | **8.7** | **7.2** | **4.5** | **6.2** |

### Key Insights

- **Acme leads** in API reference quality with auto-generated interactive examples
- **Globex** has strong SDKs but weak code examples (average 1.2 per endpoint)
- **Our docs** should prioritize: more code examples, better error documentation
- Initech is a distant 4th; not a direct threat in developer experience
```

## Validation Criteria

- [ ] At least 3 direct competitors are identified and analyzed
- [ ] Technology stack is accurately detected for each competitor
- [ ] API surface area is fully mapped with authentication and rate limit details
- [ ] Performance benchmarks include latency percentiles (p50, p95, p99) under load
- [ ] Feature gap matrix covers all major product capabilities
- [ ] Code quality metrics (test coverage, LOC, contributor count) are documented
- [ ] Report includes prioritized recommendations with effort estimates
- [ ] All data sources are cited with access dates for reproducibility
- [ ] No proprietary or non-public data is accessed or included

## Best Practices

- Conduct competitor analysis **quarterly** to stay current with market changes
- Focus on publicly available data only — never attempt to access private repositories or APIs
- Use consistent benchmarking methodology to enable trend analysis over time
- Share findings across product, engineering, and leadership teams
- Prioritize gaps by combining user feedback with competitive intelligence
- Respect robots.txt and API rate limits when scraping documentation
- Document assumptions and limitations in every analysis report
- Keep raw data archived for reproducibility and compliance
- Combine quantitative metrics (benchmarks) with qualitative assessment (UX, DX)
- Use the findings to inform roadmap prioritization, not to copy features blindly

## Tools Required

| Tool | Purpose |
|------|---------|
| `git` | Clone competitor repositories |
| `curl` / `wget` | Fetch API specs and documentation |
| `wrk` / `hey` / `k6` | API performance benchmarking |
| `scc` / `cloc` | Source code metrics and language detection |
| `jq` | Parse and compare JSON API specifications |
| `openapi-generator` | Parse and validate OpenAPI/Swagger specs |
| `postman` / `httpie` | Manual API exploration and testing |
| `openssl s_client` | TLS configuration analysis |
| `spider` / `wget --mirror` | Documentation site crawling |

## Related Skills

- `market-research-brief` — Broader market trend analysis and user needs research
- `repo-audit` — Repository health checks applicable to cloned competitor repos
- `brand-name-forge` — Naming and branding strategy based on competitive landscape
