import { Editor as MonacoEditor, loader } from "@monaco-editor/react";
import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import TabBar, { type EditorTab } from "./TabBar";

loader.config({
  paths: {
    vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.0/min/vs",
  },
});

/* ─────────────────────── custom monaco theme ─────────────────────── */

const CONSTRUCT_THEME_ID = "construct-dark";

const CONSTRUCT_THEME = {
  base: "vs-dark" as const,
  inherit: true,
  rules: [
    { token: "comment", foreground: "849495", fontStyle: "italic" },
    { token: "keyword", foreground: "c678dd" },
    { token: "keyword.control", foreground: "c678dd" },
    { token: "string", foreground: "98c379" },
    { token: "string.escape", foreground: "e5c07b" },
    { token: "number", foreground: "d19a66" },
    { token: "type", foreground: "e5c07b" },
    { token: "type.identifier", foreground: "e5c07b" },
    { token: "function", foreground: "61afef" },
    { token: "variable", foreground: "e2e2e6" },
    { token: "variable.predefined", foreground: "e5c07b" },
    { token: "operator", foreground: "c678dd" },
    { token: "delimiter", foreground: "849495" },
    { token: "tag", foreground: "e06c75" },
    { token: "attribute.name", foreground: "d19a66" },
    { token: "attribute.value", foreground: "98c379" },
    { token: "meta.decorator", foreground: "61afef" },
    { token: "regexp", foreground: "98c379" },
  ],
  colors: {
    "editor.background": "#0c0e11",
    "editor.foreground": "#e2e2e6",
    "editor.lineHighlightBackground": "#1e2023",
    "editor.selectionBackground": "rgba(0, 245, 255, 0.15)",
    "editor.inactiveSelectionBackground": "rgba(0, 245, 255, 0.08)",
    "editorLineNumber.foreground": "#84949580",
    "editorLineNumber.activeForeground": "#849495",
    "editorLineNumber.background": "#0c0e11",
    "editorCursor.foreground": "#00f5ff",
    "editor.findMatchBackground": "rgba(0, 245, 255, 0.2)",
    "editor.findMatchHighlightBackground": "rgba(0, 245, 255, 0.08)",
    "editorIndentGuide.background": "#282a2d",
    "editorIndentGuide.activeBackground": "#3a494a",
    "editorBracketMatch.background": "rgba(0, 245, 255, 0.1)",
    "editorBracketMatch.border": "rgba(0, 245, 255, 0.3)",
    "editorOverviewRuler.border": "#0c0e11",
    "editorGutter.background": "#0c0e11",
    "editorGutter.border": "#282a2d",
    "scrollbarSlider.background": "#282a2d80",
    "scrollbarSlider.hoverBackground": "#3a494a",
    "scrollbarSlider.activeBackground": "#3a494a",
    "editorWidget.background": "#141619",
    "editorWidget.border": "#282a2d",
    "editorSuggestWidget.background": "#141619",
    "editorSuggestWidget.border": "#282a2d",
    "editorSuggestWidget.selectedBackground": "#1e2023",
    "editorSuggestWidget.highlightForeground": "#00f5ff",
    "peekViewEditor.background": "#0c0e11",
    "peekViewResult.background": "#141619",
    "minimap.background": "#0c0e11",
  },
};

/* ─────────────────────── LSP & Completion Helpers ─────────────────────── */

const BACKEND_URL = "http://127.0.0.1:8000";

/** Languages that support LSP */
const LSP_LANGUAGES = ["typescript", "javascript", "typescriptreact", "javascriptreact", "python", "rust"];

/** Map Monaco language to file extension for display */
/** Map Monaco language to file extension for display */
// @ts-ignore: utility function for future use
function _getLanguageFromPath(filePath: string): string {
  const ext = filePath.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    ts: "typescript", tsx: "typescriptreact", js: "javascript", jsx: "javascriptreact",
    py: "python", rs: "rust", json: "json", md: "markdown", css: "css",
    html: "html", yaml: "yaml", yml: "yaml", toml: "toml",
  };
  return map[ext] ?? "plaintext";
}

/* ─────────────────────── default code ─────────────────────── */

const defaultCode = `import { useState } from "react";

interface Props {
  title: string;
  count?: number;
}

# Construct — autonomous API agent
# memory: SQLite + ChromaDB

from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from .memory import MemoryStore
from .agent import Agent

memory = MemoryStore(db_path="memories.db")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await memory.init()
    yield

    # agent writes proposed diffs here
    app.state.pending_diff = []

app = FastAPI(lifespan=lifespan)

@app.websocket("/ws/agent")
async def agent_stream(ws):
    await ws.accept()
    ctx = await memory.get_context()
`;

/* ─────────────────────── tab helpers ─────────────────────── */

let tabIdCounter = 0;

function createTab(
  fileName: string,
  filePath: string,
  language: string,
  content: string,
  isModified: boolean = false
): EditorTab {
  return {
    id: `tab-${++tabIdCounter}-${Date.now().toString(36)}`,
    fileName,
    filePath,
    language,
    content,
    isModified,
    isActive: false,
  };
}

/* ─────────────────────── main component ─────────────────────── */

function Editor() {
  const [tabs, setTabs] = useState<EditorTab[]>(() => [
    createTab("main.py", "src/main.py", "python", defaultCode, true),
    createTab("agent.py", "src/agent.py", "python", "# Agent component code\n", true),
    createTab("main.tsx", "src/main.tsx", "typescript", "// main entry point\n", false),
  ]);

  const themeDefined = useRef(false);

  // LSP WebSocket ref
  const lspWsRef = useRef<WebSocket | null>(null);
  // LSP connected state
  const [lspConnected, setLspConnected] = useState(false);
  const [lspLanguage, setLspLanguage] = useState<string | null>(null);
  // Inline completion debounce
  const completionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useState(() => {
    setTabs((prev) =>
      prev.map((t, i) => ({ ...t, isActive: i === 0 }))
    );
  });

  const activeTab = useMemo(
    () => tabs.find((t) => t.isActive) ?? tabs[0] ?? null,
    [tabs]
  );

  const activeTabId = activeTab?.id ?? null;

  const activateTab = useCallback((id: string) => {
    setTabs((prev) =>
      prev.map((t) => ({ ...t, isActive: t.id === id }))
    );
  }, []);

  const closeTab = useCallback((id: string) => {
    setTabs((prev) => {
      if (prev.length <= 1) {
        const onlyTab = prev[0];
        if (onlyTab) {
          return [{ ...onlyTab, isModified: false, isActive: true }];
        }
        return prev;
      }
      const idx = prev.findIndex((t) => t.id === id);
      const wasActive = prev[idx]?.isActive ?? false;
      const remaining = prev.filter((t) => t.id !== id);
      if (wasActive && remaining.length > 0) {
        const newIdx = Math.min(idx, remaining.length - 1);
        remaining[newIdx] = { ...remaining[newIdx], isActive: true };
      }
      return remaining;
    });
  }, []);

  const openTab = useCallback(
    (file: {
      fileName: string;
      filePath: string;
      language?: string;
      content?: string;
    }) => {
      setTabs((prev) => {
        const existing = prev.find((t) => t.filePath === file.filePath);
        if (existing) {
          return prev.map((t) => ({
            ...t,
            isActive: t.id === existing.id,
          }));
        }
        const newTab = createTab(
          file.fileName,
          file.filePath,
          file.language ?? "typescript",
          file.content ?? "",
          false
        );
        return [...prev.map((t) => ({ ...t, isActive: false })), { ...newTab, isActive: true }];
      });
    },
    []
  );

  const handleEditorChange = useCallback(
    (value: string | undefined) => {
      if (!activeTab) return;
      const newContent = value ?? "";
      setTabs((prev) =>
        prev.map((t) =>
          t.id === activeTab.id
            ? { ...t, content: newContent, isModified: true }
            : t
        )
      );
    },
    [activeTab]
  );

  const handleBeforeMount = useCallback((monaco: Parameters<NonNullable<import("@monaco-editor/react").EditorProps["beforeMount"]>>[0]) => {
    if (!themeDefined.current) {
      monaco.editor.defineTheme(CONSTRUCT_THEME_ID, CONSTRUCT_THEME);
      themeDefined.current = true;
    }
  }, []);

  const handleOnMount = useCallback((_editor: import("monaco-editor").editor.IStandaloneCodeEditor, monaco: typeof import("monaco-editor")) => {
    if (!themeDefined.current) {
      monaco.editor.defineTheme(CONSTRUCT_THEME_ID, CONSTRUCT_THEME);
      themeDefined.current = true;
    }
    monaco.editor.setTheme(CONSTRUCT_THEME_ID);

    // ─── Register Inline Completions Provider for AI ghost text ───
    const DEBOUNCE_MS = 300;

    LSP_LANGUAGES.forEach((lang) => {
      monaco.languages.registerInlineCompletionsProvider(lang, {
        provideInlineCompletions: async (model, position, _context, _token) => {
          const text = model.getValue();
          const offset = model.getOffsetAt(position);

          // Get context around cursor
          const lines = text.split("\n");
          const currentLine = position.lineNumber - 1;
          const startLine = Math.max(0, currentLine - 50);
          const contextLines = lines.slice(startLine, currentLine + 1);
          const prefix = contextLines.join("\n");

          // Debounce: only request after a pause in typing
          if (completionTimeoutRef.current) {
            clearTimeout(completionTimeoutRef.current);
          }

          await new Promise<void>((resolve) => {
            completionTimeoutRef.current = setTimeout(resolve, DEBOUNCE_MS);
          });

          try {
            const response = await fetch(`${BACKEND_URL}/completions/inline`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                prefix,
                suffix: text.slice(offset),
                language: lang,
                file_path: model.uri.path,
                line: position.lineNumber,
                column: position.column,
              }),
            });

            if (!response.ok) return { items: [] };

            const data = await response.json();
            if (!data.completion) return { items: [] };

            return {
              items: [{
                insertText: data.completion,
                range: new monaco.Range(
                  position.lineNumber,
                  position.column,
                  position.lineNumber,
                  position.column
                ),
                command: {
                  id: "construct.acceptCompletion",
                  title: "Accept AI Completion",
                  arguments: [data.completion_id, true],
                },
              }],
            };
          } catch {
            return { items: [] };
          }
        },
        freeInlineCompletions: () => {},
      });
    });

    // ─── Auto-start LSP for the current file's language ───
    const currentLang = activeTab?.language ?? "typescript";
    if (LSP_LANGUAGES.includes(currentLang)) {
      startLSP(currentLang);
    }
  }, [activeTab?.language]);

  // ─── LSP Connection Management ───
  const startLSP = useCallback(async (language: string) => {
    // Close existing WebSocket if switching languages
    if (lspWsRef.current) {
      lspWsRef.current.close();
      lspWsRef.current = null;
    }

    try {
      // First, start the LSP server via REST
      const startResp = await fetch(`${BACKEND_URL}/lsp/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language, project_path: "." }),
      });

      if (!startResp.ok) {
        setLspConnected(false);
        setLspLanguage(null);
        return;
      }

      const startData = await startResp.json();
      if (!startData.started) {
        console.warn(`[LSP] Server not started: ${startData.error}`);
        if (startData.install_hint) {
          console.info(`[LSP] Install with: ${startData.install_hint}`);
        }
        setLspConnected(false);
        setLspLanguage(null);
        return;
      }

      // Connect WebSocket for real-time communication
      const ws = new WebSocket(`ws://127.0.0.1:8000/lsp/${language}`);

      ws.onopen = () => {
        setLspConnected(true);
        setLspLanguage(language);
        console.info(`[LSP] Connected to ${language} language server`);
      };

      ws.onclose = () => {
        setLspConnected(false);
        setLspLanguage(null);
        console.info(`[LSP] Disconnected from ${language} server`);
      };

      ws.onerror = (err) => {
        console.error("[LSP] WebSocket error", err);
        setLspConnected(false);
      };

      lspWsRef.current = ws;
    } catch (err) {
      console.error("[LSP] Failed to start:", err);
      setLspConnected(false);
      setLspLanguage(null);
    }
  }, []);

  // Auto-start LSP when tab changes
  useEffect(() => {
    if (activeTab?.language && LSP_LANGUAGES.includes(activeTab.language)) {
      if (lspLanguage !== activeTab.language) {
        startLSP(activeTab.language);
      }
    }
    return () => {
      // Don't close on every re-render, only on unmount
    };
  }, [activeTab?.language, lspLanguage, startLSP]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (lspWsRef.current) {
        lspWsRef.current.close();
      }
      if (completionTimeoutRef.current) {
        clearTimeout(completionTimeoutRef.current);
      }
    };
  }, []);

  const monacoOptions = useMemo(
    () => ({
      fontSize: 13,
      fontFamily: "'JetBrains Mono', monospace",
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      automaticLayout: true,
      lineNumbers: "on" as const,
      renderLineHighlight: "line" as const,
      tabSize: 2,
      insertSpaces: true,
      wordWrap: "on" as const,
      folding: true,
      bracketPairColorization: { enabled: true },
      guides: {
        bracketPairs: true,
        indentation: true,
      },
      scrollbar: {
        useShadows: false,
        verticalScrollbarSize: 8,
        horizontalScrollbarSize: 8,
      },
      padding: { top: 8 },
      cursorStyle: "line" as const,
      cursorBlinking: "blink" as const,
      smoothScrolling: false,
      lineNumbersMinChars: 3,
      lineDecorationsWidth: 0,
    }),
    []
  );

  return (
    <div className="flex flex-col w-full h-full bg-bg-onyx font-mono">
      {/* ── Tab Bar ── */}
      <TabBar
        tabs={tabs}
        activeTabId={activeTabId}
        onActivate={activateTab}
        onClose={closeTab}
        onOpen={openTab}
      />

      {/* ── Breadcrumb Path ── */}
      <div className="flex items-center h-6 px-3 shrink-0 bg-bg-onyx border-b border-border-subtle">
        <span className="text-[10px] font-mono text-c-text4 tracking-wide whitespace-nowrap overflow-hidden text-ellipsis">
          {activeTab?.filePath ?? "no file open"}
        </span>
        {activeTab?.isModified && (
          <span className="ml-2 text-[9px] font-mono text-accent-cyan">
            ● modified
          </span>
        )}
        {/* LSP status indicator */}
        {lspConnected && lspLanguage && (
          <span className="ml-auto flex items-center gap-1 text-[9px] font-mono text-status-running">
            <span className="w-1.5 h-1.5 rounded-full bg-status-running" />
            {lspLanguage.toUpperCase()} LSP
          </span>
        )}
      </div>

      {/* ── Monaco Editor ── */}
      <div className="flex-1 min-h-0">
        <MonacoEditor
          key={activeTabId ?? "empty"}
          height="100%"
          language={activeTab?.language ?? "typescript"}
          theme={CONSTRUCT_THEME_ID}
          value={activeTab?.content ?? ""}
          onChange={handleEditorChange}
          beforeMount={handleBeforeMount}
          onMount={handleOnMount}
          options={monacoOptions}
          loading={
            <div className="flex items-center justify-center w-full h-full text-[11px] text-c-text4 font-mono">
              loading editor...
            </div>
          }
        />
      </div>
    </div>
  );
}

export default Editor;
