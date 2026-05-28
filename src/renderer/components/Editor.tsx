import { Editor as MonacoEditor, loader } from "@monaco-editor/react";
import { useState, useCallback, useMemo } from "react";
import TabBar, { type EditorTab } from "./TabBar";

loader.config({
  paths: {
    vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.0/min/vs",
  },
});

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
  border: "rgba(255,255,255,0.04)",
};

const ff = '"Geist Mono", "JetBrains Mono", monospace';

const defaultCode = `import { useState } from "react";

interface Props {
  title: string;
  count?: number;
}

// agent: reviewing component structure for memoization opportunities
export default function Example({ title, count = 0 }: Props) {
  const [value, setValue] = useState(count);

  // mem: previous implementation used useCallback here - unnecessary for this case
  const handleIncrement = () => setValue((v) => v + 1);

  // agent-suggest: consider extracting this to a separate component
  return (
    <div className="p-4">
      <h1>{title}</h1>
      <p>Count: {value}</p>
      <button onClick={handleIncrement}>
        Increment
      </button>
    </div>
  );
}
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
  // ── tab state ──
  const [tabs, setTabs] = useState<EditorTab[]>(() => [
    createTab("App.tsx", "src/App.tsx", "typescript", defaultCode, true),
    createTab("Sidebar.tsx", "src/components/Sidebar.tsx", "typescript", "// Sidebar component code\n", true),
    createTab("main.tsx", "src/main.tsx", "typescript", "// main entry point\n", false),
  ]);

  // Activate first tab on mount
  useState(() => {
    setTabs((prev) =>
      prev.map((t, i) => ({ ...t, isActive: i === 0 }))
    );
  });

  // ── derived: active tab ──
  const activeTab = useMemo(
    () => tabs.find((t) => t.isActive) ?? tabs[0] ?? null,
    [tabs]
  );

  const activeTabId = activeTab?.id ?? null;

  // ── actions ──

  /** Activate a tab by its id */
  const activateTab = useCallback((id: string) => {
    setTabs((prev) =>
      prev.map((t) => ({ ...t, isActive: t.id === id }))
    );
  }, []);

  /** Close a tab by its id. If closing the active tab, activate the nearest neighbor. */
  const closeTab = useCallback((id: string) => {
    setTabs((prev) => {
      if (prev.length <= 1) {
        // Keep at least one tab
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

  /** Open a file as a tab. If already open, activate it. */
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

  // ── editor change handler ──
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

  // ── monaco options ──
  const monacoOptions = useMemo(
    () => ({
      fontSize: 12,
      fontFamily: "'Geist Mono', 'JetBrains Mono', monospace",
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
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: "100%",
        height: "100%",
        backgroundColor: C.base,
        fontFamily: ff,
      }}
    >
      {/* ── Tab Bar ── */}
      <TabBar
        tabs={tabs}
        activeTabId={activeTabId}
        onActivate={activateTab}
        onClose={closeTab}
        onOpen={openTab}
      />

      {/* ── Breadcrumb Path ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          height: 22,
          padding: "0 12px",
          backgroundColor: C.base,
          borderBottom: `1px solid ${C.border}`,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontFamily: ff,
            color: C.t4,
            letterSpacing: "0.02em",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {activeTab?.filePath ?? "no file open"}
        </span>
        {activeTab?.isModified && (
          <span
            style={{
              marginLeft: 8,
              fontSize: 9,
              color: C.accent,
              fontFamily: ff,
            }}
          >
            ● modified
          </span>
        )}
      </div>

      {/* ── Monaco Editor ── */}
      <div style={{ flex: 1, minHeight: 0 }}>
        <MonacoEditor
          key={activeTabId ?? "empty"}
          height="100%"
          language={activeTab?.language ?? "typescript"}
          theme="vs-dark"
          value={activeTab?.content ?? ""}
          onChange={handleEditorChange}
          options={monacoOptions}
          loading={
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "100%",
                height: "100%",
                fontSize: 11,
                color: C.t4,
                fontFamily: ff,
              }}
            >
              loading editor...
            </div>
          }
        />
      </div>
    </div>
  );
}

export default Editor;
