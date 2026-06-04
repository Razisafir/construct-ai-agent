//! SQLite database layer for persistent agent memory.
//!
//! Provides storage and retrieval for:
//! - Conversations (user/agent message history)
//! - Code events (file changes, diffs, summaries)
//! - User preferences (learned patterns with confidence scores)
//! - Project state (branch, commit, context snapshot)

use chrono::Utc;
use rusqlite::{params, Connection, Result};
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::Manager;

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

/// A single message in the conversation history.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversationMessage {
    pub id: String,
    pub timestamp: i64,
    pub role: String,
    pub content: String,
}

/// A code change event recorded by the agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeEvent {
    pub id: String,
    pub timestamp: i64,
    pub file_path: String,
    pub change_type: String,
    pub diff: Option<String>,
    pub summary: String,
}

/// A learned user preference with confidence score.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Preference {
    pub key: String,
    pub value: String,
    pub confidence: f64,
    pub last_updated: i64,
}

/// Snapshot of the current project state.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectState {
    pub project_path: String,
    pub current_branch: String,
    pub last_commit: String,
    pub agent_context_json: String,
}

/// Unified context item returned by the recall system.
/// Aggregates both conversations and code events, ordered by relevance.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContextItem {
    pub id: String,
    pub source: String,   // "conversation" or "code_event"
    pub content: String,
    pub relevance: f32,   // placeholder for future vector similarity score
    pub timestamp: i64,
}

// ---------------------------------------------------------------------------
// Send-wrapper for rusqlite::Connection
// ---------------------------------------------------------------------------

/// Wrapper that forces `Send` on a `rusqlite::Connection`.
///
/// # Safety
///
/// This is safe because we compile SQLite with `SQLITE_THREADSAFE=1`
/// (via the `bundled` feature), which puts SQLite in *serialized* mode.
/// In this mode SQLite itself guarantees thread-safety as long as no single
/// connection is used from two threads **simultaneously** — a guarantee
/// provided by the `std::sync::Mutex` that wraps this type in `AppState`.
pub struct SendConnection(pub Connection);
unsafe impl Send for SendConnection {}

// ---------------------------------------------------------------------------
// Shared application state
// ---------------------------------------------------------------------------

/// Shared Tauri state holding the SQLite connection.
pub struct AppState {
    pub db: Mutex<SendConnection>,
}

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

/// SQL executed once when the database is first created.
pub const INIT_SQL: &str = r#"
-- conversations: stores all agent conversations
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding_vector BLOB
);
CREATE INDEX IF NOT EXISTS idx_conversations_ts ON conversations(timestamp);
CREATE INDEX IF NOT EXISTS idx_conversations_role ON conversations(role);

-- code_events: tracks code changes made by the agent
CREATE TABLE IF NOT EXISTS code_events (
    id TEXT PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    change_type TEXT NOT NULL,
    diff TEXT,
    summary TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_code_events_ts ON code_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_code_events_file ON code_events(file_path);

-- user_preferences: learned user preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    last_updated INTEGER NOT NULL
);

-- project_state: current project snapshot
CREATE TABLE IF NOT EXISTS project_state (
    project_path TEXT PRIMARY KEY,
    current_branch TEXT NOT NULL DEFAULT '',
    last_commit TEXT NOT NULL DEFAULT '',
    agent_context_json TEXT NOT NULL DEFAULT '{}',
    updated_at INTEGER NOT NULL
);
"#;

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

/// Initialise the SQLite database for the current application.
///
/// The database file is stored in the user's data directory
/// (`~/.local/share/construct/construct.db` on Linux,
/// `~/Library/Application Support/construct/construct.db` on macOS,
/// `%APPDATA%\construct\construct.db` on Windows).
pub fn init_db(app: &mut tauri::App) -> Result<AppState, Box<dyn std::error::Error>> {
    let app_handle = app.handle();
    let app_data_dir = app_handle
        .path()
        .app_data_dir()
        .expect("failed to resolve app data directory");

    std::fs::create_dir_all(&app_data_dir)?;

    let db_path = app_data_dir.join("construct.db");
    let conn = Connection::open(&db_path)?;

    conn.execute_batch(INIT_SQL)?;

    // Enable WAL mode for better concurrency and performance
    conn.execute_batch(
        "PRAGMA journal_mode = WAL;
         PRAGMA synchronous = NORMAL;
         PRAGMA cache_size = -64000;     -- 64 MB cache
         PRAGMA temp_store = MEMORY;
         PRAGMA mmap_size = 30000000000; -- 30 GB memory map
         PRAGMA page_size = 4096;
         PRAGMA auto_vacuum = INCREMENTAL;
        "
    )?;

    Ok(AppState {
        db: Mutex::new(SendConnection(conn)),
    })
}

// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------

/// Persist a single conversation message.
pub fn record_conversation(db: &Connection, msg: &ConversationMessage) -> Result<()> {
    db.execute(
        "INSERT OR REPLACE INTO conversations (id, timestamp, role, content)
         VALUES (?1, ?2, ?3, ?4)",
        params![&msg.id, msg.timestamp, &msg.role, &msg.content],
    )?;
    Ok(())
}

/// Retrieve the most recent conversation messages.
pub fn get_recent_conversations(db: &Connection, limit: usize) -> Result<Vec<ConversationMessage>> {
    let mut stmt = db.prepare(
        "SELECT id, timestamp, role, content FROM conversations
         ORDER BY timestamp DESC LIMIT ?1"
    )?;
    let rows = stmt.query_map([limit], |row| {
        Ok(ConversationMessage {
            id: row.get(0)?,
            timestamp: row.get(1)?,
            role: row.get(2)?,
            content: row.get(3)?,
        })
    })?;

    let mut messages = Vec::new();
    for msg in rows {
        messages.push(msg?);
    }
    messages.reverse(); // oldest first
    Ok(messages)
}

/// Search conversation content with a simple LIKE query.
///
/// > **Note:** This is a placeholder full-text search. For production,
/// > consider migrating to SQLite FTS5 or a vector search backend.
pub fn search_conversations(db: &Connection, query: &str, limit: usize) -> Result<Vec<ConversationMessage>> {
    let pattern = format!("%{}%", query);
    let mut stmt = db.prepare(
        "SELECT id, timestamp, role, content FROM conversations
         WHERE content LIKE ?1
         ORDER BY timestamp DESC LIMIT ?2"
    )?;
    let rows = stmt.query_map([&pattern, &limit.to_string()], |row| {
        Ok(ConversationMessage {
            id: row.get(0)?,
            timestamp: row.get(1)?,
            role: row.get(2)?,
            content: row.get(3)?,
        })
    })?;

    let mut messages = Vec::new();
    for msg in rows {
        messages.push(msg?);
    }
    Ok(messages)
}

// ---------------------------------------------------------------------------
// Code events
// ---------------------------------------------------------------------------

/// Record a code change event (create, modify, delete, refactor).
pub fn record_code_event(db: &Connection, event: &CodeEvent) -> Result<()> {
    db.execute(
        "INSERT OR REPLACE INTO code_events (id, timestamp, file_path, change_type, diff, summary)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        params![
            &event.id,
            event.timestamp,
            &event.file_path,
            &event.change_type,
            &event.diff,
            &event.summary
        ],
    )?;
    Ok(())
}

/// Retrieve the most recent code events.
pub fn get_recent_code_events(db: &Connection, limit: usize) -> Result<Vec<CodeEvent>> {
    let mut stmt = db.prepare(
        "SELECT id, timestamp, file_path, change_type, diff, summary
         FROM code_events
         ORDER BY timestamp DESC LIMIT ?1"
    )?;
    let rows = stmt.query_map([limit], |row| {
        Ok(CodeEvent {
            id: row.get(0)?,
            timestamp: row.get(1)?,
            file_path: row.get(2)?,
            change_type: row.get(3)?,
            diff: row.get(4)?,
            summary: row.get(5)?,
        })
    })?;

    let mut events = Vec::new();
    for ev in rows {
        events.push(ev?);
    }
    events.reverse(); // oldest first
    Ok(events)
}

// ---------------------------------------------------------------------------
// Preferences
// ---------------------------------------------------------------------------

/// Store or update a user preference.
pub fn store_preference(db: &Connection, key: &str, value: &str, confidence: f64) -> Result<()> {
    let now = Utc::now().timestamp();
    db.execute(
        "INSERT INTO user_preferences (key, value, confidence, last_updated)
         VALUES (?1, ?2, ?3, ?4)
         ON CONFLICT(key) DO UPDATE SET
             value = excluded.value,
             confidence = excluded.confidence,
             last_updated = excluded.last_updated",
        params![key, value, confidence, now],
    )?;
    Ok(())
}

/// Retrieve all stored preferences ordered by confidence (highest first).
pub fn get_preferences(db: &Connection) -> Result<Vec<Preference>> {
    let mut stmt = db.prepare(
        "SELECT key, value, confidence, last_updated
         FROM user_preferences
         ORDER BY confidence DESC, last_updated DESC"
    )?;
    let rows = stmt.query_map([], |row| {
        Ok(Preference {
            key: row.get(0)?,
            value: row.get(1)?,
            confidence: row.get(2)?,
            last_updated: row.get(3)?,
        })
    })?;

    let mut prefs = Vec::new();
    for p in rows {
        prefs.push(p?);
    }
    Ok(prefs)
}

// ---------------------------------------------------------------------------
// Project state
// ---------------------------------------------------------------------------

/// Load the project state for a given project path.
pub fn get_project_state(db: &Connection, path: &str) -> Result<ProjectState> {
    let mut stmt = db.prepare(
        "SELECT project_path, current_branch, last_commit, agent_context_json
         FROM project_state WHERE project_path = ?1"
    )?;
    let state = stmt.query_row([path], |row| {
        Ok(ProjectState {
            project_path: row.get(0)?,
            current_branch: row.get(1)?,
            last_commit: row.get(2)?,
            agent_context_json: row.get(3)?,
        })
    });

    // Return a default state if no row exists yet.
    match state {
        Ok(s) => Ok(s),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(ProjectState {
            project_path: path.to_string(),
            current_branch: String::new(),
            last_commit: String::new(),
            agent_context_json: "{}".to_string(),
        }),
        Err(e) => Err(e),
    }
}

/// Upsert a project state snapshot.
pub fn update_project_state(db: &Connection, state: &ProjectState) -> Result<()> {
    let now = Utc::now().timestamp();
    db.execute(
        "INSERT INTO project_state (project_path, current_branch, last_commit, agent_context_json, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5)
         ON CONFLICT(project_path) DO UPDATE SET
             current_branch = excluded.current_branch,
             last_commit = excluded.last_commit,
             agent_context_json = excluded.agent_context_json,
             updated_at = excluded.updated_at",
        params![
            &state.project_path,
            &state.current_branch,
            &state.last_commit,
            &state.agent_context_json,
            now
        ],
    )?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Unified recall (context assembly)
// ---------------------------------------------------------------------------

/// Combine conversations and code events into a single context stream.
///
/// Results are ordered by timestamp descending (newest first).  The `relevance`
/// field is currently a placeholder (`0.0`) and will be replaced with actual
/// vector-similarity scores once an embedding backend is integrated.
pub fn recall_context(db: &Connection, search_text: &str, limit: usize) -> Result<Vec<ContextItem>> {
    let pattern = format!("%{}%", search_text);

    // -- matching conversations -----------------------------------------------
    let mut stmt = db.prepare(
        "SELECT id, content, timestamp FROM conversations
         WHERE content LIKE ?1
         ORDER BY timestamp DESC LIMIT ?2"
    )?;
    let conv_rows = stmt.query_map([&pattern, &limit.to_string()], |row| {
        Ok(ContextItem {
            id: row.get(0)?,
            source: "conversation".to_string(),
            content: row.get(1)?,
            relevance: 0.0,
            timestamp: row.get(2)?,
        })
    })?;

    let mut items: Vec<ContextItem> = conv_rows.filter_map(|r| r.ok()).collect();

    // -- matching code events -------------------------------------------------
    let mut stmt = db.prepare(
        "SELECT id, summary || ' | ' || file_path, timestamp FROM code_events
         WHERE summary LIKE ?1 OR file_path LIKE ?1
         ORDER BY timestamp DESC LIMIT ?2"
    )?;
    let code_rows = stmt.query_map([&pattern, &limit.to_string()], |row| {
        Ok(ContextItem {
            id: row.get(0)?,
            source: "code_event".to_string(),
            content: row.get(1)?,
            relevance: 0.0,
            timestamp: row.get(2)?,
        })
    })?;

    items.extend(code_rows.filter_map(|r| r.ok()));

    // Sort combined list by timestamp descending and cap at `limit`.
    items.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
    items.truncate(limit);
    Ok(items)
}

// ---------------------------------------------------------------------------
// Maintenance
// ---------------------------------------------------------------------------

/// Run periodic database maintenance (VACUUM + WAL checkpoint).
///
/// Call this on a background thread every few hours or on app idle.
/// Returns the number of freed pages, or `0` if no work was needed.
pub fn vacuum_db(db: &Connection) -> Result<usize> {
    // Checkpoint WAL before vacuuming so the main DB file is up-to-date.
    db.execute_batch("PRAGMA wal_checkpoint(TRUNCATE);")?;

    // Incremental vacuum frees pages on the freelist.
    db.execute("PRAGMA incremental_vacuum;", [])?;

    // Full VACUUM rebuilds the database file (expensive — best done
    // during idle time or on app exit).
    // db.execute_batch("VACUUM;")?;

    let freed: usize = db.query_row(
        "PRAGMA freelist_count",
        [],
        |row| row.get(0),
    )?;

    Ok(freed)
}
