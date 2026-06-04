//! Terminal PTY module — STUBBED for CI compatibility.
//!
//! The real PTY implementation using portable-pty is disabled until
//! CI build issues are resolved. This stub provides the same Tauri
//! command interface so the frontend doesn't break, but returns
//! errors indicating the feature is not yet available.
//!
//! To re-enable:
//!   1. Add `portable-pty = "0.9"` to Cargo.toml
//!   2. Add `libudev-dev` to CI workflow system deps
//!   3. Replace this file with the real implementation
//!   4. Uncomment terminal commands in lib.rs invoke_handler

use std::sync::Arc;
use tokio::sync::Mutex;
use tauri::{AppHandle, Emitter};

/// Managed state: one terminal session per app (stubbed).
pub struct TerminalState {
    pub session: Arc<Mutex<Option<String>>>,
}

impl TerminalState {
    pub fn new() -> Self {
        Self {
            session: Arc::new(Mutex::new(None)),
        }
    }
}

/// Spawn a new PTY shell — STUBBED.
///
/// Returns an error explaining the terminal is not yet available.
/// The frontend should display a "Coming soon" message.
#[tauri::command]
pub async fn spawn_terminal(
    app: AppHandle,
    cols: u16,
    rows: u16,
) -> Result<String, String> {
    log::warn!(
        "Terminal PTY not available (stubbed). Requested {}x{}",
        cols, rows
    );
    let _ = app.emit("terminal:data", "\r\n\x1b[33mTerminal is coming soon — PTY backend is being configured.\x1b[0m\r\n");
    Err("Terminal PTY is not yet available. This feature will be re-enabled in a future update.".to_string())
}

/// Send input from the frontend to the shell — STUBBED.
#[tauri::command]
pub async fn terminal_input(
    _app: AppHandle,
    _data: String,
) -> Result<(), String> {
    Err("Terminal PTY is not yet available.".to_string())
}

/// Resize the terminal viewport — STUBBED.
#[tauri::command]
pub async fn terminal_resize(
    _app: AppHandle,
    _cols: u16,
    _rows: u16,
) -> Result<(), String> {
    Err("Terminal PTY is not yet available.".to_string())
}

/// Kill the terminal session — STUBBED.
#[tauri::command]
pub async fn kill_terminal(_app: AppHandle) -> Result<(), String> {
    Err("Terminal PTY is not yet available.".to_string())
}
