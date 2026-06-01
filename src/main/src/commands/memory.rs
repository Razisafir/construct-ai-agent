//! Tauri command wrappers for the memory database layer.
//!
//! These commands are registered in `lib.rs` and can be invoked from the
//! frontend via `invoke('command_name', { ... })`.

use tauri::State;

use crate::db::{
    AppState, CodeEvent, ConversationMessage, ContextItem, Preference, ProjectState,
};

/// Helper: lock the mutex and borrow the inner `rusqlite::Connection`.
fn conn(state: &AppState) -> Result<std::sync::MutexGuard<'_, crate::db::SendConnection>, String> {
    state.db.lock().map_err(|e| e.to_string())
}

// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------

/// Store a conversation message in the database.
///
/// # Example (frontend)
/// ```ts
/// await invoke('record_conversation', {
///   message: { id: 'uuid', timestamp: 123, role: 'user', content: 'Hello!' }
/// });
/// ```
#[tauri::command]
pub fn record_conversation(
    state: State<AppState>,
    message: ConversationMessage,
) -> Result<(), String> {
    let db = conn(&state)?;
    crate::db::record_conversation(&db.0, &message).map_err(|e| e.to_string())
}

/// Retrieve recent conversation messages (newest last).
///
/// # Example (frontend)
/// ```ts
/// const messages = await invoke('get_recent_conversations', { limit: 50 });
/// ```
#[tauri::command]
pub fn get_recent_conversations(
    state: State<AppState>,
    limit: Option<usize>,
) -> Result<Vec<ConversationMessage>, String> {
    let db = conn(&state)?;
    crate::db::get_recent_conversations(&db.0, limit.unwrap_or(50)).map_err(|e| e.to_string())
}

// ---------------------------------------------------------------------------
// Code events
// ---------------------------------------------------------------------------

/// Record a code change event.
///
/// # Example (frontend)
/// ```ts
/// await invoke('record_code_event', {
///   event: { id: 'uuid', timestamp: 123, file_path: 'src/main.rs',
///            change_type: 'create', diff: '...', summary: 'Created main.rs' }
/// });
/// ```
#[tauri::command]
pub fn record_code_event(state: State<AppState>, event: CodeEvent) -> Result<(), String> {
    let db = conn(&state)?;
    crate::db::record_code_event(&db.0, &event).map_err(|e| e.to_string())
}

/// Retrieve recent code events (oldest first).
///
/// # Example (frontend)
/// ```ts
/// const events = await invoke('get_recent_code_events', { limit: 20 });
/// ```
#[tauri::command]
pub fn get_recent_code_events(
    state: State<AppState>,
    limit: Option<usize>,
) -> Result<Vec<CodeEvent>, String> {
    let db = conn(&state)?;
    crate::db::get_recent_code_events(&db.0, limit.unwrap_or(20)).map_err(|e| e.to_string())
}

// ---------------------------------------------------------------------------
// Preferences
// ---------------------------------------------------------------------------

/// Store or update a user preference with default confidence (0.8).
///
/// # Example (frontend)
/// ```ts
/// await invoke('store_preference', { key: 'theme', value: 'dark' });
/// ```
#[tauri::command]
pub fn store_preference(
    state: State<AppState>,
    key: String,
    value: String,
) -> Result<(), String> {
    let db = conn(&state)?;
    crate::db::store_preference(&db.0, &key, &value, 0.8).map_err(|e| e.to_string())
}

/// Retrieve all stored preferences ordered by confidence (highest first).
///
/// # Example (frontend)
/// ```ts
/// const prefs = await invoke('get_preferences');
/// ```
#[tauri::command]
pub fn get_preferences(state: State<AppState>) -> Result<Vec<Preference>, String> {
    let db = conn(&state)?;
    crate::db::get_preferences(&db.0).map_err(|e| e.to_string())
}

// ---------------------------------------------------------------------------
// Project state
// ---------------------------------------------------------------------------

/// Fetch the stored project state for a given path.
/// Returns a default state if none has been saved yet.
///
/// # Example (frontend)
/// ```ts
/// const state = await invoke('get_project_state', { path: '/home/user/my-project' });
/// ```
#[tauri::command]
pub fn get_project_state(
    state: State<AppState>,
    path: Option<String>,
) -> Result<ProjectState, String> {
    let db = conn(&state)?;
    // Default to current working directory if no path provided
    let project_path = path.unwrap_or_else(|| {
        std::env::current_dir()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_default()
    });
    crate::db::get_project_state(&db.0, &project_path).map_err(|e| e.to_string())
}

/// Upsert the project state snapshot.
///
/// # Example (frontend)
/// ```ts
/// await invoke('update_project_state', {
///   stateData: { project_path: '/home/user/proj', current_branch: 'main',
///                last_commit: 'abc123', agent_context_json: '{}' }
/// });
/// ```
#[tauri::command]
pub fn update_project_state(
    state: State<AppState>,
    state_data: ProjectState,
) -> Result<(), String> {
    let db = conn(&state)?;
    crate::db::update_project_state(&db.0, &state_data).map_err(|e| e.to_string())
}

// ---------------------------------------------------------------------------
// Unified recall
// ---------------------------------------------------------------------------

/// Search across conversations and code events for context relevant to `query`.
///
/// # Example (frontend)
/// ```ts
/// const ctx = await invoke('recall_context', { query: 'authentication', limit: 10 });
/// ```
#[tauri::command]
pub fn recall_context(
    state: State<AppState>,
    query: String,
    limit: Option<usize>,
) -> Result<Vec<ContextItem>, String> {
    let db = conn(&state)?;
    crate::db::recall_context(&db.0, &query, limit.unwrap_or(10)).map_err(|e| e.to_string())
}
