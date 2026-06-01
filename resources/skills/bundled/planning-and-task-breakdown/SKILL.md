---
name: planning-and-task-breakdown
version: 1.0.0
category: coding
description: Decompose complex goals into actionable, prioritized tasks with clear deliverables and dependencies
author: Construct AI
tools_needed: [write_file, read_file, shell, edit_file]
confidence: 0.95
---

# Planning and Task Breakdown

## Description

Systematically decompose complex projects into small, actionable tasks with clear dependencies, priorities, and acceptance criteria. Creates execution plans that can be tracked and measured.

## When to Use

- Starting a new project or major feature
- Facing an ambiguous or complex requirement
- Need to estimate timelines or allocate resources
- Feeling overwhelmed by the scope of work
- Need to coordinate work across multiple files or modules

## Steps

### Step 1: Understand the Goal

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/path/to/requirements.md"}
```

**Validation:** Can articulate the end goal in one sentence and identify 3+ key constraints.

### Step 2: Identify Major Components

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/plan/components.md",
  "content": "# Components Analysis\n\n## Major Components\n1. Component A - responsibility\n2. Component B - responsibility\n\n## Interactions\n- A depends on B for X\n- B provides Y to C\n"
}
```

**Validation:** All major functional areas are identified with clear responsibilities.

### Step 3: Create Task Breakdown

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/plan/tasks.md",
  "content": "# Task Breakdown\n\n## Task 1: Setup [HIGH]\n- Create project structure\n- Dependencies: None\n- Acceptance: Directory exists, tests run\n\n## Task 2: Core Logic [HIGH]\n- Implement main algorithm\n- Dependencies: Task 1\n- Acceptance: Unit tests pass\n"
}
```

**Validation:** Every task has: unique ID, priority, description, dependencies, acceptance criteria, estimated effort.

### Step 4: Establish Dependencies

**Tool:** `shell`
**Parameters:**

```json
{"command": "python scripts/generate-dependency-graph.py --tasks docs/plan/tasks.md --output docs/plan/dependency-graph.png", "description": "Generate task dependency graph"}
```

**Validation:** Dependency graph shows no circular dependencies. Critical path is identified.

### Step 5: Prioritize and Sequence

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/plan/execution-order.md",
  "content": "# Execution Order\n\n## Phase 1: Foundation (Day 1-2)\n1. Task 1 - Setup\n2. Task 2 - Core interfaces\n\n## Phase 2: Implementation (Day 3-5)\n3. Task 3 - Main logic\n4. Task 4 - Error handling\n"
}
```

**Validation:** Tasks are ordered by dependency and priority. Parallelizable tasks are grouped.

### Step 6: Create Tracking Document

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/docs/plan/progress.md",
  "content": "# Progress Tracker\n\n| Task | Status | Started | Completed | Notes |\n|------|--------|---------|-----------|-------|\n| Task 1 | TODO | - | - | - |\n| Task 2 | TODO | - | - | - |\n"
}
```

**Validation:** All tasks from the breakdown appear in the tracker. Status values are standardized (TODO/IN_PROGRESS/DONE/BLOCKED).

### Step 7: Validate Plan Completeness

**Tool:** `shell`
**Parameters:**

```json
{"command": "python scripts/validate-plan.py --tasks docs/plan/tasks.md --criteria docs/requirements.md", "description": "Validate plan covers all requirements"}
```

**Validation:** Every requirement has at least one task addressing it. No orphan tasks without requirements.

## Examples

### Example 1: Building a REST API

**Input:** "Build a REST API for a task management system."

**Process:**

1. Goal: CRUD API for tasks with authentication
2. Components: Models, Controllers, Auth, Database, Tests
3. Tasks: 15 tasks across 5 components with dependencies
4. Dependencies: Models → Controllers → Auth → Integration Tests
5. Execution: Phase 1 (models), Phase 2 (controllers), Phase 3 (auth + tests)

**Output:** A complete execution plan with 15 prioritized tasks across 3 phases.

### Example 2: Refactoring a Monolith

**Input:** "Extract the payment service from our monolith."

**Process:**

1. Goal: Independent payment service with same functionality
2. Components: Database schema, API endpoints, business logic, integrations
3. Tasks: 20 tasks including data migration, API compatibility layer, testing
4. Dependencies: Schema → Service → Migration → Cutover
5. Execution: Weekly milestones with rollback plan at each stage

**Output:** A safe migration plan with rollback points and verification at each stage.

### Example 3: Adding a Feature to Existing Code

**Input:** "Add real-time notifications to the chat app."

**Process:**

1. Goal: WebSocket-based notifications for messages
2. Components: WebSocket server, event emitter, client handler, fallback
3. Tasks: 8 tasks with clear dependencies
4. Dependencies: Server → Events → Client → Fallback (polling)
5. Execution: Server first, then client, then integration

**Output:** An 8-task plan with WebSocket and polling fallback strategies.

## Best Practices

- **SMART tasks.** Every task should be Specific, Measurable, Achievable, Relevant, Time-bound.
- **Vertical slices.** Prefer end-to-end features over horizontal layers for faster value delivery.
- **Dependency-first.** Complete foundational tasks before dependent tasks.
- **Buffer for unknowns.** Add 20-30% buffer for tasks with high uncertainty.
- **Daily updates.** Update the progress tracker at the end of each work session.
- **Re-plan freely.** When reality diverges from the plan, update the plan rather than blindly following it.
- **Limit WIP.** Have at most 2-3 tasks in progress simultaneously to maintain focus.