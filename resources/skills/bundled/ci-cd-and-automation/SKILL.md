---
name: ci-cd-and-automation
version: 1.0.0
category: devops
description: Build CI/CD pipelines with GitHub Actions, Docker, and automated deployments
author: Construct AI
tools_needed: [write_file, shell, read_file]
confidence: 0.95
---

# CI/CD and Automation

## Description

Design and implement continuous integration and continuous deployment pipelines that automate testing, building, and releasing software. Includes GitHub Actions workflows, Docker containerization, and deployment strategies.

## When to Use

- Setting up CI for a new project
- Automating test runs on pull requests
- Building Docker images for deployment
- Setting up staging and production environments
- Implementing blue-green or canary deployments

## Steps

### Step 1: Create CI Workflow for Testing

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/.github/workflows/ci.yml",
  "content": "name: CI\n\non:\n  push:\n    branches: [main, develop]\n  pull_request:\n    branches: [main]\n\njobs:\n  test:\n    runs-on: ubuntu-latest\n    strategy:\n      matrix:\n        python-version: ['3.10', '3.11', '3.12']\n\n    steps:\n      - uses: actions/checkout@v4\n\n      - name: Set up Python\n        uses: actions/setup-python@v5\n        with:\n          python-version: ${{ matrix.python-version }}\n\n      - name: Install dependencies\n        run: |\n          pip install -e '.[dev]'\n\n      - name: Lint\n        run: |\n          ruff check src/\n          ruff format --check src/\n          mypy src/\n\n      - name: Test with coverage\n        run: |\n          pytest tests/ -v --cov=src --cov-report=xml --cov-fail-under=85\n\n      - name: Upload coverage\n        uses: codecov/codecov-action@v3\n        with:\n          files: ./coverage.xml\n"
}
```

**Validation:** Workflow triggers on PR and push. All checks (lint, type-check, test, coverage) run in parallel where possible.

### Step 2: Create Docker Configuration

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/Dockerfile",
  "content": "FROM python:3.11-slim AS builder\n\nWORKDIR /app\nCOPY pyproject.toml .\nRUN pip install --no-cache-dir -e '.[prod]'\n\nFROM python:3.11-slim AS runtime\n\nWORKDIR /app\nCOPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages\nCOPY --from=builder /usr/local/bin /usr/local/bin\nCOPY src/ ./src/\n\nRUN useradd -m appuser && chown -R appuser /app\nUSER appuser\n\nEXPOSE 8000\n\nHEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \\\n  CMD python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\"\n\nCMD ['uvicorn', 'src.main:app', '--host', '0.0.0.0', '--port', '8000']\n"
}
```

**Validation:** Docker image builds successfully and passes health check. Image size is minimized with multi-stage build.

### Step 3: Build and Push Docker Image

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/.github/workflows/docker.yml",
  "content": "name: Build and Push Docker\n\non:\n  push:\n    tags: ['v*']\n\njobs:\n  docker:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n\n      - name: Docker meta\n        id: meta\n        uses: docker/metadata-action@v5\n        with:\n          images: ghcr.io/${{ github.repository }}\n          tags: |\n            type=semver,pattern={{version}}\n            type=semver,pattern={{major}}.{{minor}}\n\n      - name: Set up Docker Buildx\n        uses: docker/setup-buildx-action@v3\n\n      - name: Login to registry\n        uses: docker/login-action@v3\n        with:\n          registry: ghcr.io\n          username: ${{ github.actor }}\n          password: ${{ secrets.GITHUB_TOKEN }}\n\n      - name: Build and push\n        uses: docker/build-push-action@v5\n        with:\n          context: .\n          push: true\n          tags: ${{ steps.meta.outputs.tags }}\n          labels: ${{ steps.meta.outputs.labels }}\n          cache-from: type=gha\n          cache-to: type=gha,mode=max\n"
}
```

**Validation:** Image builds and pushes on tag creation. Tags follow semantic versioning.

### Step 4: Create Deployment Workflow

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/.github/workflows/deploy-staging.yml",
  "content": "name: Deploy to Staging\n\non:\n  push:\n    branches: [develop]\n\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n    environment: staging\n    steps:\n      - uses: actions/checkout@v4\n\n      - name: Deploy to staging\n        run: |\n          echo '${{ secrets.KUBECONFIG }}' | base64 -d > kubeconfig\n          export KUBECONFIG=kubeconfig\n          kubectl set image deployment/app app=ghcr.io/${{ github.repository }}:${{ github.sha }}\n          kubectl rollout status deployment/app --timeout=300s\n\n      - name: Smoke tests\n        run: |\n          sleep 10\n          curl -sf https://staging.example.com/health || exit 1\n"
}
```

**Validation:** Deployment succeeds, rollout is verified, smoke tests pass.

### Step 5: Set Up Environment Protection

**Tool:** `shell`
**Parameters:**

```json
{"command": "gh api repos/{owner}/{repo}/environments/staging --field wait_timer=0 --field reviewers='[]'", "description": "Configure environment protection rules"}
```

**Validation:** Production deployments require manual approval. Staging deploys automatically.

### Step 6: Add Deployment Notifications

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/.github/workflows/deploy-production.yml",
  "old_string": "      - name: Smoke tests\n        run: |\n          sleep 10\n          curl -sf https://staging.example.com/health || exit 1",
  "new_string": "      - name: Smoke tests\n        run: |\n          sleep 10\n          curl -sf https://staging.example.com/health || exit 1\n\n      - name: Notify Slack\n        if: always()\n        uses: slackapi/slack-github-action@v1\n        with:\n          payload: |\n            {\n              'text': 'Deployment to production ${{ job.status }}: ${{ github.event.head_commit.message }}'\n            }\n        env:\n          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}"
}
```

**Validation:** Notifications sent on success and failure. Message includes deployment status and commit info.

### Step 7: Verify Pipeline End-to-End

**Tool:** `shell`
**Parameters:**

```json
{"command": "act push -e .github/test-event.json -s GITHUB_TOKEN=fake --dry-run", "description": "Test workflow locally with act"}
```

**Validation:** Full pipeline tested: PR → CI passes → Merge → Build image → Deploy → Notify.

## Examples

### Example 1: Full Pipeline for Python API

**Input:** "Set up CI/CD for a Python FastAPI service."

**Process:**

1. CI: Test on Python 3.10/3.11/3.12 with lint, type-check, coverage
2. Docker: Multi-stage build, slim base, non-root user, health check
3. Registry: Push to GHCR on version tags
4. Staging: Auto-deploy on merge to develop, smoke tests
5. Production: Manual approval, blue-green deployment
6. Notifications: Slack alerts for deployments and failures
7. Verify: End-to-end test with local `act`

**Output:** Complete CI/CD pipeline from PR to production.

### Example 2: Monorepo CI Setup

**Input:** "Configure CI for a monorepo with frontend and backend."

**Process:**

1. CI: Path-based triggers — only run frontend checks when frontend/ changes
2. Docker: Separate images for frontend (nginx) and backend (python)
3. Registry: Push both images with the same version tag
4. Staging: Deploy both services with docker-compose
5. Production: Kubernetes deployment with ingress
6. Notifications: Per-service deployment notifications
7. Verify: Changed-path detection works correctly

**Output:** Efficient monorepo CI that only builds what changed.

### Example 3: Legacy App Migration to Docker

**Input:** "Containerize a legacy Django application."

**Process:**

1. CI: Add tests first (there were none), then lint and type-check
2. Docker: Create Dockerfile with proper settings.py for containers
3. Registry: Push to private registry
4. Staging: Docker Compose with PostgreSQL and Redis
5. Production: Kubernetes with persistent volumes for uploads
6. Notifications: Email on deployment
7. Verify: Feature parity between containerized and bare-metal

**Output:** Legacy app successfully containerized and deployed.

## Best Practices

- **Fail fast.** Run linting and fast checks before slow tests.
- **Parallelize.** Run independent jobs in parallel to reduce pipeline time.
- **Cache aggressively.** Cache dependencies, Docker layers, and build artifacts.
- **Immutable artifacts.** Build once, deploy the same artifact to all environments.
- **Secrets in CI only.** Never commit secrets; use CI environment variables.
- **Smoke tests after deploy.** Verify the deployment worked before considering it done.
- **Rollback plan.** Every deployment should have a one-command rollback.
- **Audit trail.** Log who deployed what and when.
- **Environment parity.** Keep staging as close to production as possible.
- **Automate everything.** If you do it manually more than twice, automate it.