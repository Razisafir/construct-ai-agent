/**
 * Native OS file dialogs via Tauri plugin-dialog.
 *
 * Falls back to console.log when not running inside Tauri
 * (e.g. during web preview or Vite dev server without Tauri).
 */

let dialogModule: any = null;

async function getDialog() {
  if (dialogModule !== null) return dialogModule;
  try {
    // Dynamic import so it doesn't crash in pure web mode
    dialogModule = await import("@tauri-apps/plugin-dialog");
  } catch {
    dialogModule = null;
  }
  return dialogModule;
}

function isTauri(): boolean {
  return typeof window !== "undefined" && !!(window as any).__TAURI__;
}

/**
 * Open a native folder-picker dialog.
 * Returns the selected folder path, or null if cancelled.
 */
export async function openFolderDialog(): Promise<string | null> {
  if (!isTauri()) {
    console.log("[nativeDialogs] openFolderDialog — not in Tauri, skipping");
    return null;
  }

  const dialog = await getDialog();
  if (!dialog) return null;

  try {
    const selected = await dialog.open({
      directory: true,
      multiple: false,
      title: "Open Project Folder",
    });
    return selected as string | null;
  } catch (err) {
    console.warn("[nativeDialogs] openFolderDialog failed:", err);
    return null;
  }
}

/**
 * Open a native file-picker dialog.
 * Returns the selected file path, or null if cancelled.
 */
export async function openFileDialog(): Promise<string | null> {
  if (!isTauri()) {
    console.log("[nativeDialogs] openFileDialog — not in Tauri, skipping");
    return null;
  }

  const dialog = await getDialog();
  if (!dialog) return null;

  try {
    const selected = await dialog.open({
      directory: false,
      multiple: false,
      filters: [
        { name: "All Files", extensions: ["*"] },
        { name: "Python", extensions: ["py"] },
        { name: "TypeScript", extensions: ["ts", "tsx"] },
        { name: "JavaScript", extensions: ["js", "jsx"] },
        { name: "Rust", extensions: ["rs"] },
      ],
      title: "Open File",
    });
    return selected as string | null;
  } catch (err) {
    console.warn("[nativeDialogs] openFileDialog failed:", err);
    return null;
  }
}

/**
 * Open a native save-file dialog.
 * Returns the chosen save path, or null if cancelled.
 */
export async function saveFileDialog(defaultName?: string): Promise<string | null> {
  if (!isTauri()) {
    console.log("[nativeDialogs] saveFileDialog — not in Tauri, skipping");
    return null;
  }

  const dialog = await getDialog();
  if (!dialog) return null;

  try {
    const selected = await dialog.save({
      defaultPath: defaultName,
      filters: [{ name: "All Files", extensions: ["*"] }],
      title: "Save File",
    });
    return selected;
  } catch (err) {
    console.warn("[nativeDialogs] saveFileDialog failed:", err);
    return null;
  }
}
