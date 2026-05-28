import { lazy, Suspense, useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import StatusBar from "./components/StatusBar";
import CommandPalette from "./components/CommandPalette";
import type { PaletteCommand } from "./components/CommandPalette";
import {
  useKeyboardShortcuts,
  createConstructShortcuts,
} from "./hooks/useKeyboardShortcuts";
import useAppStore from "./stores/useAppStore";

const Editor = lazy(() => import("./components/Editor"));
const Panel = lazy(() => import("./components/Panel"));

const C = {
  base: "#0c0c10",
  s1: "#12121a",
  border: "rgba(255,255,255,0.04)",
  t2: "#94949c",
  accent: "#6366f1",
};

function App() {
  const sidebarVisible = useAppStore((s) => s.sidebarVisible);
  const panelVisible = useAppStore((s) => s.panelVisible);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const togglePanel = useAppStore((s) => s.togglePanel);
  // ── Command Palette state ──
  const [showCommandPalette, setShowCommandPalette] = useState(false);

  const openCommandPalette = useCallback(() => {
    setShowCommandPalette(true);
  }, []);

  const closeCommandPalette = useCallback(() => {
    setShowCommandPalette(false);
  }, []);

  // ── Keyboard shortcuts ──
  const shortcuts = createConstructShortcuts({
    // File
    newFile: () => {
      console.log("[shortcut] new file");
    },
    openFile: () => {
      console.log("[shortcut] open file");
    },
    save: () => {
      console.log("[shortcut] save");
    },
    saveAll: () => {
      console.log("[shortcut] save all");
    },
    closeTab: () => {
      console.log("[shortcut] close tab");
    },

    // Edit
    undo: () => {
      console.log("[shortcut] undo");
    },
    redo: () => {
      console.log("[shortcut] redo");
    },
    find: () => {
      console.log("[shortcut] find");
    },
    replace: () => {
      console.log("[shortcut] replace");
    },
    goToLine: () => {
      console.log("[shortcut] go to line");
    },

    // View
    toggleSidebar: () => {
      toggleSidebar();
    },
    toggleAgentPanel: () => {
      console.log("[shortcut] toggle agent panel");
    },
    toggleMemoryPanel: () => {
      console.log("[shortcut] toggle memory panel");
    },
    toggleTerminal: () => {
      togglePanel();
    },
    fullscreen: () => {
      console.log("[shortcut] fullscreen");
    },

    // Agent / Action
    commandPalette: () => {
      openCommandPalette();
    },
    runCurrentFile: () => {
      console.log("[shortcut] run current file");
    },
  });

  useKeyboardShortcuts(shortcuts, true);

  // ── Command palette handler ──
  const handleCommandSelect = useCallback((cmd: PaletteCommand) => {
    console.log(`[command palette] selected: ${cmd.id} — ${cmd.label}`);

    // Wire up known commands
    switch (cmd.id) {
      case "toggle-sidebar":
        toggleSidebar();
        break;
      case "toggle-terminal":
        togglePanel();
        break;
      default:
        break;
    }
  }, [toggleSidebar, togglePanel]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: "100vw",
        height: "100vh",
        backgroundColor: C.base,
        fontFamily: '"Geist Mono", "JetBrains Mono", monospace',
        overflow: "hidden",
      }}
    >
      {/* Title Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          height: 28,
          padding: "0 12px",
          backgroundColor: C.s1,
          borderBottom: `1px solid ${C.border}`,
          flexShrink: 0,
          userSelect: "none",
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.08em",
            color: C.t2,
            textTransform: "uppercase" as const,
          }}
        >
          Construct
        </span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 10, color: "#6b6b73" }}>v0.1.0-alpha</span>
      </div>

      {/* Main Layout */}
      <div
        style={{
          display: "flex",
          flex: 1,
          minHeight: 0,
          overflow: "hidden",
        }}
      >
        {/* Sidebar */}
        {sidebarVisible && (
          <aside
            style={{
              width: 280,
              flexShrink: 0,
              display: "flex",
              borderRight: `1px solid ${C.border}`,
              overflow: "hidden",
            }}
          >
            <Sidebar />
          </aside>
        )}

        {/* Center - Editor + Panel */}
        <main
          style={{
            display: "flex",
            flexDirection: "column",
            flex: 1,
            minWidth: 0,
          }}
        >
          <div style={{ flex: 1, minHeight: 0 }}>
            <Suspense
              fallback={
                <div
                  style={{
                    width: "100%",
                    height: "100%",
                    padding: 16,
                    fontSize: 11,
                    color: "#6b6b73",
                  }}
                >
                  loading...
                </div>
              }
            >
              <Editor />
            </Suspense>
          </div>

          {/* Bottom Panel */}
          {panelVisible && (
            <div
              style={{
                height: 240,
                flexShrink: 0,
                borderTop: `1px solid ${C.border}`,
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <Suspense
                fallback={
                  <div
                    style={{
                      padding: 8,
                      fontSize: 10,
                      color: "#6b6b73",
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                    }}
                  >
                    loading panel...
                  </div>
                }
              >
                <Panel />
              </Suspense>
            </div>
          )}
        </main>
      </div>

      <StatusBar />

      {/* ── Command Palette ── */}
      <CommandPalette
        isOpen={showCommandPalette}
        onClose={closeCommandPalette}
        onCommandSelect={handleCommandSelect}
      />
    </div>
  );
}

export default App;
