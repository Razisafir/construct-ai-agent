# System Architecture

> **Version:** 0.1.0  
> **Last Updated:** 2026-05-28

---

## Overview

Construct is a desktop AI coding agent built on a three-tier architecture:

1. **Frontend** — React 18 + TypeScript + Tailwind CSS, served inside a Tauri v2 shell
2. **Backend (Rust)** — Tauri commands, SQLite database, system tray, process management
3. **Agent (Python)** — FastAPI server, LLM service, tool system, ChromaDB semantic memory

```
+-----------------------------------------------------------+
|                        Desktop Window                      |
|  +-----------------------------------------------------+  |
|  |                  React 18 Frontend                   |  |
|  |  +-----------+  +----------+  +------------------+  |  |
|  |  | Sidebar   |  | Editor   |  | Panel (Bottom)   |  |  |
|  |  | - File    |  | Monaco   |  | - Terminal       |  |  |
|  |  |   tree    |  | Editor   |  | - Problems       |  |  |
|  |  | - Nav     |  |          |  | - Chat           |  |  |
|  |  +-----------+  +----------+  | - Agent          |  |  |
|  |                               | - Memory         |  |  |
|  |                               +------------------+  |  |
|  +-------------------|----------------|------------------+  |
|                      | invoke()  | listen()               |
+----------------------|----------|--------------------------+
                       |          |
            +----------v----------v----------+
            |      Tauri v2 (Rust)            |
            |  +---------------------------+  |
            |  |  SQLite (rusqlite/WAL)    |  |
            |  |  - conversations          |  |
            |  |  - code_events            |  |
            |  |  - user_preferences       |  |
            |  |  - project_state          |  |
            |  +---------------------------+  |
            |  +---------------------------+  |
            |  |  AgentState (in-memory)   |  |
            |  |  - sessions HashMap       |  |
            |  +---------------------------+  |
            |  +---------------------------+  |
            |  |  AutonomousManager        |  |
            |  |  - background worker      |  |
            |  +---------------------------+  |
            +---------------|-----------------+
                            | HTTP/WebSocket
                            |
                +-----------v-----------+
                |   Python FastAPI      |
                |   (Port 8000)         |
                +-----------|-----------+
                            |
        +-------------------+-------------------+
        |                   |                   |
+-------v--------+ +-------v--------+ +--------v--------+
|  LLM Service   | |  Tool System   | |  Memory Layer   |
|                | |                | |                 |
| - OpenAI GPT   | | - File tools   | | - ChromaDB      |
| - Anthropic    | | - Shell tools  | | - Embedding     |
| - Google       | | - Git tools    | | - Semantic      |
| - Ollama       | | - Code tools   | |   search        |
+-------+--------+ +-------+--------+ +--------+--------+
        |                   |                   |
        +---------+---------+---------+---------+
                  |                   |
          +-------v--------+ +--------v--------+
          |  Orchestrator  | |  Safety/Security |
          |                | |                  |
          | - Role agents  | | - AgentShield    |
          | - Task planner | | - Approval req   |
          | - Execution    | | - Rate limiting  |
          +----------------+ +------------------+
```

---

## Frontend (React + Tauri)

### Component Hierarchy

```
App.tsx
├── Sidebar.tsx          # Left navigation panel
│   ├── File tree
│   └── Navigation links
├── Editor.tsx           # Monaco code editor
│   └── Monaco Editor (CDN-loaded)
├── Panel.tsx            # Bottom panel container
│   ├── AgentPanel.tsx   # AI agent control
│   │   ├── Goal input
│   │   ├── Start/Pause/Resume/Stop buttons
│   │   ├── Task list with status
│   │   └── Output stream viewer
│   ├── MemoryPanel.tsx  # Memory system UI
│   │   ├── Conversation history
│   │   ├── Code events
│   │   └── Preferences
│   ├── Terminal         # Shell output
│   └── Problems         # Error/diagnostic list
└── StatusBar.tsx        # Bottom status bar
    ├── Current project
    ├── Git branch
    ├── LLM provider
    └── Connection status
```

### State Management

The frontend uses **Zustand** (via `useAppStore.ts`) for global state:

```typescript
interface AppState {
  // UI state
  activePanel: 'terminal' | 'problems' | 'chat' | 'agent' | 'memory';
  sidebarVisible: boolean;
  
  // Project state
  currentProject: string;
  currentBranch: string;
  
  // Agent state
  agentSessionId: string | null;
  agentStatus: 'idle' | 'running' | 'paused' | 'completed' | 'failed';
  agentTasks: AgentTask[];
  agentOutput: AgentOutputEvent[];
  
  // Memory state
  conversations: ConversationMessage[];
  codeEvents: CodeEvent[];
  preferences: Preference[];
}
```

### Event Flow

The frontend communicates with the Rust backend via **Tauri invocations** and **event listeners**:

```
User Action
    |
    v
+---+------------------------+
|  invoke('command', args)   |  <-- Synchronous request/response
+---+------------------------+
    |
    v
+---+------------------------+
|  listen('agent:{id}', cb)  |  <-- Asynchronous event stream
+---+------------------------+
    |
    v
Rust Backend (Tauri Command)
    |
    v
HTTP Request to Python API (port 8000)
    |
    v
Python Agent Processing
    |
    v
Event emitted back to Frontend
```

**Key patterns:**
- **Commands** (invoke): Memory CRUD, agent control, state queries
- **Events** (listen): Real-time agent output, autonomous mode updates, notifications

---

## Backend (Rust)

### Tauri Commands

Commands are organized in three modules:

| Module | File | Commands | Purpose |
|--------|------|----------|---------|
| `memory` | `commands/memory.rs` | 8 | SQLite memory CRUD |
| `agent` | `commands/agent.rs` | 6 | Agent session lifecycle |
| `autonomous` | `commands/autonomous.rs` | 5 | Background worker control |

### State Management

Three shared state objects are managed via Tauri's `app.manage()`:

1. **`AppState`** — SQLite connection (Mutex-wrapped)
2. **`AgentState`** — In-memory HashMap of agent sessions
3. **`AutonomousManager`** — Background worker state + log ring buffer

```rust
// In lib.rs setup()
app.manage(state);           // AppState -> SQLite
app.manage(AgentState::new());         // Agent sessions
app.manage(AutonomousManager::new());  // Autonomous worker
```

### SQLite Database (`db.rs`)

**Location:**
- macOS: `~/Library/Application Support/construct/construct.db`
- Windows: `%APPDATA%\construct\construct.db`
- Linux: `~/.local/share/construct/construct.db`

**Schema:**

| Table | Columns | Purpose |
|-------|---------|---------|
| `conversations` | id, timestamp, role, content, embedding_vector | Message history |
| `code_events` | id, timestamp, file_path, change_type, diff, summary | Code changes |
| `user_preferences` | key, value, confidence, last_updated | Learned preferences |
| `project_state` | project_path, current_branch, last_commit, agent_context_json, updated_at | Project snapshot |

**Optimizations:**
- WAL (Write-Ahead Logging) mode enabled
- 64 MB page cache
- Memory-mapped I/O (30 GB)
- Incremental auto-vacuum

---

## Agent (Python)

### LLM Service (`core/llm_service.py`)

Multi-provider LLM with smart routing:

| Provider | Model | Trigger |
|----------|-------|---------|
| OpenAI | GPT-4o | Code tasks (if Anthropic unavailable) |
| Anthropic | Claude Sonnet | Code tasks, complex reasoning |
| Google | Gemini 1.5 Pro | Long context (if configured) |
| Ollama | qwen2.5-coder:14b | Short prompts (< 200 chars), fallback |

**Routing logic:**
```
Prompt < 200 chars       -> Ollama (fast, local)
Contains code keywords    -> Anthropic > OpenAI
Contains reasoning words  -> Anthropic
Default                   -> Anthropic > OpenAI > Google > Ollama
```

**Features:**
- Streaming and non-streaming completions
- Automatic fallback to Ollama on cloud provider failure
- Token usage logging with timing
- Tool schema injection for function calling

### Tool System (`tools/`)

21 tools organized in 4 categories:

| Category | Tools | Description |
|----------|-------|-------------|
| **File** | `read_file`, `write_file`, `list_directory`, `search_files` | File system operations |
| **Shell** | `execute_command`, `run_test`, `install_dependency` | Command execution |
| **Git** | `git_status`, `git_diff`, `git_commit`, `git_branch`, `git_log`, `git_checkout` | Version control |
| **Code** | `parse_ast`, `find_references`, `refactor_rename`, `extract_function` | Code analysis |

### Execution Loop (`core/executor.py`)

```
+-----------+     +----------+     +----------+     +-----------+
|  Observe  | --> |   Plan   | --> |   Act    | --> |  Verify   |
|  Project  |     |  Tasks   |     |  Tools   |     |  Results  |
+-----------+     +----------+     +----------+     +-----+-----+
      ^                                                  |
      +--------------------------------------------------+
                        (Iterate until complete)
```

### Memory Layer (`memory/semantic.py`)

ChromaDB-backed semantic memory with sentence-transformer embeddings:

| Collection | Content |
|------------|---------|
| `conversation_embeddings` | Vectorized conversation messages |
| `code_embeddings` | Vectorized code events and diffs |

**Operations:**
- `store_conversation_message()` — Store a message with embedding
- `store_code_event()` — Store a code event with embedding
- `query_similar()` — Semantic search across all collections
- `query_conversations()` — Search conversations only
- `query_code_events()` — Search code events only
- `hybrid_search()` — Fuse SQLite FTS with vector similarity

### Specialized Agent Roles (`agents/roles/`)

7 specialized roles for different task types:

| Role | File | Expertise |
|------|------|-----------|
| Code Engineer | `code_engineer.py` | Writing, refactoring, debugging code |
| Test Engineer | `test_engineer.py` | Writing tests, test plans |
| Security Auditor | `security_auditor.py` | Security review, vulnerability scanning |
| DevOps Engineer | `devops_engineer.py` | CI/CD, deployment, infrastructure |
| UI Designer | `ui_designer.py` | UI/UX design, component creation |
| Researcher | `researcher.py` | Research, documentation, analysis |
| Project Manager | `project_manager.py` | Task planning, estimation |
| Legal Reviewer | `legal_reviewer.py` | License compliance, legal review |

The **Orchestrator** (`agents/orchestrator.py`) routes tasks to the appropriate role agent.

---

## Data Flow

### 1. User Sends a Message

```
User types in Chat Panel
         |
         v
Frontend: invoke('record_conversation', message)
         |
         v
Rust: db::record_conversation() -> SQLite
         |
         v
Frontend: HTTP POST /memory/message -> Python
         |
         v
Python: store_conversation_message() -> ChromaDB (with embedding)
         |
         v
LLM processes message -> response generated
         |
         v
Rust: db::record_conversation() (assistant response)
Python: store_conversation_message() (assistant response)
         |
         v
Frontend displays response
```

### 2. Agent Executes a Task

```
User clicks "Start Agent" with goal
         |
         v
Frontend: invoke('start_agent', { goal, projectPath })
         |
         v
Rust: Creates session, spawns background thread
         |
         v
Thread: HTTP POST /agent/start -> Python
         |
         v
Python: AgentExecutor.start_session()
         |   - Plan tasks
         |   - Execute loop (observe -> plan -> act -> verify)
         |   - Call tools as needed
         |
         v
Rust: Emits events on channel 'agent:{sessionId}'
         |
         v
Frontend: listen('agent:{sessionId}', callback)
         |   - Updates task list
         |   - Appends to output log
         |   - Displays code snippets
```

### 3. Autonomous Mode

```
User enables autonomous mode
         |
         v
Frontend: invoke('enable_autonomous_mode')
         |
         v
Rust: Sets enabled=true, emits 'autonomous:started'
         |
         v
BackgroundWorker runs continuously:
   - Check goal queue
   - Execute highest-priority goal
   - Save checkpoints periodically
   - Monitor resource usage
   - Enforce safety limits
         |
         v
Rust: Emits events:
   'autonomous:checkpoint' — Progress updates
   'autonomous:completed'  — Goal finished
   'autonomous:error'      — Error occurred
```

---

## Security Model

### Trust Boundaries

```
+-----------------------------------------------------+
|  Trust Boundary: Tauri Desktop Shell                |
|                                                     |
|  +----------------+    +-------------------------+  |
|  |  Frontend      |    |  Rust Backend           |  |
|  |  (Sandboxed)   |<-->|  (Native OS access)     |  |
|  +----------------+    +-------------------------+  |
|                                                     |
|  - Frontend cannot access filesystem directly       |
|  - All file access goes through Tauri APIs          |
|  - Frontend code runs in WebView sandbox            |
+-----------------------------------------------------+
                            |
                            v HTTP (localhost only)
+-----------------------------------------------------+
|  Trust Boundary: Python Agent Backend               |
|                                                     |
|  - Runs as separate process                         |
|  - Shell command execution sandboxed                |
|  - File access limited to project directory         |
|  - Git operations require explicit approval         |
+-----------------------------------------------------+
```

### Permission Model

| Operation | Approval Required | Configurable |
|-----------|-------------------|--------------|
| Read files | No | — |
| Write files | No | — |
| Shell commands | `destructive_only` | `REQUIRE_APPROVAL` |
| Git commit/push | `destructive_only` | `REQUIRE_APPROVAL` |
| Delete files | Always | — |
| Install dependencies | `destructive_only` | `REQUIRE_APPROVAL` |

**Approval levels:**
- `none` — No approval required (not recommended)
- `destructive_only` — Only destructive operations need approval (default)
- `all` — All operations need approval

### AgentShield (`security/agentshield.py`)

Automated security scanning that:
- Scans generated code for known vulnerability patterns
- Blocks unsafe shell commands
- Enforces rate limits on tool calls
- Tracks deletion counts to prevent mass-deletion
- Logs all security events

---

## Key Files Reference

| Layer | File | Purpose |
|-------|------|---------|
| **Frontend** | `src/renderer/App.tsx` | Main app component |
| | `src/renderer/components/AgentPanel.tsx` | Agent UI |
| | `src/renderer/components/MemoryPanel.tsx` | Memory UI |
| | `src/renderer/stores/useAppStore.ts` | Zustand state |
| **Rust** | `src/main/src/lib.rs` | App entry point |
| | `src/main/src/db.rs` | SQLite layer |
| | `src/main/src/commands/memory.rs` | Memory commands |
| | `src/main/src/commands/agent.rs` | Agent commands |
| | `src/main/src/commands/autonomous.rs` | Autonomous commands |
| **Python** | `agent-backend/app.py` | FastAPI server |
| | `agent-backend/core/llm_service.py` | LLM service |
| | `agent-backend/core/executor.py` | Execution loop |
| | `agent-backend/memory/semantic.py` | ChromaDB memory |
| | `agent-backend/tools/` | Tool implementations |
