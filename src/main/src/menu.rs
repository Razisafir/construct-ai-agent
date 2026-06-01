//! Native application menu for Construct IDE.
//!
//! Uses Tauri's built-in menu system to create OS-native menus
//! (File, Edit, View, Agent, Help) with keyboard shortcuts that
//! work through the native menu system, not just React key handlers.

use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem, Submenu},
    AppHandle, Manager, Runtime,
};

pub fn create_app_menu<R: Runtime>(app: &AppHandle<R>) -> Menu<R> {
    let menu = Menu::new(app);

    // ── File menu ──────────────────────────────────────────────
    let new_file = MenuItem::with_id(app, "new_file", "New File", true, Some("CmdOrCtrl+N"));
    let open_file = MenuItem::with_id(app, "open_file", "Open File...", true, Some("CmdOrCtrl+O"));
    let open_folder = MenuItem::with_id(app, "open_folder", "Open Folder...", true, Some("CmdOrCtrl+K"));
    let sep1 = PredefinedMenuItem::separator(app);
    let save = MenuItem::with_id(app, "save", "Save", true, Some("CmdOrCtrl+S"));
    let save_all = MenuItem::with_id(app, "save_all", "Save All", true, Some("CmdOrCtrl+Shift+S"));
    let sep2 = PredefinedMenuItem::separator(app);
    let quit = PredefinedMenuItem::quit(app, None);

    let file_menu = Submenu::with_items(
        app,
        "File",
        true,
        &[
            &new_file,
            &open_file,
            &open_folder,
            &sep1,
            &save,
            &save_all,
            &sep2,
            &quit,
        ],
    )
    .expect("failed to create File menu");

    // ── Edit menu ──────────────────────────────────────────────
    let undo = PredefinedMenuItem::undo(app, None);
    let redo = PredefinedMenuItem::redo(app, None);
    let sep3 = PredefinedMenuItem::separator(app);
    let cut = PredefinedMenuItem::cut(app, None);
    let copy = PredefinedMenuItem::copy(app, None);
    let paste = PredefinedMenuItem::paste(app, None);

    let edit_menu = Submenu::with_items(
        app,
        "Edit",
        true,
        &[&undo, &redo, &sep3, &cut, &copy, &paste],
    )
    .expect("failed to create Edit menu");

    // ── View menu ──────────────────────────────────────────────
    let command_palette = MenuItem::with_id(
        app,
        "command_palette",
        "Command Palette...",
        true,
        Some("CmdOrCtrl+Shift+P"),
    );
    let sep4 = PredefinedMenuItem::separator(app);
    let explorer = MenuItem::with_id(app, "explorer", "Explorer", true, Some("CmdOrCtrl+Shift+E"));
    let search = MenuItem::with_id(app, "search", "Search", true, Some("CmdOrCtrl+Shift+F"));
    let toggle_sidebar = MenuItem::with_id(
        app,
        "toggle_sidebar",
        "Toggle Sidebar",
        true,
        Some("CmdOrCtrl+B"),
    );
    let toggle_right_sidebar = MenuItem::with_id(
        app,
        "toggle_right_sidebar",
        "Toggle Right Sidebar",
        true,
        Some("CmdOrCtrl+Shift+B"),
    );
    let toggle_panel = MenuItem::with_id(
        app,
        "toggle_panel",
        "Toggle Bottom Panel",
        true,
        Some("CmdOrCtrl+`"),
    );

    let view_menu = Submenu::with_items(
        app,
        "View",
        true,
        &[
            &command_palette,
            &sep4,
            &explorer,
            &search,
            &toggle_sidebar,
            &toggle_right_sidebar,
            &toggle_panel,
        ],
    )
    .expect("failed to create View menu");

    // ── Agent menu (Construct-specific) ────────────────────────
    let new_chat = MenuItem::with_id(
        app,
        "new_chat",
        "New Chat",
        true,
        Some("CmdOrCtrl+Shift+L"),
    );
    let memory_browser = MenuItem::with_id(app, "memory_browser", "Memory Browser", true, None);
    let agent_dashboard = MenuItem::with_id(app, "agent_dashboard", "Agent Dashboard", true, None);
    let sep5 = PredefinedMenuItem::separator(app);
    let new_terminal = MenuItem::with_id(app, "new_terminal", "New Terminal", true, None);

    let agent_menu = Submenu::with_items(
        app,
        "Agent",
        true,
        &[
            &new_chat,
            &memory_browser,
            &agent_dashboard,
            &sep5,
            &new_terminal,
        ],
    )
    .expect("failed to create Agent menu");

    // ── Help menu ──────────────────────────────────────────────
    let documentation = MenuItem::with_id(app, "documentation", "Documentation", true, None);
    let keyboard_shortcuts = MenuItem::with_id(
        app,
        "keyboard_shortcuts",
        "Keyboard Shortcuts",
        true,
        Some("CmdOrCtrl+K CmdOrCtrl+S"),
    );
    let sep6 = PredefinedMenuItem::separator(app);
    let about = MenuItem::with_id(app, "about", "About Construct", true, None);

    let help_menu = Submenu::with_items(
        app,
        "Help",
        true,
        &[&documentation, &keyboard_shortcuts, &sep6, &about],
    )
    .expect("failed to create Help menu");

    // ── Assemble menu bar ──────────────────────────────────────
    menu.append(&file_menu)
        .and_then(|_| menu.append(&edit_menu))
        .and_then(|_| menu.append(&view_menu))
        .and_then(|_| menu.append(&agent_menu))
        .and_then(|_| menu.append(&help_menu))
        .expect("failed to build menu bar");

    menu
}
