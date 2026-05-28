# API Reference

> **Version:** 0.1.0  
> **Last Updated:** 2026-05-28

---

## Table of Contents

- [Tauri Commands](#tauri-commands)
  - [Core Commands](#core-commands)
  - [Memory Commands](#memory-commands)
  - [Agent Commands](#agent-commands)
  - [Autonomous Commands](#autonomous-commands)
- [Tauri Events](#tauri-events)
- [FastAPI Endpoints](#fastapi-endpoints)
  - [Health Check](#health-check)
  - [Memory Endpoints](#memory-endpoints)
  - [Agent Endpoints](#agent-endpoints)
  - [Tool Endpoints](#tool-endpoints)
  - [LLM Endpoints](#llm-endpoints)
  - [Autonomous Endpoints](#autonomous-endpoints)
  - [Notification Endpoints](#notification-endpoints)
- [Data Types](#data-types)

---

## Tauri Commands

All Tauri commands are invoked from the frontend using:

```typescript
import { invoke } from '@tauri-apps/api/core';

const result = await invoke('command_name', { arg1: 'value', arg2: 123 });
```

---

### Core Commands

#### `greet`

**Signature:** `greet(name: &str) -> String`

**Description:** Simple greeting command for frontend-Rust communication testing.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | `string` | Yes | Name to greet |

**Returns:** `string` — Greeting message

**Example:**
```typescript
const message = await invoke('greet', { name: 'World' });
// Returns: "Hello, World! Welcome to Construct."
```

---

#### `get_app_version`

**Signature:** `get_app_version() -> String`

**Description:** Returns the current application version from `Cargo.toml`.

**Parameters:** None

**Returns:** `string` — App version (e.g., `"0.1.0"`)

**Example:**
```typescript
const version = await invoke('get_app_version');
// Returns: "0.1.0"
```

---

### Memory Commands

#### `record_conversation`

**Signature:** `record_conversation(message: ConversationMessage) -> Result<(), String>`

**Description:** Stores a conversation message in the SQLite database.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `message.id` | `string` | Yes | Unique message ID (UUID) |
| `message.timestamp` | `number` | Yes | Unix timestamp (seconds) |
| `message.role` | `string` | Yes | `"user"` or `"assistant"` |
| `message.content` | `string` | Yes | Message content |

**Returns:** `void` on success, error string on failure

**Example:**
```typescript
await invoke('record_conversation', {
  message: {
    id: 'msg-001',
    timestamp: 1716912000,
    role: 'user',
    content: 'Create a React component'
  }
});
```

---

#### `get_recent_conversations`

**Signature:** `get_recent_conversations(limit: Option<usize>) -> Result<Vec<ConversationMessage>, String>`

**Description:** Retrieves recent conversation messages, oldest first.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `limit` | `number` | No | Maximum messages to return (default: 50) |

**Returns:** `ConversationMessage[]` — Array of messages

**Example:**
```typescript
const messages = await invoke('get_recent_conversations', { limit: 20 });
// Returns: [{ id, timestamp, role, content }, ...]
```

---

#### `record_code_event`

**Signature:** `record_code_event(event: CodeEvent) -> Result<(), String>`

**Description:** Records a code change event (create, modify, delete, refactor).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `event.id` | `string` | Yes | Unique event ID (UUID) |
| `event.timestamp` | `number` | Yes | Unix timestamp |
| `event.file_path` | `string` | Yes | Path of the affected file |
| `event.change_type` | `string` | Yes | One of: `create`, `modify`, `delete`, `rename` |
| `event.diff` | `string` | No | Diff/patch text |
| `event.summary` | `string` | Yes | Human-readable change description |

**Returns:** `void` on success, error string on failure

**Example:**
```typescript
await invoke('record_code_event', {
  event: {
    id: 'evt-001',
    timestamp: 1716912000,
    file_path: 'src/components/Counter.tsx',
    change_type: 'create',
    diff: '+ export function Counter() { ... }',
    summary: 'Created Counter component'
  }
});
```

---

#### `get_recent_code_events`

**Signature:** `get_recent_code_events(limit: Option<usize>) -> Result<Vec<CodeEvent>, String>`

**Description:** Retrieves recent code events, oldest first.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `limit` | `number` | No | Maximum events to return (default: 20) |

**Returns:** `CodeEvent[]` — Array of code events

**Example:**
```typescript
const events = await invoke('get_recent_code_events', { limit: 10 });
// Returns: [{ id, timestamp, file_path, change_type, diff, summary }, ...]
```

---

#### `store_preference`

**Signature:** `store_preference(key: String, value: String) -> Result<(), String>`

**Description:** Stores or updates a user preference with default confidence (0.8).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `key` | `string` | Yes | Preference key (e.g., `theme`, `language`) |
| `value` | `string` | Yes | Preference value |

**Returns:** `void` on success, error string on failure

**Example:**
```typescript
await invoke('store_preference', { key: 'theme', value: 'dark' });
```

---

#### `get_preferences`

**Signature:** `get_preferences() -> Result<Vec<Preference>, String>`

**Description:** Retrieves all stored preferences ordered by confidence (highest first).

**Parameters:** None

**Returns:** `Preference[]` — Array of preferences

```typescript
interface Preference {
  key: string;
  value: string;
  confidence: number;   // 0.0 - 1.0
  last_updated: number; // Unix timestamp
}
```

**Example:**
```typescript
const prefs = await invoke('get_preferences');
// Returns: [{ key: 'theme', value: 'dark', confidence: 0.8, last_updated: 1716912000 }, ...]
```

---

#### `get_project_state`

**Signature:** `get_project_state(path: Option<String>) -> Result<ProjectState, String>`

**Description:** Fetches the stored project state for a given path. Returns a default state if none has been saved yet. Defaults to the current working directory.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | No | Project directory path |

**Returns:** `ProjectState`

```typescript
interface ProjectState {
  project_path: string;
  current_branch: string;
  last_commit: string;
  agent_context_json: string; // JSON string of agent context
}
```

**Example:**
```typescript
const state = await invoke('get_project_state', {
  path: '/home/user/my-project'
});
// Returns: { project_path, current_branch, last_commit, agent_context_json }
```

---

#### `update_project_state`

**Signature:** `update_project_state(state_data: ProjectState) -> Result<(), String>`

**Description:** Upserts (inserts or updates) the project state snapshot.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `state_data.project_path` | `string` | Yes | Project directory path |
| `state_data.current_branch` | `string` | Yes | Current git branch |
| `state_data.last_commit` | `string` | Yes | Last commit hash |
| `state_data.agent_context_json` | `string` | Yes | Agent context as JSON string |

**Returns:** `void` on success, error string on failure

**Example:**
```typescript
await invoke('update_project_state', {
  stateData: {
    project_path: '/home/user/proj',
    current_branch: 'main',
    last_commit: 'abc123def',
    agent_context_json: '{"current_task": "refactoring"}'
  }
});
```

---

#### `recall_context`

**Signature:** `recall_context(query: String, limit: Option<usize>) -> Result<Vec<ContextItem>, String>`

**Description:** Searches across conversations and code events for context relevant to the query. Uses SQLite `LIKE` matching; vector similarity scores are a placeholder for future integration.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | `string` | Yes | Search query text |
| `limit` | `number` | No | Maximum results (default: 10) |

**Returns:** `ContextItem[]` — Combined results from conversations and code events

```typescript
interface ContextItem {
  id: string;
  source: 'conversation' | 'code_event';
  content: string;
  relevance: number;  // Placeholder (0.0)
  timestamp: number;
}
```

**Example:**
```typescript
const ctx = await invoke('recall_context', {
  query: 'authentication',
  limit: 10
});
// Returns: [{ id, source, content, relevance, timestamp }, ...]
```

---

### Agent Commands

#### `start_agent`

**Signature:** `start_agent(goal: String, project_path: Option<String>) -> Result<String, String>`

**Description:** Starts a new agent session with the given goal. Returns the session ID immediately. The agent runs in the background and streams output via Tauri events on the channel `agent:{session_id}`.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `goal` | `string` | Yes | The agent's goal or task description |
| `project_path` | `string` | No | Path to the project directory (default: `"."`) |

**Returns:** `string` — Session ID (8-character hex string)

**Example:**
```typescript
const sessionId = await invoke('start_agent', {
  goal: 'Create a Counter component with React hooks',
  projectPath: '/home/user/my-project'
});
// Returns: "a1b2c3d4"

// Listen for output
import { listen } from '@tauri-apps/api/event';
listen(`agent:${sessionId}`, (event) => {
  const output = event.payload as AgentOutputEvent;
  console.log(output.event_type, output.content);
});
```

---

#### `get_agent_status`

**Signature:** `get_agent_status(session_id: String) -> Result<AgentSession, String>`

**Description:** Gets the current status and full details of an agent session.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `sessionId` | `string` | Yes | Session ID returned by `start_agent` |

**Returns:** `AgentSession` — Full session details

```typescript
interface AgentSession {
  id: string;
  goal: string;
  status: 'Idle' | 'Running' | 'Paused' | 'Completed' | 'Failed' | 'Waiting';
  tasks: AgentTask[];
  current_task_index: number;
  output_log: AgentOutputEvent[];
  created_at: number;
  updated_at: number;
  project_path: string;
}

interface AgentTask {
  id: string;
  description: string;
  status: 'Pending' | 'InProgress' | 'Completed' | 'Failed' | 'Blocked';
  result: string | null;
  error: string | null;
}
```

**Example:**
```typescript
const session = await invoke('get_agent_status', { sessionId: 'a1b2c3d4' });
console.log(session.status);   // "Running"
console.log(session.tasks);    // [{ id, description, status, ... }, ...]
```

---

#### `pause_agent`

**Signature:** `pause_agent(session_id: String) -> Result<(), String>`

**Description:** Pauses a running agent session. The background task will spin-wait until `resume_agent` is called.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `sessionId` | `string` | Yes | Session ID |

**Returns:** `void` on success, error string on failure

**Example:**
```typescript
await invoke('pause_agent', { sessionId: 'a1b2c3d4' });
```

---

#### `resume_agent`

**Signature:** `resume_agent(session_id: String) -> Result<(), String>`

**Description:** Resumes a paused agent session. The background task will break out of its spin-wait and continue emitting events.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `sessionId` | `string` | Yes | Session ID |

**Returns:** `void` on success, error string on failure

**Example:**
```typescript
await invoke('resume_agent', { sessionId: 'a1b2c3d4' });
```

---

#### `stop_agent`

**Signature:** `stop_agent(session_id: String) -> Result<(), String>`

**Description:** Stops (terminates) an agent session. Sets the session status to `Failed`; the background task detects this and exits cleanly after emitting an abort event.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `sessionId` | `string` | Yes | Session ID |

**Returns:** `void` on success, error string on failure

**Example:**
```typescript
await invoke('stop_agent', { sessionId: 'a1b2c3d4' });
```

---

#### `get_agent_output`

**Signature:** `get_agent_output(session_id: String, since_index: Option<usize>) -> Result<Vec<AgentOutputEvent>, String>`

**Description:** Gets output events for a session since a given index. Useful for polling or fetching historical output after a page reload.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `sessionId` | `string` | Yes | Session ID |
| `sinceIndex` | `number` | No | Start index for pagination (default: 0) |

**Returns:** `AgentOutputEvent[]` — Output events

```typescript
interface AgentOutputEvent {
  session_id: string;
  event_type: string;  // See event types below
  content: string;
  timestamp: number;
}
```

**Event types:**

| Event Type | Description |
|------------|-------------|
| `thought` | Agent's internal reasoning |
| `tool_call` | A tool is being invoked |
| `tool_result` | Result from a tool invocation |
| `code` | Generated code snippet |
| `error` | An error occurred |
| `complete` | Session finished successfully |
| `task_start` | A new task has started |
| `task_complete` | A task finished successfully |
| `task_failed` | A task failed |
| `waiting` | Agent is waiting for user input |

**Example:**
```typescript
const events = await invoke('get_agent_output', {
  sessionId: 'a1b2c3d4',
  sinceIndex: 10
});
// Returns: [{ session_id, event_type, content, timestamp }, ...]
```

---

### Autonomous Commands

#### `enable_autonomous_mode`

**Signature:** `enable_autonomous_mode() -> Result<(), String>`

**Description:** Enables autonomous mode. Transitions the worker from `Disabled` to `Idle` and emits the `autonomous:started` event.

**Parameters:** None

**Returns:** `void` on success, error string on failure

**Example:**
```typescript
await invoke('enable_autonomous_mode');
```

---

#### `disable_autonomous_mode`

**Signature:** `disable_autonomous_mode() -> Result<(), String>`

**Description:** Disables autonomous mode. Transitions the worker to `Disabled` and emits the `autonomous:paused` event with reason `"disabled_by_user"`.

**Parameters:** None

**Returns:** `void` on success, error string on failure

**Example:**
```typescript
await invoke('disable_autonomous_mode');
```

---

#### `get_autonomous_status`

**Signature:** `get_autonomous_status() -> Result<AutonomousState, String>`

**Description:** Gets current autonomous status including progress, resource usage, and queue size.

**Parameters:** None

**Returns:** `AutonomousState`

```typescript
interface AutonomousState {
  status: 'Disabled' | 'Idle' | 'Running' | 'Paused' | 'Throttled' | 'Error';
  enabled: boolean;
  current_goal: string | null;
  progress_percent: number;       // 0.0 - 100.0
  queue_size: number;
  checkpoints_saved: number;
  tasks_completed: number;
  started_at: number | null;      // Unix timestamp
  last_checkpoint_at: number | null;
  resource_cpu: number;           // CPU %
  resource_memory: number;        // Memory MB
}
```

**Example:**
```typescript
const status = await invoke('get_autonomous_status');
console.log(status.status);            // "Running"
console.log(status.progress_percent);  // 42.5
console.log(status.queue_size);        // 3
```

---

#### `set_goal_deadline`

**Signature:** `set_goal_deadline(goal_id: String, deadline: i64) -> Result<(), String>`

**Description:** Sets a deadline for a goal. Stores the deadline (Unix timestamp) associated with a goal ID.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `goalId` | `string` | Yes | Goal identifier |
| `deadline` | `number` | Yes | Unix timestamp deadline |

**Returns:** `void` on success, error string on failure

**Example:**
```typescript
await invoke('set_goal_deadline', {
  goalId: 'goal-001',
  deadline: 1719504000  // 2024-06-28 00:00:00 UTC
});
```

---

#### `get_agent_log`

**Signature:** `get_agent_log(lines: Option<usize>) -> Result<Vec<LogEntry>, String>`

**Description:** Gets recent agent log entries. Returns the most recent lines (oldest first) up to the requested limit. Defaults to 100 lines. Keeps a rolling buffer of the last 1000 entries.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `lines` | `number` | No | Number of log lines to return (default: 100) |

**Returns:** `LogEntry[]`

```typescript
interface LogEntry {
  timestamp: number;  // Unix timestamp
  level: 'info' | 'warn' | 'error';
  message: string;
  source: 'worker' | 'safety' | 'checkpoint' | 'resource';
}
```

**Example:**
```typescript
const logs = await invoke('get_agent_log', { lines: 50 });
// Returns: [{ timestamp, level, message, source }, ...]
```

---

## Tauri Events

The Rust backend emits events that the frontend listens to:

### Agent Events

| Event Channel | Payload Type | Description |
|---------------|--------------|-------------|
| `agent:{sessionId}` | `AgentOutputEvent` | Real-time agent output |

### Autonomous Events

| Event Channel | Payload | Description |
|---------------|---------|-------------|
| `autonomous:started` | `null` | Worker started |
| `autonomous:paused` | `string` (reason) | Worker paused |
| `autonomous:resumed` | `null` | Worker resumed |
| `autonomous:checkpoint` | `{ progress: number }` | Checkpoint saved |
| `autonomous:completed` | `null` | All goals completed |
| `autonomous:error` | `{ error: string }` | Error occurred |

### Listening to Events

```typescript
import { listen } from '@tauri-apps/api/event';

// Listen for agent output
const unlisten = await listen('agent:a1b2c3d4', (event) => {
  const output = event.payload as AgentOutputEvent;
  // Handle output
});

// Stop listening
unlisten();
```

---

## FastAPI Endpoints

Base URL: `http://127.0.0.1:8000`

Interactive docs: `http://127.0.0.1:8000/docs`

All endpoints return JSON responses. Error responses follow this format:

```json
{
  "detail": "Error message string"
}
```

---

### Health Check

#### `GET /health`

Returns service health status, configured LLM providers, and autonomous mode availability.

**Response:**
```json
{
  "status": "ok",
  "service": "construct-agent-api",
  "version": "0.3.0",
  "llm_providers": ["openai", "anthropic", "ollama"],
  "autonomous": {
    "available": true,
    "worker_status": { ... }
  }
}
```

---

### Memory Endpoints

#### `POST /memory/message`

Store a conversation message with embedding.

**Request Body:**
```json
{
  "role": "user",
  "content": "Create a React component",
  "conversation_id": "conv-123"
}
```

**Response:**
```json
{
  "memory_id": "uuid-string",
  "status": "stored"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `role` | `string` | Yes | `"user"` or `"assistant"` |
| `content` | `string` | Yes | Message content |
| `conversation_id` | `string` | No | Optional conversation thread UUID |

**Errors:** `500` — Storage failure

---

#### `POST /memory/code`

Store a code event with embedding.

**Request Body:**
```json
{
  "file_path": "src/components/Counter.tsx",
  "change_type": "create",
  "summary": "Created Counter component",
  "diff": "+ export function Counter() { ... }"
}
```

**Response:**
```json
{
  "memory_id": "uuid-string",
  "status": "stored"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_path` | `string` | Yes | Path of the affected file |
| `change_type` | `string` | Yes | `create`, `modify`, `delete`, or `rename` |
| `summary` | `string` | Yes | Human-readable description |
| `diff` | `string` | No | Optional diff/patch text |

**Errors:** `500` — Storage failure

---

#### `POST /memory/query`

Semantic search across all collections.

**Request Body:**
```json
{
  "query": "authentication logic",
  "source": null,
  "n_results": 5
}
```

**Response:**
```json
[
  {
    "id": "uuid",
    "text": "...",
    "source": "conversation",
    "distance": 0.23,
    "metadata": {},
    "relevance_score": 0.85
  }
]
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | `string` | Yes | Search query text |
| `source` | `string` | No | Filter by source (`conversation` or `code`) |
| `n_results` | `integer` | No | Number of results (default: 5, max: 50) |

---

#### `POST /memory/query/conversations`

Semantic search restricted to the conversation collection.

**Request Body:** Same as `/memory/query`

**Response:** Same as `/memory/query`

---

#### `POST /memory/query/code`

Semantic search restricted to the code-events collection.

**Request Body:** Same as `/memory/query`

**Response:** Same as `/memory/query`

---

#### `POST /memory/hybrid`

Hybrid search: fuses SQLite full-text results with vector similarity.

**Request Body:**
```json
{
  "query": "authentication",
  "sqlite_results": [
    { "id": "msg-1", "text": "Login form validation" },
    { "id": "msg-2", "text": "JWT token handling" }
  ],
  "n_results": 5
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | `string` | Yes | Search query text |
| `sqlite_results` | `array` | No | SQLite FTS results for fusion |
| `n_results` | `integer` | No | Number of results (default: 5, max: 50) |

**Response:** Same as `/memory/query`

---

#### `GET /memory/stats`

Return collection statistics.

**Response:**
```json
{
  "total_memories": 1523,
  "collections": {
    "conversations": 890,
    "code_events": 633
  },
  "chroma_path": "/path/to/chroma",
  "embedding_model": "all-MiniLM-L6-v2",
  "version": "0.3.0"
}
```

---

#### `DELETE /memory/{memory_id}`

Delete a memory entry by ID.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `memory_id` | `string` | The UUID of the memory to delete |

**Query Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `source` | `string` | No | Source collection (default: `conversation`) |

**Response:**
```json
{
  "memory_id": "uuid-string",
  "deleted": true
}
```

**Errors:** `404` — Memory not found, `500` — Deletion failure

---

### Agent Endpoints

#### `POST /agent/start`

Start a new agent session with the given goal.

**Request Body:**
```json
{
  "goal": "Refactor the authentication module to use JWT tokens",
  "project_path": "/home/user/my-project"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `goal` | `string` | Yes | The agent's goal or task description |
| `project_path` | `string` | No | Path to the project directory (default: `"."`) |

**Response:**
```json
{
  "session_id": "sess-uuid",
  "goal": "Refactor the authentication module to use JWT tokens",
  "status": "running",
  "message": "Agent session started with 5 planned tasks"
}
```

**Errors:** `503` — Agent services not initialized, `500` — Start failure

---

#### `GET /agent/{session_id}/status`

Get the current status of an agent session including all tasks.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `session_id` | `string` | The session ID |

**Response:**
```json
{
  "session_id": "sess-uuid",
  "goal": "Refactor auth module",
  "status": "running",
  "tasks": [
    { "id": "task-1", "description": "Analyze current auth code", "status": "completed", ... }
  ],
  "task_summary": {
    "total": 5,
    "pending": 2,
    "in_progress": 1,
    "completed": 2,
    "failed": 0
  },
  "current_task_index": 2,
  "project_path": "/home/user/my-project",
  "updated_at": 1716912000.0
}
```

**Errors:** `404` — Session not found

---

#### `POST /agent/{session_id}/pause`

Pause a running agent session.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `session_id` | `string` | The session ID |

**Response:**
```json
{
  "session_id": "sess-uuid",
  "action": "pause",
  "status": "paused",
  "message": "Session paused"
}
```

**Errors:** `400` — Session not found or not running

---

#### `POST /agent/{session_id}/resume`

Resume a paused agent session.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `session_id` | `string` | The session ID |

**Response:**
```json
{
  "session_id": "sess-uuid",
  "action": "resume",
  "status": "running",
  "message": "Session resumed"
}
```

**Errors:** `400` — Session not found or not paused

---

#### `POST /agent/{session_id}/stop`

Stop (fail) an agent session.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `session_id` | `string` | The session ID |

**Response:**
```json
{
  "session_id": "sess-uuid",
  "action": "stop",
  "status": "stopped",
  "message": "Session stopped"
}
```

**Errors:** `404` — Session not found

---

#### `GET /agent/{session_id}/output`

Get new output events for a session (since-last-check semantics). Each call returns only events that have not been returned before.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `session_id` | `string` | The session ID |

**Response:**
```json
{
  "session_id": "sess-uuid",
  "events": [
    { "event_type": "thought", "content": "Analyzing...", "timestamp": 1716912000 }
  ],
  "has_more": true
}
```

**Errors:** `404` — Session not found

---

#### `GET /agent/sessions`

List all agent sessions, most recently updated first.

**Response:**
```json
{
  "sessions": [
    { "id": "sess-1", "goal": "...", "status": "completed", ... }
  ],
  "total": 5
}
```

---

### Tool Endpoints

#### `GET /tools`

List all available tools with their schemas.

**Response:**
```json
{
  "tools": [
    {
      "name": "read_file",
      "description": "Read the contents of a file",
      "parameters": { ... }
    }
  ],
  "count": 21
}
```

---

#### `POST /tools/execute`

Execute a tool directly by name with JSON arguments. Useful for ad-hoc tool use without starting a full agent session.

**Request Body:**
```json
{
  "tool_name": "read_file",
  "arguments": {
    "file_path": "src/App.tsx"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tool_name` | `string` | Yes | Name of the tool to execute |
| `arguments` | `object` | No | Tool arguments as a JSON object |

**Response:**
```json
{
  "tool_name": "read_file",
  "result": {
    "content": "...",
    "size": 1234
  }
}
```

**Errors:** `503` — Tool registry not initialized, `400` — Unknown tool, `500` — Execution failure

---

### LLM Endpoints

#### `POST /llm/complete`

Send a prompt directly to the LLM and get a response. Uses smart routing when `model="auto"`.

**Request Body:**
```json
{
  "prompt": "Explain React hooks in 3 sentences",
  "model": "auto",
  "system_prompt": null,
  "stream": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | `string` | Yes | The prompt to send |
| `model` | `string` | No | Model identifier or `"auto"` (default: `"auto"`) |
| `system_prompt` | `string` | No | Override the default system prompt |
| `stream` | `boolean` | No | Stream the response (default: `false`) |

**Response:**
```json
{
  "response": "React hooks are functions that let you use state...",
  "model_used": "claude-sonnet-4-20250514",
  "provider": "anthropic"
}
```

**Errors:** `503` — LLM service not initialized, `500` — Completion failure

---

#### `GET /llm/stats`

Return LLM usage statistics.

**Response:**
```json
{
  "total_calls": 152,
  "calls_by_provider": {
    "openai": 45,
    "anthropic": 78,
    "ollama": 29
  },
  "total_tokens": 125000,
  "average_latency_ms": 2340
}
```

---

### Autonomous Endpoints

#### `POST /autonomous/start`

Start the background worker. Optionally queues an immediate goal.

**Request Body:**
```json
{
  "immediate_goal": "Refactor all class components to functional components",
  "project_path": "/home/user/my-project"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `immediate_goal` | `string` | No | Optional goal to start immediately |
| `project_path` | `string` | No | Project path for immediate goal |

**Response:**
```json
{
  "action": "start",
  "status": "started",
  "message": "Background worker started with goal 'Refactor all...'",
  "worker_status": { ... }
}
```

**Errors:** `500` — Start failure

---

#### `POST /autonomous/stop`

Stop the background worker gracefully.

**Response:**
```json
{
  "action": "stop",
  "status": "stopped",
  "message": "Background worker stopped"
}
```

---

#### `GET /autonomous/status`

Get the current worker status, including the active goal and queue size.

**Response:**
```json
{
  "status": "running",
  "current_goal": {
    "id": "goal-1",
    "description": "Refactor auth module",
    "priority": "high"
  },
  "queue_size": 3,
  "goals_completed": 5,
  "goals_failed": 1,
  "error_retries": 0
}
```

---

#### `POST /autonomous/pause`

Pause the background worker and any active session.

**Response:**
```json
{
  "action": "pause",
  "status": "paused",
  "message": "Background worker paused"
}
```

---

#### `POST /autonomous/resume`

Resume the background worker from paused/throttled/error state.

**Response:**
```json
{
  "action": "resume",
  "status": "running",
  "message": "Background worker resumed"
}
```

---

#### `POST /autonomous/goal`

Add a new goal to the worker's priority queue.

**Request Body:**
```json
{
  "description": "Write unit tests for the auth module",
  "priority": "high",
  "deadline": 1719504000,
  "project_path": "/home/user/my-project"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | `string` | Yes | Goal description |
| `priority` | `string` | No | `critical`, `high`, `normal`, or `low` (default: `normal`) |
| `deadline` | `number` | No | Unix timestamp deadline |
| `project_path` | `string` | No | Project path |

**Response:**
```json
{
  "goal_id": "goal-uuid",
  "status": "queued",
  "priority": "high",
  "message": "Goal added to queue: Write unit tests..."
}
```

---

#### `GET /autonomous/goals`

List all goals in the queue with their status.

**Response:**
```json
{
  "goals": [
    {
      "id": "goal-1",
      "description": "Write unit tests",
      "priority": "high",
      "status": "in_progress"
    }
  ],
  "total": 3
}
```

---

### Autonomous Checkpoint Endpoints

#### `POST /autonomous/checkpoint/{session_id}`

Force an immediate checkpoint save for a session.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `session_id` | `string` | The session ID to checkpoint |

**Response:**
```json
{
  "session_id": "sess-uuid",
  "checkpoint_file": "/path/to/checkpoint.json",
  "status": "saved",
  "task_count": 5,
  "message": "Checkpoint saved to /path/to/checkpoint.json"
}
```

**Errors:** `404` — Session not found, `500` — Save failure

---

#### `GET /autonomous/checkpoints`

List all available checkpoints.

**Response:**
```json
{
  "checkpoints": [
    {
      "session_id": "sess-1",
      "saved_at": 1716912000,
      "task_count": 5
    }
  ],
  "total": 3
}
```

---

#### `GET /autonomous/checkpoints/{session_id}`

Load a checkpoint by session ID.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `session_id` | `string` | The session ID to load |

**Response:**
```json
{
  "session_id": "sess-uuid",
  "goal": "Refactor auth module",
  "status": "paused",
  "project_path": "/home/user/project",
  "current_task_index": 2,
  "saved_at": 1716912000,
  "task_count": 5,
  "tasks": [...],
  "output_log_length": 42,
  "file_hash_count": 12,
  "git_state": { ... }
}
```

**Errors:** `404` — Checkpoint not found

---

#### `DELETE /autonomous/checkpoints/{session_id}`

Delete a checkpoint by session ID.

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `session_id` | `string` | The session ID to delete |

**Response:**
```json
{
  "session_id": "sess-uuid",
  "deleted": true
}
```

**Errors:** `404` — Checkpoint not found

---

### Autonomous Safety Endpoints

#### `GET /autonomous/safety/stats`

Return safety monitor statistics.

**Response:**
```json
{
  "total_scans": 152,
  "blocked_operations": 3,
  "deletion_count": 12,
  "rate_limit_hits": 0,
  "last_scan": 1716912000
}
```

---

#### `POST /autonomous/safety/reset`

Reset safety monitor counters (failure counts, deletion counts).

**Response:**
```json
{
  "status": "reset",
  "message": "Safety counters reset"
}
```

---

### Autonomous Resource Endpoints

#### `GET /autonomous/resources`

Return current system resource usage.

**Response:**
```json
{
  "cpu_percent": 15.2,
  "memory_mb": 512.3,
  "memory_percent": 12.5,
  "disk_usage_gb": 45.2,
  "timestamp": 1716912000
}
```

---

### Notification Endpoints

#### `POST /notifications`

Send a notification (test endpoint or manual send).

**Request Body:**
```json
{
  "title": "Task Complete",
  "body": "The authentication refactor is finished",
  "actions": ["View", "Dismiss"],
  "urgency": "normal"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | `string` | Yes | Notification title |
| `body` | `string` | Yes | Notification body text |
| `actions` | `string[]` | No | Action button labels |
| `urgency` | `string` | No | `low`, `normal`, or `critical` (default: `normal`) |

**Response:**
```json
{
  "sent": true,
  "title": "Task Complete",
  "urgency": "normal"
}
```

---

#### `GET /notifications/recent`

Get recent notifications.

**Query Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `limit` | `integer` | No | Maximum notifications (default: 10) |

**Response:**
```json
{
  "notifications": [
    {
      "id": "notif-1",
      "title": "Task Complete",
      "body": "...",
      "timestamp": 1716912000,
      "urgency": "normal"
    }
  ],
  "total": 5
}
```

---

#### `GET /notifications/stats`

Return notification service statistics.

**Response:**
```json
{
  "total_sent": 45,
  "total_failed": 2,
  "pending": 1,
  "by_urgency": {
    "low": 10,
    "normal": 30,
    "critical": 5
  }
}
```

---

#### `POST /notifications/flush`

Attempt to re-send all queued notifications.

**Response:**
```json
{
  "delivered": 3,
  "message": "Flushed 3 queued notifications"
}
```

---

#### `DELETE /notifications/clear`

Clear all notification history.

**Response:**
```json
{
  "status": "cleared",
  "message": "Notification history cleared"
}
```

---

## Data Types

### Summary of All Data Types

#### Rust → TypeScript Types

| Rust Type | TypeScript Equivalent | Description |
|-----------|----------------------|-------------|
| `ConversationMessage` | `{ id: string, timestamp: number, role: string, content: string }` | Chat message |
| `CodeEvent` | `{ id: string, timestamp: number, file_path: string, change_type: string, diff: string \| null, summary: string }` | Code change record |
| `Preference` | `{ key: string, value: string, confidence: number, last_updated: number }` | User preference |
| `ProjectState` | `{ project_path: string, current_branch: string, last_commit: string, agent_context_json: string }` | Project snapshot |
| `ContextItem` | `{ id: string, source: string, content: string, relevance: number, timestamp: number }` | Search result |
| `AgentSession` | `{ id: string, goal: string, status: AgentStatus, tasks: AgentTask[], current_task_index: number, output_log: AgentOutputEvent[], created_at: number, updated_at: number, project_path: string }` | Agent session |
| `AgentTask` | `{ id: string, description: string, status: TaskStatus, result: string \| null, error: string \| null }` | Individual task |
| `AgentOutputEvent` | `{ session_id: string, event_type: string, content: string, timestamp: number }` | Output event |
| `AutonomousState` | `{ status: string, enabled: boolean, current_goal: string \| null, progress_percent: number, queue_size: number, checkpoints_saved: number, tasks_completed: number, started_at: number \| null, last_checkpoint_at: number \| null, resource_cpu: number, resource_memory: number }` | Worker state |
| `LogEntry` | `{ timestamp: number, level: string, message: string, source: string }` | Log entry |

### Status Enums

**AgentStatus:**
```typescript
type AgentStatus = 'Idle' | 'Running' | 'Paused' | 'Completed' | 'Failed' | 'Waiting';
```

**TaskStatus:**
```typescript
type TaskStatus = 'Pending' | 'InProgress' | 'Completed' | 'Failed' | 'Blocked';
```

**AutonomousStatus:**
```typescript
type AutonomousStatus = 'Disabled' | 'Idle' | 'Running' | 'Paused' | 'Throttled' | 'Error';
```
