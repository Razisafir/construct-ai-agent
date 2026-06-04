---
name: deprecation-and-migration
version: 1.0.0
category: devops
description: Safely deprecate APIs, features, and migrate users with zero downtime
author: Construct AI
tools_needed: [write_file, read_file, edit_file, shell]
confidence: 0.95
---

# Deprecation and Migration

## Description

Safely deprecate APIs, features, and dependencies while maintaining backward compatibility and providing clear migration paths. Minimize disruption to users and ensure zero-downtime transitions.

## When to Use

- Replacing an old API with a new version
- Removing deprecated features
- Upgrading major dependencies (framework, database)
- Database schema migrations with data transformation
- Sunsetting a service or endpoint

## Steps

### Step 1: Audit Current Usage

**Tool:** `shell`
**Parameters:**

```json
{"command": "grep -r 'old_function_name' --include='*.py' . | grep -v '.venv' | wc -l", "description": "Count usages of deprecated function"}
```

**Also:**

```json
{"command": "cat /var/log/nginx/access.log | grep '/api/v1/old-endpoint' | awk '{print $1}' | sort | uniq -c | sort -rn | head -20", "description": "Find top consumers of deprecated endpoint"}
```

**Validation:** Complete inventory of all callers, users, and dependencies on the deprecated item.

### Step 2: Document the Deprecation

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/deprecations/api-v1-sunset.md",
  "content": "# Deprecation Notice: API v1 Endpoints\n\n## Status\nDeprecated: 2024-01-01\nEnd of Life: 2024-06-30\n\n## Affected Endpoints\n- `GET /api/v1/users` → Use `GET /api/v2/users`\n- `POST /api/v1/orders` → Use `POST /api/v2/orders`\n\n## Migration Guide\n1. Update base URL from `/api/v1/` to `/api/v2/`\n2. `user_id` field renamed to `id` (UUID format)\n3. `created` field renamed to `created_at` (ISO 8601)\n4. Pagination changed from offset/limit to cursor-based\n\n## Breaking Changes\n- Response envelope removed (no more `{\"data\": ...}` wrapper)\n- Error format changed to RFC 7807 Problem Details\n\n## Support\nContact api-migration@example.com for assistance.\n"
}
```

**Validation:** Migration guide includes: timeline, affected items, step-by-step migration, breaking changes, support contact.

### Step 3: Add Deprecation Warnings

**Tool:** `edit_file`
**Parameters:**

```json
{
  "file_path": "/src/api/v1/users.py",
  "old_string": "@router.get('/users')\ndef list_users_v1(...):\n    return user_service.list_users(...)",
  "new_string": "import warnings\nfrom fastapi import Response\n\n@router.get('/users')\ndef list_users_v1(response: Response, ...):\n    warnings.warn(\n        'API v1 is deprecated. Migrate to /api/v2/users by 2024-06-30. '\\
        'See https://docs.example.com/migration',\n        DeprecationWarning,\n        stacklevel=2\n    )\n    response.headers['Deprecation'] = 'true'\n    response.headers['Sunset'] = 'Sat, 30 Jun 2024 00:00:00 GMT'\n    response.headers['Link'] = '</api/v2/users>; rel=\"successor-version\"'\n    return user_service.list_users(...)"
}
```

**Validation:** Deprecation headers returned on every response. Warnings are logged server-side.

### Step 4: Provide Backward Compatibility Layer

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/api/compatibility.py",
  "content": "\"\"\"Backward compatibility adapter for v1 → v2 migration.\"\"\"\n\ndef adapt_v1_response(v2_data):\n    \"\"\"Convert v2 response format to v1 format.\"\"\"\n    if isinstance(v2_data, list):\n        return {'data': [adapt_v1_item(item) for item in v2_data]}\n    return adapt_v1_item(v2_data)\n\ndef adapt_v1_item(item):\n    \"\"\"Convert single v2 item to v1 format.\"\"\"\n    return {\n        'user_id': item.get('id'),\n        'email': item.get('email'),\n        'name': item.get('name'),\n        'created': item.get('created_at'),\n    }\n\ndef adapt_v1_request(v1_data):\n    \"\"\"Convert v1 request format to v2 format.\"\"\"\n    return {\n        'email': v1_data.get('email'),\n        'name': v1_data.get('name'),\n    }\n"
}
```

**Validation:** Compatibility layer converts data correctly. All existing tests still pass.

### Step 5: Monitor Usage During Deprecation Period

**Tool:** `shell`
**Parameters:**

```json
{"command": "python scripts/analyze-deprecated-usage.py --endpoint /api/v1/users --days 7 --output usage-report.json", "description": "Generate usage report for deprecated endpoint"}
```

**Validation:** Report shows: unique callers, request volume, trend (increasing/decreasing).

### Step 6: Remove the Deprecated Code

**Tool:** `shell`
**Parameters:**

```json
{"command": "git rm -r src/api/v1/ && git commit -m 'chore!: remove API v1 endpoints (sunset 2024-06-30)'", "description": "Remove deprecated v1 endpoints"}
```

**Validation:** Removal is done after the announced sunset date. Breaking change is clearly marked with `!` in commit.

### Step 7: Verify Clean Removal

**Tool:** `shell`
**Parameters:**

```json
{"command": "grep -r 'v1' --include='*.py' src/ || echo 'Clean: No v1 references found'", "description": "Verify no deprecated code remains"}
```

**Validation:** No references to deprecated code remain. All tests pass. Documentation updated.

## Examples

### Example 1: API Version Sunset

**Input:** "Deprecate and remove API v1."

**Process:**

1. Audit: 12 integrations using v1, 3 using v2
2. Document: Migration guide with code examples in Python, JS, curl
3. Warnings: Deprecation headers added, email sent to all API consumers
4. Compatibility: Adapter layer for response format conversion
5. Monitor: Weekly usage reports show gradual migration
6. Remove: After 6-month notice period, v1 endpoints removed
7. Verify: All v1 references cleaned up, tests pass

**Output:** Clean API v1 removal with zero unexpected breakage.

### Example 2: Dependency Upgrade (Django 3 → 4)

**Input:** "Upgrade Django from 3.2 to 4.2."

**Process:**

1. Audit: List all deprecated features used in the codebase
2. Document: Django 4 migration checklist
3. Warnings: Run with deprecation warnings enabled, fix each one
4. Compatibility: Use `django-upgrade` tool for automated fixes
5. Monitor: Test suite passes at each step
6. Remove: Update requirements.txt, remove compatibility shims
7. Verify: Full test suite passes, no deprecation warnings

**Output:** Smooth Django upgrade with no runtime issues.

### Example 3: Database Migration with Data Transformation

**Input:** "Migrate from integer IDs to UUIDs for user table."

**Process:**

1. Audit: All tables referencing user.id, all queries using it
2. Document: Migration plan with rollback strategy
3. Warnings: Dual-write period — write to both id and uuid columns
4. Compatibility: Backfill UUIDs, add views that support both
5. Monitor: Verify dual-write consistency with daily checks
6. Remove: After verification period, drop integer id column
7. Verify: All foreign keys updated, no references to old id

**Output:** Zero-downtime migration from integer to UUID primary keys.

## Best Practices

- **Communicate early.** Announce deprecation as soon as the decision is made.
- **Set a deadline.** Give users at least 3-6 months for non-critical deprecations.
- **Provide a migration guide.** Include code examples for common use cases.
- **Use Sunset headers.** HTTP `Sunset` header is the standard way to announce removal.
- **Version your deprecations.** Track what was deprecated when and when it will be removed.
- **Monitor usage.** Know who is still using deprecated features before removal.
- **Offer support.** Provide a migration support channel or office hours.
- **Be empathetic.** Deprecation causes work for your users; make it as easy as possible.
- **Never break unannounced.** Removal should never surprise users.
- **Have a rollback plan.** If removal causes issues, be able to restore quickly.