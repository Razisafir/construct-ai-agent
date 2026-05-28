//! Agent control commands — start, pause, resume, stop, status, output.
//!
//! The agent runs asynchronously in a background task. Output is streamed
//! to the frontend via Tauri events (not command return values).
//!
//! # Frontend usage
//! ```ts
//! // Start an agent session
//! const sessionId = await invoke('start_agent', {
//!   goal: 'Create a Counter component',
//!   projectPath: '/path/to/project'
//! });
//!
//! // Listen for output events
//! listen(`agent:${sessionId}`, (event) => {
//!   const output = event.payload as AgentOutputEvent;
//!   console.log(output.event_type, output.content);
//! });
//! ```

use std::collections::HashMap;
use std::sync::Arc;

use chrono::Utc;
use parking_lot::Mutex;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, State};
use uuid::Uuid;

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

/// Overall state of an agent session.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AgentStatus {
    Idle,
    Running,
    Paused,
    Completed,
    Failed,
    Waiting,
}

/// Status of an individual task within a session.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TaskStatus {
    Pending,
    InProgress,
    Completed,
    Failed,
    Blocked,
}

/// A single task the agent is working on.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentTask {
    pub id: String,
    pub description: String,
    pub status: TaskStatus,
    pub result: Option<String>,
    pub error: Option<String>,
}

/// A running (or completed) agent session.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentSession {
    pub id: String,
    pub goal: String,
    pub status: AgentStatus,
    pub tasks: Vec<AgentTask>,
    pub current_task_index: usize,
    pub output_log: Vec<AgentOutputEvent>,
    pub created_at: i64,
    pub updated_at: i64,
    pub project_path: String,
}

/// A single output event emitted by the agent.
///
/// The `event_type` field is one of:
/// - `"thought"` — the agent's internal reasoning
/// - `"tool_call"` — a tool is being invoked
/// - `"tool_result"` — result from a tool invocation
/// - `"code"` — generated code snippet
/// - `"error"` — an error occurred
/// - `"complete"` — the session finished successfully
/// - `"task_start"` — a new task has started
/// - `"task_complete"` — a task finished successfully
/// - `"task_failed"` — a task failed
/// - `"waiting"` — the agent is waiting for user input
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentOutputEvent {
    pub session_id: String,
    #[serde(rename = "type")]
    pub event_type: String,
    pub content: String,
    pub timestamp: i64,
}

// ---------------------------------------------------------------------------
// Shared state
// ---------------------------------------------------------------------------

/// Thread-safe store of all active and completed agent sessions.
pub struct AgentState {
    pub sessions: Arc<Mutex<HashMap<String, AgentSession>>>,
}

impl AgentState {
    pub fn new() -> Self {
        Self {
            sessions: Arc::new(Mutex::new(HashMap::new())),
        }
    }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Emit an output event for the given session.
///
/// Events are sent on the channel `agent:{session_id}` so the frontend
/// can scope listeners to a single session.
fn emit_output(app: &AppHandle, session_id: &str, event_type: &str, content: &str) {
    let event = AgentOutputEvent {
        session_id: session_id.to_string(),
        event_type: event_type.to_string(),
        content: content.to_string(),
        timestamp: Utc::now().timestamp(),
    };

    let channel = format!("agent:{}", session_id);

    if let Err(e) = app.emit(&channel, event.clone()) {
        eprintln!("[agent] failed to emit event on '{}': {}", channel, e);
    }

    // Also append to the in-memory log so `get_agent_output` can paginate.
    // NOTE: we do *not* hold the lock while emitting — the event is already
    // sent; this just stores it for later replay.
    // In a real implementation we would need access to the state map here.
    // The log is updated by the background task itself (see `start_agent`).
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

/// Start a new agent session with the given goal.
///
/// Returns the session ID immediately. The agent runs in the background
/// and streams output via Tauri events on the channel `agent:{session_id}`.
///
/// # Example (frontend)
/// ```ts
/// const sessionId = await invoke('start_agent', {
///   goal: 'Create a Counter component',
///   projectPath: '/home/user/my-project'
/// });
///
/// listen(`agent:${sessionId}`, (event) => {
///   const output = event.payload as AgentOutputEvent;
///   appendToUI(output);
/// });
/// ```
#[tauri::command]
pub fn start_agent(
    state: State<'_, AgentState>,
    app_handle: AppHandle,
    goal: String,
    project_path: Option<String>,
) -> Result<String, String> {
    let session_id = Uuid::new_v4().to_string()[..8].to_string();

    let session = AgentSession {
        id: session_id.clone(),
        goal: goal.clone(),
        status: AgentStatus::Running,
        tasks: vec![],
        current_task_index: 0,
        output_log: vec![],
        created_at: Utc::now().timestamp(),
        updated_at: Utc::now().timestamp(),
        project_path: project_path.clone().unwrap_or_else(|| ".".to_string()),
    };

    {
        let mut sessions = state.sessions.lock();
        sessions.insert(session_id.clone(), session);
    }

    // Spawn background task that calls the Python agent backend.
    let sessions = state.sessions.clone();
    let sid = session_id.clone();
    let app = app_handle.clone();
    let path = project_path.unwrap_or_else(|| ".".to_string());
    let goal_clone = goal.clone();

    std::thread::spawn(move || {
        // Emit initial event.
        let initial_event = AgentOutputEvent {
            session_id: sid.clone(),
            event_type: "thought".to_string(),
            content: format!(
                "Starting agent session for goal: {} (project: {})",
                goal_clone, path
            ),
            timestamp: Utc::now().timestamp(),
        };

        {
            let mut sessions = sessions.lock();
            if let Some(session) = sessions.get_mut(&sid) {
                session.output_log.push(initial_event.clone());
            }
        }

        let _ = app.emit(&format!("agent:{}", sid), initial_event);

        // TODO: Call Python backend API to actually run the agent.
        // For now, emit a demo event sequence so the UI works immediately.
        std::thread::sleep(std::time::Duration::from_secs(1));

        let demo_events: Vec<(&str, &str)> = vec![
            ("thought", "Analyzing project structure..."),
            ("tool_call", "list_directory({\"dir_path\": \".\"})"),
            ("tool_result", "Found: src/, package.json, README.md"),
            (
                "thought",
                "Project is a React + TypeScript app. Planning component creation.",
            ),
            ("task_start", "Create Counter component file"),
            (
                "tool_call",
                "write_file({\"file_path\": \"src/components/Counter.tsx\", ...})",
            ),
            ("tool_result", "File written successfully (245 bytes)"),
            ("task_complete", "Create Counter component file"),
            ("task_start", "Add Counter to App.tsx"),
            (
                "tool_call",
                "read_file({\"file_path\": \"src/App.tsx\"})",
            ),
            ("tool_result", "Read 12 lines from src/App.tsx"),
            (
                "code",
                "import { Counter } from './components/Counter';\n// ...",
            ),
            ("task_complete", "Add Counter to App.tsx"),
            ("task_start", "Run tests to verify"),
            (
                "tool_call",
                "run_test({\"test_command\": \"npm test\"})",
            ),
            ("tool_result", "Tests passed: 3/3"),
            ("task_complete", "Run tests to verify"),
            (
                "complete",
                "All tasks completed! Counter component created and verified.",
            ),
        ];

        for (event_type, content) in demo_events {
            // Respect pause — if the session is paused, spin-wait.
            loop {
                let is_paused = {
                    let sessions = sessions.lock();
                    if let Some(session) = sessions.get(&sid) {
                        matches!(session.status, AgentStatus::Paused)
                    } else {
                        false
                    }
                };

                if !is_paused {
                    break;
                }
                std::thread::sleep(std::time::Duration::from_millis(200));
            }

            // Check if the session was stopped (marked Failed).
            let was_stopped = {
                let sessions = sessions.lock();
                if let Some(session) = sessions.get(&sid) {
                    matches!(session.status, AgentStatus::Failed)
                } else {
                    true
                }
            };

            if was_stopped {
                let abort_event = AgentOutputEvent {
                    session_id: sid.clone(),
                    event_type: "error".to_string(),
                    content: "Session was stopped by the user.".to_string(),
                    timestamp: Utc::now().timestamp(),
                };

                {
                    let mut sessions = sessions.lock();
                    if let Some(session) = sessions.get_mut(&sid) {
                        session.output_log.push(abort_event.clone());
                    }
                }

                let _ = app.emit(&format!("agent:{}", sid), abort_event);
                return;
            }

            std::thread::sleep(std::time::Duration::from_millis(800));

            let event = AgentOutputEvent {
                session_id: sid.clone(),
                event_type: event_type.to_string(),
                content: content.to_string(),
                timestamp: Utc::now().timestamp(),
            };

            {
                let mut sessions = sessions.lock();
                if let Some(session) = sessions.get_mut(&sid) {
                    session.output_log.push(event.clone());
                    session.updated_at = Utc::now().timestamp();

                    // Update task tracking based on event type.
                    match event_type {
                        "task_start" => {
                            let task = AgentTask {
                                id: format!("task-{}", session.tasks.len()),
                                description: content.to_string(),
                                status: TaskStatus::InProgress,
                                result: None,
                                error: None,
                            };
                            session.tasks.push(task);
                            session.current_task_index = session.tasks.len().saturating_sub(1);
                        }
                        "task_complete" => {
                            if let Some(task) = session.tasks.last_mut() {
                                task.status = TaskStatus::Completed;
                                task.result = Some(content.to_string());
                            }
                        }
                        "task_failed" => {
                            if let Some(task) = session.tasks.last_mut() {
                                task.status = TaskStatus::Failed;
                                task.error = Some(content.to_string());
                            }
                        }
                        "error" => {
                            session.status = AgentStatus::Failed;
                        }
                        _ => {}
                    }
                }
            }

            let _ = app.emit(&format!("agent:{}", sid), event);
        }

        // Mark session as completed.
        let mut sessions = sessions.lock();
        if let Some(session) = sessions.get_mut(&sid) {
            session.status = AgentStatus::Completed;
            session.updated_at = Utc::now().timestamp();
        }
    });

    Ok(session_id)
}

/// Get the current status and full details of an agent session.
///
/// # Example (frontend)
/// ```ts
/// const session = await invoke('get_agent_status', { sessionId: 'abc12345' });
/// console.log(session.status, session.tasks);
/// ```
#[tauri::command]
pub fn get_agent_status(
    state: State<'_, AgentState>,
    session_id: String,
) -> Result<AgentSession, String> {
    let sessions = state.sessions.lock();
    sessions
        .get(&session_id)
        .cloned()
        .ok_or_else(|| "Session not found".to_string())
}

/// Pause a running agent session.
///
/// The background task will spin-wait until `resume_agent` is called.
#[tauri::command]
pub fn pause_agent(
    state: State<'_, AgentState>,
    session_id: String,
) -> Result<(), String> {
    let mut sessions = state.sessions.lock();
    if let Some(session) = sessions.get_mut(&session_id) {
        session.status = AgentStatus::Paused;
        session.updated_at = Utc::now().timestamp();
        Ok(())
    } else {
        Err("Session not found".to_string())
    }
}

/// Resume a paused agent session.
///
/// The background task will break out of its spin-wait and continue
/// emitting events.
#[tauri::command]
pub fn resume_agent(
    state: State<'_, AgentState>,
    session_id: String,
) -> Result<(), String> {
    let mut sessions = state.sessions.lock();
    if let Some(session) = sessions.get_mut(&session_id) {
        session.status = AgentStatus::Running;
        session.updated_at = Utc::now().timestamp();
        Ok(())
    } else {
        Err("Session not found".to_string())
    }
}

/// Stop (terminate) an agent session.
///
/// Sets the session status to `Failed`. The background task detects
/// this on its next iteration and exits cleanly after emitting an
/// abort event.
#[tauri::command]
pub fn stop_agent(
    state: State<'_, AgentState>,
    session_id: String,
) -> Result<(), String> {
    let mut sessions = state.sessions.lock();
    if let Some(session) = sessions.get_mut(&session_id) {
        session.status = AgentStatus::Failed;
        session.updated_at = Utc::now().timestamp();
        Ok(())
    } else {
        Err("Session not found".to_string())
    }
}

/// Get output events for a session since a given index.
///
/// This is useful for polling (as a fallback when events are missed)
/// or for fetching historical output after a page reload.
///
/// # Example (frontend)
/// ```ts
/// const events = await invoke('get_agent_output', {
///   sessionId: 'abc12345',
///   sinceIndex: 10
/// });
/// ```
#[tauri::command]
pub fn get_agent_output(
    state: State<'_, AgentState>,
    session_id: String,
    since_index: Option<usize>,
) -> Result<Vec<AgentOutputEvent>, String> {
    let sessions = state.sessions.lock();
    if let Some(session) = sessions.get(&session_id) {
        let start = since_index.unwrap_or(0);
        Ok(session.output_log.iter().skip(start).cloned().collect())
    } else {
        Err("Session not found".to_string())
    }
}
