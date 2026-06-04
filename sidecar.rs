//! Python backend sidecar management.
//!
//! Spawns the bundled Python FastAPI backend as a child process,
//! monitors its health, and provides the backend URL to commands.

use std::sync::Arc;
use parking_lot::Mutex;
use tauri::{AppHandle, Emitter, Manager};

/// Shared state for the backend sidecar.
#[derive(Debug)]
pub struct BackendState {
    /// The port the backend is listening on.
    pub port: u16,
    /// Whether the backend is confirmed healthy.
    pub healthy: bool,
    /// Number of restart attempts (for crash recovery).
    pub restart_count: u32,
}

impl BackendState {
    pub fn new(port: u16) -> Self {
        Self {
            port,
            healthy: false,
            restart_count: 0,
        }
    }

    /// Return the backend base URL.
    pub fn url(&self) -> String {
        format!("http://127.0.0.1:{}", self.port)
    }
}

/// Find an available TCP port on localhost.
pub fn find_open_port() -> u16 {
    std::net::TcpListener::bind("127.0.0.1:0")
        .expect("Failed to bind to find open port")
        .local_addr()
        .expect("Failed to get local address")
        .port()
}

/// Spawn the Python backend sidecar and monitor it.
///
/// This function should be called from the Tauri `.setup()` closure.
/// It spawns the sidecar, waits for it to become healthy, and sets
/// up an async monitoring task.
pub fn spawn_backend(app: &AppHandle) -> Result<u16, String> {
    let port = find_open_port();

    // Get app data directory for backend persistence
    let app_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to get app data dir: {}", e))?;
    std::fs::create_dir_all(&app_dir).map_err(|e| format!("Failed to create app dir: {}", e))?;

    // Prepare environment variables for the sidecar
    let data_dir_str = app_dir.to_string_lossy().to_string();

    // Spawn the sidecar using tauri-plugin-shell
    let sidecar = app
        .shell()
        .sidecar("agent-backend")
        .map_err(|e| format!("Failed to create sidecar command: {}. Is the binary in src/main/bin/?", e))?;

    let (mut rx, _child) = sidecar
        .env("CONSTRUCT_PORT", port.to_string())
        .env("CONSTRUCT_DATA_DIR", &data_dir_str)
        .env("CONSTRUCT_LOG_LEVEL", "info")
        .spawn()
        .map_err(|e| format!("Failed to spawn backend sidecar: {}. Check that the binary exists.", e))?;

    // Store backend state
    let backend_state = Arc::new(Mutex::new(BackendState::new(port)));
    app.manage(backend_state.clone());

    // Monitor sidecar output in async task
    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                tauri_plugin_shell::process::ShellEvent::Stdout(line) => {
                    let line = String::from_utf8_lossy(&line);
                    log::info!("[backend] {}", line.trim());
                    // Check if backend reports it's ready
                    if line.contains("Application startup complete") || line.contains("Uvicorn running") {
                        let mut state = backend_state.lock();
                        state.healthy = true;
                        let _ = app_handle.emit("backend:ready", state.port);
                    }
                }
                tauri_plugin_shell::process::ShellEvent::Stderr(line) => {
                    let line = String::from_utf8_lossy(&line);
                    log::warn!("[backend stderr] {}", line.trim());
                }
                tauri_plugin_shell::process::ShellEvent::Error(e) => {
                    log::error!("Backend sidecar error: {}", e);
                    let mut state = backend_state.lock();
                    state.healthy = false;
                }
                tauri_plugin_shell::process::ShellEvent::Terminated(payload) => {
                    log::error!("Backend sidecar terminated: code={:?}, signal={:?}", payload.code, payload.signal);
                    let mut state = backend_state.lock();
                    state.healthy = false;
                }
                _ => {}
            }
        }
    });

    Ok(port)
}

/// Wait for the backend to become ready (health check).
///
/// Polls the /health endpoint until it responds or timeout is reached.
pub async fn wait_for_backend(port: u16, timeout_secs: u64) -> Result<(), String> {
    let client = reqwest::Client::new();
    let url = format!("http://127.0.0.1:{}/health", port);

    for i in 0..timeout_secs {
        match client.get(&url).timeout(std::time::Duration::from_secs(2)).send().await {
            Ok(resp) if resp.status().is_success() => {
                log::info!("Backend healthy on port {} (after {}s)", port, i);
                return Ok(());
            }
            _ => {
                tokio::time::sleep(std::time::Duration::from_secs(1)).await;
            }
        }
    }

    Err(format!("Backend failed to become healthy on port {} within {}s", port, timeout_secs))
}
