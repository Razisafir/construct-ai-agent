---
name: shipping-and-launch
version: 1.0.0
category: devops
description: Pre-launch checklist, release process, and go-live procedures
author: Construct AI
tools_needed: [write_file, read_file, shell]
confidence: 0.95
---

# Shipping and Launch

## Description

A structured approach to shipping software to production. Covers pre-launch checklists, release processes, monitoring setup, rollback procedures, and post-launch validation to ensure confident, reliable launches.

## When to Use

- Preparing for a production launch
- Major feature releases
- Production deployments
- Hotfix deployments
- Post-incident verification

## Steps

### Step 1: Pre-Launch Checklist

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/launch/checklist-v1.0.0.md",
  "content": "# Launch Checklist v1.0.0\n\n## Code Quality\n- [ ] All tests passing (unit, integration, e2e)\n- [ ] Code coverage >= 85%\n- [ ] Security scan clean (Bandit, dependency check)\n- [ ] Performance benchmarks within SLA\n- [ ] No critical or high bugs open\n\n## Documentation\n- [ ] README updated\n- [ ] API documentation current\n- [ ] ADRs written for major decisions\n- [ ] Runbooks created for common issues\n- [ ] Changelog updated\n\n## Infrastructure\n- [ ] Production environment configured\n- [ ] Database migrations tested on production-like data\n- [ ] Environment variables set\n- [ ] SSL certificates valid\n- [ ] CDN configured (if applicable)\n- [ ] Backup strategy verified\n\n## Monitoring\n- [ ] Application metrics configured (latency, errors, throughput)\n- [ ] Alerting rules set up with PagerDuty/Opsgenie\n- [ ] Log aggregation configured\n- [ ] Dashboard created\n- [ ] On-call rotation established\n\n## Security\n- [ ] Security headers configured\n- [ ] Rate limiting enabled\n- [ ] Authentication working in production\n- [ ] Secrets rotated\n- [ ] Penetration test passed\n\n## Rollback\n- [ ] Rollback procedure documented\n- [ ] Previous version artifact available\n- [ ] Database rollback tested\n- [ ] Feature flags configured (if applicable)\n"
}
```

**Validation:** Every item checked and signed off. No item skipped without documented risk acceptance.

### Step 2: Prepare Release Artifact

**Tool:** `shell`
**Parameters:**

```json
{"command": "python -m build && ls -la dist/", "description": "Build release artifacts"}
```

**Validation:** Artifact builds cleanly. Version matches tag. No uncommitted changes.

### Step 3: Run Final Verification Suite

**Tool:** `shell`
**Parameters:**

```json
{"command": "pytest tests/ -v --tb=short -q && echo 'ALL TESTS PASSED' || echo 'TESTS FAILED'", "description": "Run full test suite"}
```

**Validation:** 100% of tests pass. No warnings, no deprecations, no flaky tests.

### Step 4: Deploy to Staging

**Tool:** `shell`
**Parameters:**

```json
{"command": "./scripts/deploy.sh staging v1.0.0 && ./scripts/smoke-tests.sh staging", "description": "Deploy to staging and run smoke tests"}
```

**Validation:** Staging deployment successful. Smoke tests pass. No errors in logs.

### Step 5: Execute Production Deployment

**Tool:** `shell`
**Parameters:**

```json
{"command": "./scripts/deploy.sh production v1.0.0 --strategy blue-green", "description": "Deploy to production with blue-green strategy"}
```

**Validation:** Deployment completes without errors. Health checks pass. Traffic routing works.

### Step 6: Post-Launch Monitoring

**Tool:** `shell`
**Parameters:**

```json
{"command": "python scripts/monitor-launch.py --duration 30 --checks health,errors,latency,throughput", "description": "Monitor for 30 minutes post-launch"}
```

**Validation:** Monitoring dashboard shows: error rate < 0.1%, p95 latency < SLA, no 5xx errors.

### Step 7: Post-Launch Validation and Sign-Off

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/launch/post-launch-v1.0.0.md",
  "content": "# Post-Launch Report: v1.0.0\n\n## Launch Summary\n- **Version:** v1.0.0\n- **Date:** 2024-01-15 14:00 UTC\n- **Deployer:** Jane Doe\n- **Strategy:** Blue-green\n\n## Metrics (First 30 Minutes)\n- Error rate: 0.02% (target: < 0.1%)\n- P95 latency: 45ms (target: < 100ms)\n- Throughput: 1200 req/s\n- CPU usage: 35% average\n- Memory usage: 1.2GB average\n\n## Issues\n- None\n\n## Sign-Off\n- [x] Engineering: Jane Doe\n- [x] Product: John Smith\n- [x] QA: Alice Johnson\n\n## Notes\nLaunch was smooth. All systems nominal.\n"
}
```

**Validation:** All stakeholders signed off. Metrics within expected ranges. No outstanding issues.

## Examples

### Example 1: SaaS Feature Launch

**Input:** "Launch the new reporting feature."

**Process:**

1. Checklist: All items verified — tests 95%, security clean, docs updated
2. Artifact: Docker image v2.3.0 built and pushed
3. Verification: Full suite passes, performance tests within budget
4. Staging: Deployed, smoke tests pass, PM validates feature
5. Production: Blue-green deploy, 5-minute cutover
6. Monitor: 30-minute watch — 0 errors, 120ms p95 latency
7. Sign-off: Engineering, Product, and QA all approve

**Output:** Successful feature launch with zero customer impact.

### Example 2: Hotfix Deployment

**Input:** "Deploy critical security fix."

**Process:**

1. Checklist: Abbreviated — tests focused on fix area, security verified
2. Artifact: Emergency build v1.2.1-hotfix.1
3. Verification: Regression test for the specific vulnerability passes
4. Staging: Quick validation — 2 minutes
5. Production: Immediate deploy with monitoring
6. Monitor: Intensive 1-hour watch — all metrics nominal
7. Sign-off: Security team confirms vulnerability patched

**Output:** Critical fix deployed in under 30 minutes with full verification.

### Example 3: Infrastructure Migration Launch

**Input:** "Migrate from EC2 to Kubernetes."

**Process:**

1. Checklist: Extensive — infra tests, load tests, DR validation
2. Artifact: Helm charts v1.0.0, container images tagged
3. Verification: Load test at 2x expected traffic passes
4. Staging: Full parallel environment validation
5. Production: DNS cutover with 30-second TTL
6. Monitor: 2-hour watch — auto-scaling works, pods healthy
7. Sign-off: Infra, Engineering, and SRE teams sign off

**Output:** Smooth infrastructure migration with no downtime.

## Best Practices

- **Checklists are mandatory.** Never ship without a completed checklist.
- **Deploy during business hours.** Avoid Friday afternoon or holiday deployments.
- **Have a rollback plan.** Know exactly how to revert within 5 minutes.
- **Monitor aggressively.** Watch metrics closely for the first hour post-launch.
- **Communicate.** Notify stakeholders before, during, and after launch.
- **Feature flags.** Use flags to enable features gradually (canary releases).
- **Automate deployments.** Manual deployments are error-prone; automate everything.
- **Keep releases small.** Smaller releases are lower risk and easier to debug.
- **Post-mortem on issues.** If something goes wrong, document and learn.
- **Celebrate wins.** Shipping is hard work — acknowledge the team's effort.