---
name: api-and-interface-design
version: 1.0.0
category: coding
description: Design RESTful and GraphQL APIs with OpenAPI specifications and clear contracts
author: Construct AI
tools_needed: [write_file, read_file, shell]
confidence: 0.95
---

# API and Interface Design

## Description

Design robust, versioned APIs with clear contracts, consistent patterns, and comprehensive documentation. Covers RESTful conventions, GraphQL schemas, OpenAPI specifications, authentication, rate limiting, and error handling.

## When to Use

- Designing a new API or microservice
- Versioning an existing API
- Creating internal service interfaces
- Building webhooks or integrations
- Documenting API contracts for team coordination

## Steps

### Step 1: Define Resource Model

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/api/resource-model.md",
  "content": "# Resource Model\n\n## User Resource\n| Field | Type | Required | ReadOnly |\n|-------|------|----------|----------|\n| id | UUID | Yes | Yes |\n| email | string | Yes | No |\n| name | string | Yes | No |\n| role | enum | Yes | No |\n| created_at | ISO8601 | Yes | Yes |\n\n## Relationships\n- User has many Orders\n- User belongs to an Organization\n"
}
```

**Validation:** Resource model covers all entities, their fields, and relationships.

### Step 2: Design Endpoint Structure

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/api/endpoints.md",
  "content": "# API Endpoints\n\n## Users\n| Method | Path | Description | Auth |\n|--------|------|-------------|------|\n| GET | /api/v1/users | List users | Bearer |\n| GET | /api/v1/users/{id} | Get user | Bearer |\n| POST | /api/v1/users | Create user | Bearer + Admin |\n| PUT | /api/v1/users/{id} | Update user | Bearer + Owner |\n| DELETE | /api/v1/users/{id} | Delete user | Bearer + Admin |\n\n## Query Parameters (List)\n- `page`: int (default: 1)\n- `per_page`: int (default: 20, max: 100)\n- `sort`: string (e.g., 'created_at,-name')\n- `filter[field]`: string\n"
}
```

**Validation:** Endpoints follow REST conventions. All CRUD operations covered. Pagination, sorting, filtering specified.

### Step 3: Write OpenAPI Specification

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/api/openapi.yaml",
  "content": "openapi: 3.0.3\ninfo:\n  title: User API\n  version: 1.0.0\npaths:\n  /api/v1/users:\n    get:\n      summary: List users\n      parameters:\n        - name: page\n          in: query\n          schema: { type: integer, default: 1 }\n        - name: per_page\n          in: query\n          schema: { type: integer, default: 20 }\n      responses:\n        '200':\n          description: Paginated list of users\n          content:\n            application/json:\n              schema:\n                type: object\n                properties:\n                  data: { type: array, items: { $ref: '#/components/schemas/User' } }\n                  meta: { $ref: '#/components/schemas/PaginationMeta' }\n    post:\n      summary: Create user\n      requestBody:\n        required: true\n        content:\n          application/json:\n            schema: { $ref: '#/components/schemas/UserInput' }\n      responses:\n        '201': { description: User created }\n        '422': { description: Validation error }\ncomponents:\n  schemas:\n    User:\n      type: object\n      properties:\n        id: { type: string, format: uuid }\n        email: { type: string, format: email }\n        name: { type: string }\n"
}
```

**Validation:** OpenAPI spec is valid (use swagger-cli validate). All endpoints documented.

### Step 4: Define Error Response Format

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/api/errors.md",
  "content": "# Error Response Format\n\nAll errors follow RFC 7807 (Problem Details):\n\n```json\n{\n  \"type\": \"https://api.example.com/errors/validation-failed\",\n  \"title\": \"Validation Failed\",\n  \"status\": 422,\n  \"detail\": \"The request body contains invalid data.\",\n  \"errors\": [\n    {\n      \"field\": \"email\",\n      \"message\": \"Must be a valid email address\"\n    }\n  ]\n}\n```\n\n## Standard Error Codes\n| Status | Code | Usage |\n|--------|------|-------|\n| 400 | bad_request | Malformed request |\n| 401 | unauthorized | Missing/invalid auth |\n| 403 | forbidden | Insufficient permissions |\n| 404 | not_found | Resource doesn't exist |\n| 409 | conflict | Resource conflict |\n| 422 | validation_failed | Invalid input data |\n| 429 | rate_limited | Too many requests |\n| 500 | internal_error | Server error |\n"
}
```

**Validation:** Error format is consistent across all endpoints. Status codes follow HTTP semantics.

### Step 5: Implement Endpoint

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/api/users.py",
  "content": "from fastapi import APIRouter, Depends, HTTPException, Query\nfrom sqlalchemy.orm import Session\nfrom src.schemas.user import UserCreate, UserResponse, UserList\nfrom src.services.user_service import UserService\nfrom src.dependencies import get_db, get_current_user\n\nrouter = APIRouter(prefix='/api/v1/users', tags=['users'])\n\n@router.get('/', response_model=UserList)\nasync def list_users(\n    page: int = Query(1, ge=1),\n    per_page: int = Query(20, ge=1, le=100),\n    sort: str = Query('created_at'),\n    db: Session = Depends(get_db),\n    current_user = Depends(get_current_user)\n):\n    \"\"\"List users with pagination and sorting.\"\"\"\n    service = UserService(db)\n    return service.list_users(page=page, per_page=per_page, sort=sort)\n\n@router.post('/', response_model=UserResponse, status_code=201)\nasync def create_user(\n    data: UserCreate,\n    db: Session = Depends(get_db),\n    current_user = Depends(require_admin)\n):\n    \"\"\"Create a new user. Requires admin role.\"\"\"\n    service = UserService(db)\n    try:\n        return service.create_user(data)\n    except EmailExistsError:\n        raise HTTPException(status_code=409, detail='Email already exists')\n"
}
```

**Validation:** Endpoint matches OpenAPI spec. Request/response models are validated. Auth is enforced.

### Step 6: Generate Client SDK

**Tool:** `shell`
**Parameters:**

```json
{"command": "openapi-generator-cli generate -i docs/api/openapi.yaml -g python -o clients/python/", "description": "Generate Python client from OpenAPI spec"}
```

**Validation:** Generated client compiles and can call the API successfully.

### Step 7: Verify with Contract Tests

**Tool:** `shell`
**Parameters:**

```json
{"command": "pytest tests/api/ -v --contract-test --openapi-spec=docs/api/openapi.yaml", "description": "Run contract tests against OpenAPI spec"}
```

**Validation:** All responses match the OpenAPI schema. No undocumented fields or status codes.

## Examples

### Example 1: RESTful CRUD API

**Input:** "Design a task management API."

**Process:**

1. Resource model: Task, Project, User entities with relationships
2. Endpoints: Full CRUD for tasks with filtering by status, priority
3. OpenAPI spec: Complete spec with schemas for all requests/responses
4. Errors: Consistent error format with validation details
5. Implementation: FastAPI with SQLAlchemy, pagination, sorting
6. Client SDK: Auto-generated Python client
7. Contract tests: Verify all responses match spec

**Output:** Fully documented, tested REST API with auto-generated client.

### Example 2: GraphQL Schema Design

**Input:** "Design a GraphQL API for an e-commerce platform."

**Process:**

1. Resource model: Product, Order, Customer, Cart types
2. Schema: Queries (products, orders), Mutations (addToCart, checkout)
3. Resolvers: DataLoader for N+1 prevention
4. Auth: Directive-based @auth on sensitive fields
5. Implementation: Apollo Server with type generation
6. Client: React hooks with generated types

**Output:** Type-safe GraphQL API with efficient data loading.

### Example 3: Webhook Design

**Input:** "Design webhooks for order status updates."

**Process:**

1. Resource model: Webhook subscription, event types, delivery attempts
2. Contract: Event payload schema, signature verification (HMAC)
3. Delivery: At-least-once delivery with exponential backoff
4. Retry: Max 5 attempts, dead letter queue after
5. Security: HMAC-SHA256 signature in header
6. Documentation: Complete webhook guide with examples

**Output:** Reliable webhook system with signed payloads and retry logic.

## Best Practices

- **Version in URL.** Use `/api/v1/` for versioning; never break existing clients.
- **Use nouns, not verbs.** `/users` not `/getUsers`. HTTP methods define the action.
- **Plural resources.** Use `/users` not `/user` for collections.
- **Consistent pagination.** Always paginate list endpoints with page/per_page or cursor.
- **Filter with query params.** Use `?status=active&role=admin` for filtering.
- **HATEOAS optional.** Include `_links` when client discovery is needed.
- **Idempotency keys.** Require `Idempotency-Key` header for POST/PUT to prevent duplicates.
- **Rate limit headers.** Return `X-RateLimit-*` headers on all responses.
- **Never expose internals.** Error messages should not reveal stack traces or DB details.
- **Content negotiation.** Support `Accept` header for response format selection.