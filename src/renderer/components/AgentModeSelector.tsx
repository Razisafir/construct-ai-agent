import { useState, useRef, useEffect } from "react";

export type AgentMode = "code" | "architect" | "debug" | "review" | "security" | "devops";

interface AgentModeSelectorProps {
  mode: AgentMode;
  onChange: (mode: AgentMode) => void;
}

interface ModeConfig {
  id: AgentMode;
  label: string;
  icon: string;
  color: string;
  description: string;
}

const modes: ModeConfig[] = [
  { id: "code", label: "CODE", icon: "code", color: "#00f5ff", description: "Write and edit code" },
  { id: "architect", label: "ARCH", icon: "architecture", color: "#a78bfa", description: "Design and plan architecture" },
  { id: "debug", label: "DEBUG", icon: "bug_report", color: "#e9c349", description: "Find and fix bugs" },
  { id: "review", label: "REVIEW", icon: "visibility", color: "#06b6d4", description: "Code review and quality check" },
  { id: "security", label: "SEC", icon: "shield", color: "#4ade80", description: "Security audit and hardening" },
  { id: "devops", label: "DEVOPS", icon: "dns", color: "#f97316", description: "CI/CD, Docker, deployment" },
];

function AgentModeSelector({ mode, onChange }: AgentModeSelectorProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const activeMode = modes.find((m) => m.id === mode) ?? modes[0];

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) { setOpen(false); }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 h-[22px] px-2 border cursor-pointer font-mono text-[10px] font-semibold tracking-wider outline-none rounded"
        style={{ backgroundColor: "var(--c-s2)", borderColor: "var(--c-border)", borderLeft: `2px solid ${activeMode.color}`, color: activeMode.color, transition: "background-color 0.1s" }}
      >
        <span className="material-symbols-outlined text-[11px]">{activeMode.icon}</span>
        <span>{activeMode.label}</span>
        <span className="text-[8px] ml-[2px] inline-block" style={{ color: "var(--c-text4)", transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.1s" }}>▼</span>
      </button>

      {open && (
        <div
          className="glass-panel absolute left-0 z-[100] min-w-[200px] rounded-lg overflow-hidden"
          style={{ top: "calc(100% + 2px)" }}
        >
          {modes.map((m) => {
            const isSelected = m.id === mode;
            return (
              <button
                key={m.id}
                onClick={() => { onChange(m.id); setOpen(false); }}
                title={m.description}
                className="flex items-center gap-2 w-full h-7 px-2.5 border-none cursor-pointer font-mono text-[10px] text-left outline-none"
                style={{
                  borderBottom: "1px solid var(--c-border)",
                  backgroundColor: isSelected ? "var(--c-s2)" : "transparent",
                  color: isSelected ? m.color : "var(--c-text2)",
                  fontWeight: isSelected ? 600 : 400,
                  letterSpacing: "0.06em",
                  transition: "background-color 50ms",
                }}
              >
                <span className="material-symbols-outlined text-[14px]" style={{ color: m.color, opacity: 0.8 }}>{m.icon}</span>
                <span>{m.label}</span>
                <span className="text-[9px] ml-1 font-normal" style={{ color: "var(--c-text4)", letterSpacing: "normal" }}>{m.description}</span>
                {isSelected && <span className="ml-auto text-[9px]" style={{ color: m.color }}>●</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default AgentModeSelector;
