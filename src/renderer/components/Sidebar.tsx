import {
  Files,
  Search,
  GitBranch,
  Puzzle,
  Settings,
  FolderOpen,
  ChevronRight,
  ChevronDown,
} from "lucide-react";
import useAppStore from "@/stores/useAppStore";
import { useState } from "react";

interface NavItem {
  id: string;
  icon: React.ReactNode;
  label: string;
}

const navItems: NavItem[] = [
  { id: "files", icon: <Files size={18} />, label: "Explorer" },
  { id: "search", icon: <Search size={18} />, label: "Search" },
  { id: "git", icon: <GitBranch size={18} />, label: "Source Control" },
  { id: "extensions", icon: <Puzzle size={18} />, label: "Extensions" },
];

function Sidebar() {
  const activeTab = useAppStore((s) => s.activeSidebarTab);
  const setActiveTab = useAppStore((s) => s.setActiveSidebarTab);
  const [folderExpanded, setFolderExpanded] = useState(true);

  return (
    <div className="flex w-full h-full">
      {/* Icon Rail */}
      <div className="flex flex-col items-center w-10 py-2 bg-construct-bg-primary-tertiary border-r border-construct-border shrink-0">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            title={item.label}
            className={`
              flex items-center justify-center w-7 h-7 rounded-md mb-1
              transition-colors duration-150
              ${
                activeTab === item.id
                  ? "bg-construct-bg-primary-elevated text-construct-text-primary"
                  : "text-construct-text-muted hover:text-construct-text-primary hover:bg-construct-bg-primary-elevated"
              }
            `}
          >
            {item.icon}
          </button>
        ))}
        <div className="flex-1" />
        <button
          title="Settings"
          className="flex items-center justify-center w-7 h-7 rounded-md mb-1 text-construct-text-muted hover:text-construct-text-primary hover:bg-construct-bg-primary-elevated transition-colors duration-150"
        >
          <Settings size={18} />
        </button>
      </div>

      {/* Content Panel */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Section Header */}
        <div className="flex items-center h-8 px-3 bg-construct-bg-primary-secondary">
          <span className="text-xs font-semibold text-construct-text-muted uppercase tracking-wider select-none">
            {navItems.find((n) => n.id === activeTab)?.label}
          </span>
        </div>

        {/* Files Explorer Content */}
        {activeTab === "files" && (
          <div className="flex-1 overflow-y-auto py-1">
            <button
              onClick={() => setFolderExpanded(!folderExpanded)}
              className="flex items-center w-full px-2 h-6 text-construct-text-primary hover:bg-construct-bg-primary-elevated transition-colors"
            >
              {folderExpanded ? (
                <ChevronDown size={14} className="mr-1 shrink-0" />
              ) : (
                <ChevronRight size={14} className="mr-1 shrink-0" />
              )}
              <FolderOpen size={14} className="mr-1.5 text-construct-accent-primary shrink-0" />
              <span className="text-xs truncate">project-root</span>
            </button>
            {folderExpanded && (
              <div className="pl-5">
                {[
                  { name: "src", icon: "📁" },
                  { name: "components", icon: "📁", indent: 1 },
                  { name: "App.tsx", icon: "📄", indent: 2 },
                  { name: "main.tsx", icon: "📄", indent: 2 },
                  { name: "index.css", icon: "🎨", indent: 1 },
                  { name: "package.json", icon: "📦", indent: 0 },
                  { name: "README.md", icon: "📝", indent: 0 },
                ].map((file) => (
                  <div
                    key={file.name}
                    className="flex items-center h-6 px-2 text-construct-text-primary hover:bg-construct-bg-primary-elevated cursor-pointer transition-colors"
                    style={{ paddingLeft: `${(file.indent || 0) * 12 + 20}px` }}
                  >
                    <span className="text-xs mr-1.5">{file.icon}</span>
                    <span className="text-xs truncate">{file.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Other tabs */}
        {activeTab === "search" && (
          <div className="flex-1 p-3">
            <input
              type="text"
              placeholder="Search files..."
              className="w-full h-7 px-2 bg-construct-bg-primary border border-construct-border rounded text-xs text-construct-text-primary placeholder-construct-text-muted outline-none focus:border-construct-accent-primary transition-colors"
            />
            <p className="mt-3 text-xs text-construct-text-muted">
              Type to search across files
            </p>
          </div>
        )}
        {activeTab === "git" && (
          <div className="flex-1 p-3">
            <p className="text-xs text-construct-text-muted">
              No git repository initialized.
            </p>
          </div>
        )}
        {activeTab === "extensions" && (
          <div className="flex-1 p-3">
            <p className="text-xs text-construct-text-muted">
              Extensions panel coming soon.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default Sidebar;
