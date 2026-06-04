import { useState } from "react";
import useAppStore from "../stores/useAppStore";
import MCPConnector from "./MCPConnector";

interface FileNode {
  name: string;
  type: "file" | "folder";
  indent: number;
  expanded?: boolean;
  status?: "M" | "A" | "D";
  fileType?: string;
}

const fileTree: FileNode[] = [
  { name: "src", type: "folder", indent: 0, expanded: true },
  { name: "components", type: "folder", indent: 1, expanded: true },
  { name: "Sidebar.tsx", type: "file", indent: 2, status: "M", fileType: "tsx" },
  { name: "Editor.tsx", type: "file", indent: 2, status: "A", fileType: "tsx" },
  { name: "Panel.tsx", type: "file", indent: 2, fileType: "tsx" },
  { name: "StatusBar.tsx", type: "file", indent: 2, fileType: "tsx" },
  { name: "App.tsx", type: "file", indent: 1, status: "M", fileType: "tsx" },
  { name: "main.tsx", type: "file", indent: 1, fileType: "tsx" },
  { name: "tests", type: "folder", indent: 0, expanded: false },
  { name: "test_agent.py", type: "file", indent: 1, fileType: "py" },
  { name: "test_memory.py", type: "file", indent: 1, fileType: "py" },
  { name: "requirements.txt", type: "file", indent: 0, fileType: "txt" },
  { name: "README.md", type: "file", indent: 0, fileType: "md" },
];

/** File status indicator classes */
function statusIndicatorClass(status?: string): string {
  if (status === "M") return "text-[#e9c349]"; // gold — modified
  if (status === "A") return "text-[#4ade80]"; // green — added/new
  if (status === "D") return "text-[#f87171]"; // red — deleted
  return "";
}

function statusDotClass(status?: string): string {
  if (status === "M") return "bg-[#facc15]"; // yellow — modified
  if (status === "A") return "bg-[#4ade80]"; // green — added
  if (status === "D") return "bg-[#f87171]"; // red — deleted
  return "bg-[#3a494a]"; // muted — no status
}

function statusLetter(status?: string): string {
  if (status === "M") return "M";
  if (status === "A") return "U";
  if (status === "D") return "D";
  return "";
}

const recentMemories = [
  { text: "Uses FastAPI + async routes", time: "2 days ago", dotColor: "bg-[#4ade80]" },
  { text: "Prefers snake_case, ruff for linting", time: "1 week ago", dotColor: "bg-[#60a5fa]" },
  { text: "Added ChromaDB for embeddings", time: "2 weeks ago", dotColor: "bg-[#facc15]" },
];

function Sidebar() {
  const activeSidebarTab = useAppStore((s) => s.activeSidebarTab);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(
    new Set(["src", "components"])
  );
  const [activeFile, setActiveFile] = useState("main.py");

  const toggleFolder = (name: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  /* ─── Explorer (File Tree) ─── */
  const renderExplorer = () => (
    <aside className="flex flex-col h-full bg-bg-onyx">
      {/* Explorer Header */}
      <div className="h-10 px-4 flex items-center justify-between border-b border-border-subtle">
        <span className="font-mono text-[10px] font-semibold tracking-widest uppercase text-text-secondary">
          EXPLORER
        </span>
        <span className="material-symbols-outlined text-[16px] cursor-pointer text-text-secondary hover:text-text-primary transition-colors">
          more_horiz
        </span>
      </div>

      {/* Project name */}
      <div className="h-7 px-4 flex items-center border-b border-border-subtle">
        <span className="font-mono text-[10px] font-semibold tracking-widest uppercase text-text-secondary">
          MY-API-PROJECT
        </span>
      </div>

      {/* File Tree */}
      <div className="flex-1 overflow-auto py-2 font-mono text-sm">
        <div className="flex flex-col gap-[2px]">
          {fileTree.map((node) => {
            const isFolder = node.type === "folder";
            const isExpanded = expandedFolders.has(node.name);
            const isActive = activeFile === node.name;

            return (
              <div
                key={node.name + node.indent}
                onClick={() => {
                  if (isFolder) toggleFolder(node.name);
                  else setActiveFile(node.name);
                }}
                className={
                  "flex items-center cursor-pointer border-l-2 transition-colors duration-[50ms] " +
                  (isActive
                    ? "border-accent-cyan bg-white/5 text-text-primary"
                    : "border-transparent hover:bg-white/5 text-text-secondary")
                }
                style={{
                  height: 26,
                  paddingLeft: 16 + node.indent * 16,
                  paddingRight: 8,
                }}
              >
                {isFolder ? (
                  <span className="material-symbols-outlined text-[16px] mr-1 text-[#3a494a]">
                    {isExpanded ? "arrow_drop_down" : "arrow_right"}
                  </span>
                ) : (
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 mr-2 ${statusDotClass(node.status)}`}
                  />
                )}
                <span className="truncate text-[13px]">
                  {isFolder ? node.name + "/" : node.name}
                </span>
                {node.status && (
                  <span
                    className={`text-[9px] font-semibold ml-auto font-mono ${statusIndicatorClass(node.status)}`}
                  >
                    {statusLetter(node.status)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent Memory Section */}
      <div className="h-56 border-t border-border-subtle flex flex-col">
        <div className="h-8 px-4 flex items-center gap-2">
          <span className="material-symbols-outlined text-[14px] text-accent-gold">
            memory
          </span>
          <span className="font-mono text-[10px] font-semibold tracking-widest uppercase text-text-secondary">
            RECENT MEMORY
          </span>
        </div>
        <div className="flex-1 overflow-auto p-3 flex flex-col gap-3">
          {recentMemories.map((mem, i) => (
            <div key={i} className="flex gap-3">
              <div className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${mem.dotColor}`} />
              <div>
                <div className="text-[12px] text-text-primary">{mem.text}</div>
                <div className="text-[10px] text-text-secondary mt-0.5">{mem.time}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );

  /* ─── MCP Panel ─── */
  const renderMCP = () => (
    <aside className="flex flex-col h-full bg-bg-onyx">
      <div className="h-10 px-4 flex items-center border-b border-border-subtle">
        <span className="font-mono text-[10px] font-semibold tracking-widest uppercase text-text-secondary">
          MCP SERVERS
        </span>
      </div>
      <div className="flex-1 overflow-hidden">
        <MCPConnector />
      </div>
    </aside>
  );

  /* ─── Placeholder panels ─── */
  const renderPlaceholder = (label: string, icon: string) => (
    <aside className="flex flex-col h-full bg-bg-onyx">
      <div className="h-10 px-4 flex items-center border-b border-border-subtle">
        <span className="font-mono text-[10px] font-semibold tracking-widest uppercase text-text-secondary">
          {label.toUpperCase()}
        </span>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center gap-3 text-text-secondary">
        <span className="material-symbols-outlined text-[32px] opacity-30">{icon}</span>
        <span className="text-[11px] font-mono font-semibold tracking-wider">{label}</span>
        <span className="text-[10px] font-mono opacity-60">Coming in v0.2.0</span>
      </div>
    </aside>
  );

  /* ─── Tab routing ─── */
  switch (activeSidebarTab) {
    case "explorer":
      return renderExplorer();
    case "mcp":
      return renderMCP();
    case "search":
      return renderPlaceholder("Search", "search");
    case "git":
      return renderPlaceholder("Source Control", "account_tree");
    case "debug":
      return renderPlaceholder("Run and Debug", "bug_report");
    case "extensions":
      return renderPlaceholder("Extensions", "extension");
    default:
      return renderExplorer();
  }
}

export default Sidebar;
