---
name: git-workflow-and-versioning
version: 1.0.0
category: devops
description: Branch strategies, commit conventions, semantic versioning, and release management
author: Construct AI
tools_needed: [shell, read_file, write_file]
confidence: 0.95
---

# Git Workflow and Versioning

## Description

Establish and follow disciplined Git workflows with conventional commits, semantic versioning, and structured release processes. Supports trunk-based development, GitFlow, and PR-based workflows.

## When to Use

- Starting a new project and need a branching strategy
- Preparing a release or hotfix
- Setting up CI/CD pipeline triggers
- Coordinating work across a team
- Creating changelogs and release notes

## Steps

### Step 1: Choose and Configure Branch Strategy

**Tool:** `shell`
**Parameters:**

```json
{"command": "git checkout -b develop && git push -u origin develop", "description": "Set up GitFlow with develop branch"}
```

**Validation:** Branch protection rules configured:

```json
{"command": "gh api repos/{owner}/{repo}/branches/main/protection --field required_status_checks[0]=ci --field enforce_admins=true", "description": "Configure branch protection"}
```

**Required checks:**

- [ ] `main` branch requires PR reviews
- [ ] `main` branch requires CI to pass
- [ ] No direct pushes to `main`
- [ ] `develop` branch (if using GitFlow) similarly protected

### Step 2: Configure Commit Conventions

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/.commitlintrc.json",
  "content": "{\n  'extends': ['@commitlint/config-conventional'],\n  'rules': {\n    'type-enum': [2, 'always', ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore', 'perf', 'ci']],\n    'subject-case': [0],\n    'subject-empty': [2, 'never'],\n    'type-empty': [2, 'never'],\n    'body-max-line-length': [2, 'always', 100]\n  }\n}\n"
}
```

**Validation:** Commits follow the pattern: `type(scope): subject`. Types are from the conventional commits spec.

### Step 3: Write a Proper Commit

**Tool:** `shell`
**Parameters:**

```json
{"command": "git commit -m 'feat(auth): add OAuth2 login with Google\n\n- Implement Google OAuth2 flow\n- Add JWT token generation\n- Store refresh tokens securely\n\nCloses #123'", "description": "Create conventional commit"}
```

**Validation:** Commit message includes: type, scope, description, body with details, issue reference.

### Step 4: Set Up Semantic Versioning

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/pyproject.toml",
  "content": "[tool.semantic_release]\nversion_toml = ['pyproject.toml:project.version']\nversion_variables = ['src/__init__.py:__version__']\nbranch = 'main'\nbuild_command = 'pip install build && python -m build'\ndist_path = 'dist/'\nupload_to_release = true\nupload_to_pypi = false\ncommit_message = 'chore(release): bump version to {version}'\n"
}
```

**Validation:** Version bumping is automated based on commit types: `feat` → minor, `fix` → patch, `BREAKING CHANGE` → major.

### Step 5: Create a Release

**Tool:** `shell`
**Parameters:**

```json
{"command": "git tag -a v1.2.0 -m 'Release v1.2.0 - OAuth2 and Performance' && git push origin v1.2.0", "description": "Create annotated version tag"}
```

**Validation:** Tag follows semver (vMAJOR.MINOR.PATCH). Tag points to a commit on the main branch.

### Step 6: Generate Changelog

**Tool:** `shell`
**Parameters:**

```json
{"command": "git-chglog --next-tag v1.2.0 -o CHANGELOG.md", "description": "Generate changelog from conventional commits"}
```

**Validation:** CHANGELOG.md includes all commits since last tag, grouped by type (Features, Bug Fixes, etc.).

### Step 7: Hotfix Workflow

**Tool:** `shell`
**Parameters:**

```json
{"command": "git checkout -b hotfix/v1.2.1 main && git commit -m 'fix(auth): resolve token expiration bug' && git checkout main && git merge hotfix/v1.2.1 && git tag v1.2.1", "description": "Create and apply hotfix"}
```

**Validation:** Hotfix branches from `main`, gets tagged, and is merged back to `develop` if using GitFlow.

## Examples

### Example 1: Feature Development Workflow

**Input:** "Implement a new feature following team workflow."

**Process:**

1. Strategy: GitFlow — create `feature/user-profiles` from `develop`
2. Commits: 5 commits all following conventional format
3. PR: Open PR with template, link to issue, request review
4. Review: Address feedback, squash fix commits
5. Merge: Merge to `develop` with merge commit
6. Release: When ready, merge `develop` → `main`, tag v1.3.0
7. Changelog: Auto-generated from commits

**Output:** Clean history, automated changelog, proper version bump.

### Example 2: Hotfix Production Issue

**Input:** "Critical bug in production needs immediate fix."

**Process:**

1. Branch: `hotfix/v2.1.1` from `main`
2. Fix: Single focused commit `fix(payments): resolve race condition`
3. Test: Add regression test for the bug
4. PR: Fast-track review, emergency approval
5. Merge: Merge to `main`, tag v2.1.1
6. Deploy: Automated deployment of hotfix
7. Backport: Cherry-pick to `develop`

**Output:** Production fixed in < 1 hour with proper version and audit trail.

### Example 3: Setting Up New Project

**Input:** "Configure Git workflow for a new microservice."

**Process:**

1. Strategy: Trunk-based with short-lived feature branches
2. Conventions: Commitlint + husky pre-commit hooks
3. Protection: Branch protection on `main`, required reviews
4. Versioning: Semantic release with auto-publish
5. CI: GitHub Actions run on PR and push to main
6. Release: Automated on merge with proper changelog
7. Hotfix: Documented process for emergencies

**Output:** Fully configured Git workflow with automated releases.

## Best Practices

- **Commit often, commit small.** Each commit should be a logical unit of work.
- **Write descriptive messages.** Future you (and teammates) will thank you.
- **Never force push to shared branches.** Rewrite history only on personal feature branches.
- **Use meaningful branch names.** `feature/user-auth` not `branch-123`.
- **Keep feature branches short-lived.** Merge within 1-3 days to avoid drift.
- **Tag releases.** Every production deployment should have a version tag.
- **Sign your commits.** Use GPG signing for integrity verification.
- **Review before merge.** No code reaches main without peer review.
- **Automate releases.** Let CI handle versioning and changelog generation.
- **Document your workflow.** New team members should find a WORKFLOW.md file.