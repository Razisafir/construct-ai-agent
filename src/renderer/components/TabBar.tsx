import { useState, useCallback } from "react";

/* ─────────────────────── types ─────────────────────── */

export interface EditorTab {
  id: string;
  fileName: string;
  filePath: string;
  language: string;
  content: string;
  isModified: boolean;
  isActive: boolean;
}

interface TabBarProps {
  tabs: EditorTab[];
  activeTabId: string | null;
  onActivate: (id: string) => void;
  onClose: (id: string) => void;
  onOpen: (tab: Omit<EditorTab, "id" | "isActive">) => void;
}

/* ─────────────────────── component ─────────────────────── */

function TabBar({ tabs, activeTabId, onActivate, onClose }: TabBarProps) {
  const [hoveredTab, setHoveredTab] = useState<string | null>(null);

  const handleClose = useCallback(
    (e: React.MouseEvent, id: string) => {
      e.stopPropagation();
      onClose(id);
    },
    [onClose]
  );

  return (
    <div className="h-10 flex bg-panel-bg border-b border-border-subtle overflow-x-auto">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTabId;
        const showClose = hoveredTab === tab.id || tab.isModified;

        return (
          <button
            key={tab.id}
            onClick={() => onActivate(tab.id)}
            onMouseEnter={() => setHoveredTab(tab.id)}
            onMouseLeave={() => setHoveredTab(null)}
            className={`
              group flex items-center gap-2 px-4 min-w-[120px] cursor-pointer shrink-0 whitespace-nowrap outline-none
              font-mono text-[13px] border-r border-border-subtle
              border-t-2 transition-colors duration-[50ms] relative
              ${isActive
                ? "bg-bg-onyx border-t-accent-cyan text-text-primary"
                : "bg-transparent border-t-transparent text-text-secondary hover:bg-white/5"
              }
            `}
          >
            {/* Modified dot */}
            {tab.isModified && (
              <span className="w-2 h-2 rounded-full bg-[#facc15] shrink-0" />
            )}

            <span>{tab.fileName}</span>

            {/* Close button */}
            <span
              onClick={(e) => handleClose(e, tab.id)}
              className={`
                flex items-center justify-center w-[14px] h-[14px] ml-0.5 shrink-0 cursor-pointer
                text-c-text4 hover:text-c-text2 transition-colors duration-[50ms]
                ${showClose ? "opacity-100" : "opacity-0"}
              `}
            >
              <span className="material-symbols-outlined text-[12px]">close</span>
            </span>
          </button>
        );
      })}

      {/* Empty state placeholder */}
      {tabs.length === 0 && (
        <div className="flex items-center h-full px-3 font-mono text-[11px] text-c-text4">
          no open files
        </div>
      )}
    </div>
  );
}

export default TabBar;
