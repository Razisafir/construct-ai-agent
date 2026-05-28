import { useState, useCallback } from "react";
import { X, FileCode } from "lucide-react";

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
    <div
      style={{
        display: "flex",
        alignItems: "center",
        height: 28,
        backgroundColor: C.s1,
        borderBottom: `1px solid ${C.border}`,
        overflowX: "auto",
        overflowY: "hidden",
        flexShrink: 0,
        scrollbarWidth: "thin",
        scrollbarColor: `${C.s3} transparent`,
      }}
    >
      {tabs.map((tab) => {
        const isActive = tab.id === activeTabId;
        const showClose = hoveredTab === tab.id || tab.isModified;

        return (
          <button
            key={tab.id}
            onClick={() => onActivate(tab.id)}
            onMouseEnter={() => setHoveredTab(tab.id)}
            onMouseLeave={() => setHoveredTab(null)}
            style={{
              display: "flex",
              alignItems: "center",
              height: "100%",
              padding: "0 10px",
              gap: 6,
              border: "none",
              borderRight: `1px solid ${C.border}`,
              borderBottom: isActive
                ? `2px solid ${C.accent}`
                : `2px solid transparent`,
              backgroundColor: isActive ? C.s2 : "transparent",
              color: isActive ? C.t1 : C.t3,
              cursor: "pointer",
              flexShrink: 0,
              whiteSpace: "nowrap",
              fontFamily: ff,
              fontSize: 11,
              transition: "background-color 50ms",
              position: "relative",
              outline: "none",
            }}
          >
            <FileCode size={12} style={{ flexShrink: 0, opacity: 0.8 }} />
            <span>{tab.fileName}</span>
            {/* Modified dot */}
            {tab.isModified && (
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  backgroundColor: C.accent,
                  flexShrink: 0,
                  display: "inline-block",
                }}
              />
            )}
            {/* Close button */}
            <span
              onClick={(e) => handleClose(e, tab.id)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 14,
                height: 14,
                marginLeft: 2,
                opacity: showClose ? 1 : 0,
                transition: "opacity 50ms",
                flexShrink: 0,
                cursor: "pointer",
                color: C.t4,
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.color = C.t2;
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.color = C.t4;
              }}
            >
              <X size={12} />
            </span>
          </button>
        );
      })}

      {/* Empty state placeholder */}
      {tabs.length === 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            height: "100%",
            padding: "0 12px",
            fontFamily: ff,
            fontSize: 11,
            color: C.t4,
          }}
        >
          no open files
        </div>
      )}
    </div>
  );
}

export default TabBar;
