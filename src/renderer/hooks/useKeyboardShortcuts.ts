import { useEffect, useCallback, useRef } from "react";

/* ─────────────────────── types ─────────────────────── */

interface ShortcutMap {
  [key: string]: () => void;
}

interface ParsedShortcut {
  key: string;
  ctrl: boolean;
  shift: boolean;
  alt: boolean;
  meta: boolean;
}

/* ─────────────────────── color system (for any UI feedback) ─────────────────────── */

const C = {
  base: "#0c0c10",
  s1: "#12121a",
  s2: "#1a1a24",
  s3: "#22222e",
  accent: "#6366f1",
  t1: "#e8e8ec",
  t2: "#94949c",
  t3: "#6b6b73",
  t4: "#4a4a52",
  ok: "#10b981",
  wrn: "#f59e0b",
  err: "#ef4444",
  inf: "#60a5fa",
};

const ff = '"Geist Mono", "JetBrains Mono", monospace';

/* ─────────────────────── key parsing ─────────────────────── */

/**
 * Parse a shortcut string like "ctrl+shift+p" or "f5" into
 * a structured object for comparison against KeyboardEvents.
 */
function parseShortcut(shortcut: string): ParsedShortcut {
  const parts = shortcut.toLowerCase().split("+");
  return {
    key: parts.filter(
      (p) => !["ctrl", "shift", "alt", "meta"].includes(p)
    ).join("+"),
    ctrl: parts.includes("ctrl"),
    shift: parts.includes("shift"),
    alt: parts.includes("alt"),
    meta: parts.includes("meta"),
  };
}

/**
 * Normalize a KeyboardEvent into a comparable key string.
 * Handles special keys and normalizes case.
 */
function getEventKey(e: KeyboardEvent): string {
  const key = e.key.toLowerCase();
  // Map common variations
  if (key === " ") return "space";
  if (key === "escape") return "esc";
  if (key === "arrowup") return "up";
  if (key === "arrowdown") return "down";
  if (key === "arrowleft") return "left";
  if (key === "arrowright") return "right";
  if (key === "delete") return "del";
  if (key === "insert") return "ins";
  if (key === "contextmenu") return "menu";
  if (key === "super") return "meta";
  return key;
}

/**
 * Check if a KeyboardEvent matches a parsed shortcut.
 */
function matchShortcut(e: KeyboardEvent, parsed: ParsedShortcut): boolean {
  const eventKey = getEventKey(e);

  // For single-key shortcuts (no modifiers required in combo), just match the key
  if (!parsed.ctrl && !parsed.shift && !parsed.alt && !parsed.meta) {
    return eventKey === parsed.key;
  }

  // For modifier combos, all specified modifiers must match exactly
  const ctrlOk = parsed.ctrl === e.ctrlKey;
  const shiftOk = parsed.shift === e.shiftKey;
  const altOk = parsed.alt === e.altKey;
  const metaOk = parsed.meta === e.metaKey;

  return ctrlOk && shiftOk && altOk && metaOk && eventKey === parsed.key;
}

/* ─────────────────────── hook ─────────────────────── */

/**
 * useKeyboardShortcuts — register keyboard shortcuts at the window level.
 *
 * @param shortcuts  Map of "key+combo" strings to callback functions.
 *                   Examples: "ctrl+s", "ctrl+shift+p", "f5", "esc"
 * @param enabled    Whether the shortcuts are active (default: true).
 *
 * Usage:
 *   useKeyboardShortcuts({
 *     "ctrl+s": () => saveFile(),
 *     "ctrl+shift+p": () => openPalette(),
 *     "f5": () => runCode(),
 *   }, true);
 */
export function useKeyboardShortcuts(
  shortcuts: ShortcutMap,
  enabled: boolean = true
) {
  // Parse shortcuts once on mount / change
  const parsedRef = useRef<Map<string, ParsedShortcut>>(new Map());
  const handlersRef = useRef<ShortcutMap>({});

  // Keep refs in sync
  useEffect(() => {
    const parsed = new Map<string, ParsedShortcut>();
    Object.keys(shortcuts).forEach((raw) => {
      parsed.set(raw, parseShortcut(raw));
    });
    parsedRef.current = parsed;
    handlersRef.current = shortcuts;
  }, [shortcuts]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!enabled) return;

    // Skip if user is typing in an input/textarea
    const target = e.target as HTMLElement | null;
    if (target) {
      const tag = target.tagName.toLowerCase();
      const isEditable =
        tag === "input" ||
        tag === "textarea" ||
        tag === "select" ||
        target.isContentEditable;

      // Allow shortcuts in editable fields only if Ctrl/Cmd is held
      // (prevents intercepting normal typing)
      if (isEditable && !e.ctrlKey && !e.metaKey) {
        // Still allow Escape and F-keys in inputs
        if (!e.key.startsWith("F") && e.key !== "Escape") {
          return;
        }
      }
    }

    // Try each registered shortcut
    for (const [rawCombo, parsed] of parsedRef.current.entries()) {
      if (matchShortcut(e, parsed)) {
        const handler = handlersRef.current[rawCombo];
        if (handler) {
          e.preventDefault();
          e.stopPropagation();
          try {
            handler();
          } catch (err) {
            console.error(`[useKeyboardShortcuts] Error in "${rawCombo}" handler:`, err);
          }
          return;
        }
      }
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;

    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => {
      window.removeEventListener("keydown", handleKeyDown, { capture: true });
    };
  }, [enabled, handleKeyDown]);
}

/* ─────────────────────── predefined shortcuts for Construct ─────────────────────── */

/**
 * Default keyboard shortcuts for the Construct editor.
 * These are factory functions that accept action implementations,
 * so the hook stays pure and the caller wires up actual behavior.
 */
export const DEFAULT_SHORTCUTS = {
  // File
  newFile: "ctrl+n",
  openFile: "ctrl+o",
  save: "ctrl+s",
  saveAll: "ctrl+shift+s",
  closeTab: "ctrl+w",

  // Edit
  undo: "ctrl+z",
  redo: "ctrl+y",
  find: "ctrl+f",
  replace: "ctrl+h",
  goToLine: "ctrl+g",

  // View
  toggleSidebar: "ctrl+b",
  toggleAgentPanel: "ctrl+shift+a",
  toggleMemoryPanel: "ctrl+shift+m",
  toggleTerminal: "ctrl+shift+t",
  fullscreen: "f11",

  // Agent / Action
  commandPalette: "ctrl+shift+p",
  runCurrentFile: "f5",
} as const;

/**
 * Create a fully wired shortcut map for Construct.
 * Each action receives a no-op default so the map is always valid.
 */
export function createConstructShortcuts(
  actions: Partial<Record<keyof typeof DEFAULT_SHORTCUTS, () => void>>
): ShortcutMap {
  const noOp = () => {};

  return {
    [DEFAULT_SHORTCUTS.newFile]: actions.newFile ?? noOp,
    [DEFAULT_SHORTCUTS.openFile]: actions.openFile ?? noOp,
    [DEFAULT_SHORTCUTS.save]: actions.save ?? noOp,
    [DEFAULT_SHORTCUTS.saveAll]: actions.saveAll ?? noOp,
    [DEFAULT_SHORTCUTS.closeTab]: actions.closeTab ?? noOp,
    [DEFAULT_SHORTCUTS.undo]: actions.undo ?? noOp,
    [DEFAULT_SHORTCUTS.redo]: actions.redo ?? noOp,
    [DEFAULT_SHORTCUTS.find]: actions.find ?? noOp,
    [DEFAULT_SHORTCUTS.replace]: actions.replace ?? noOp,
    [DEFAULT_SHORTCUTS.goToLine]: actions.goToLine ?? noOp,
    [DEFAULT_SHORTCUTS.toggleSidebar]: actions.toggleSidebar ?? noOp,
    [DEFAULT_SHORTCUTS.toggleAgentPanel]: actions.toggleAgentPanel ?? noOp,
    [DEFAULT_SHORTCUTS.toggleMemoryPanel]: actions.toggleMemoryPanel ?? noOp,
    [DEFAULT_SHORTCUTS.toggleTerminal]: actions.toggleTerminal ?? noOp,
    [DEFAULT_SHORTCUTS.fullscreen]: actions.fullscreen ?? noOp,
    [DEFAULT_SHORTCUTS.commandPalette]: actions.commandPalette ?? noOp,
    [DEFAULT_SHORTCUTS.runCurrentFile]: actions.runCurrentFile ?? noOp,
  };
}

export type { ShortcutMap, ParsedShortcut };
export { C, ff };
