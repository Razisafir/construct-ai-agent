pub mod commands;
pub mod db;
pub mod sidecar;
pub mod state;
pub mod tray;

use commands::agent::AgentState;
use commands::autonomous::AutonomousManager;
use sidecar::{spawn_backend, wait_for_backend};
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // ── 1. Spawn Python backend sidecar ─────────────────────────────
            let port = match spawn_backend(app) {
                Ok(p) => {
                    log::info!("Backend sidecar spawned on port {}", p);
                    p
                }
                Err(e) => {
                    log::error!("Failed to spawn backend sidecar: {}. Agent functionality will not work.", e);
                    // Use default port so the app still opens (agent just won't work)
                    8000
                }
            };

            // ── 2. Wait for backend health check ────────────────────────────
            if port != 8000 {
                let app_handle = app.handle().clone();
                tauri::async_runtime::spawn(async move {
                    match wait_for_backend(port, 30).await {
                        Ok(()) => {
                            log::info!("Backend ready on port {}", port);
                            let _ = app_handle.emit("backend:ready", port);
                        }
                        Err(e) => {
                            log::error!("Backend health check failed: {}", e);
                            let _ = app_handle.emit("backend:error", e);
                        }
                    }
                });
            }

            // ── 3. Initialise SQLite database ───────────────────────────────
            let state = db::init_db(app).expect("failed to initialise database");
            app.manage(state);

            // ── 4. Agent state ──────────────────────────────────────────────
            app.manage(AgentState::new());

            // ── 5. Autonomous mode ──────────────────────────────────────────
            app.manage(AutonomousManager::new());

            // ── 6. System tray ──────────────────────────────────────────────
            let app_handle = app.handle();
            tray::setup_tray(&app_handle).expect("failed to set up system tray");

            #[cfg(debug_assertions)]
            {
                let window = app.get_webview_window("main").unwrap();
                window.open_devtools();
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // -- existing commands --
            greet,
            get_app_version,
            // -- memory commands --
            commands::memory::record_conversation,
            commands::memory::get_recent_conversations,
            commands::memory::record_code_event,
            commands::memory::get_recent_code_events,
            commands::memory::store_preference,
            commands::memory::get_preferences,
            commands::memory::get_project_state,
            commands::memory::update_project_state,
            commands::memory::recall_context,
            // -- agent commands --
            commands::agent::start_agent,
            commands::agent::get_agent_status,
            commands::agent::pause_agent,
            commands::agent::resume_agent,
            commands::agent::stop_agent,
            commands::agent::get_agent_output,
            // -- autonomous commands --
            commands::autonomous::enable_autonomous_mode,
            commands::autonomous::disable_autonomous_mode,
            commands::autonomous::get_autonomous_status,
            commands::autonomous::set_goal_deadline,
            commands::autonomous::get_agent_log,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

/// Simple greeting command for frontend-Rust communication testing.
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! Welcome to Construct.", name)
}

/// Returns the current application version from Cargo.toml.
#[tauri::command]
fn get_app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}
