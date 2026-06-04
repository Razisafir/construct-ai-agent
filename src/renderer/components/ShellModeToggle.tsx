import { Terminal, Zap, Shield } from "lucide-react";

interface ShellModeToggleProps {
  shellMode: boolean;
  onToggle: (shellMode: boolean) => void;
}

export function ShellModeToggle({ shellMode, onToggle }: ShellModeToggleProps) {
  const baseBtn: React.CSSProperties = {
    display: "flex", alignItems: "center", gap: "6px",
    padding: "4px 10px", borderRadius: "2px", fontSize: "10px", fontWeight: 500,
    fontFamily: '"Geist Mono", "JetBrains Mono", monospace', textTransform: "uppercase",
    border: "none", cursor: "pointer", transition: "background-color 0.15s, color 0.15s",
    letterSpacing: "0.05em",
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => onToggle(false)}
        style={{
          ...baseBtn,
          backgroundColor: !shellMode ? "var(--c-accent)" : "var(--c-s2)",
          color: !shellMode ? "var(--c-text)" : "var(--c-text3)",
        }}
      >
        <Zap size={10} />
        Agent
      </button>
      <button
        onClick={() => onToggle(true)}
        style={{
          ...baseBtn,
          backgroundColor: shellMode ? "var(--c-accent)" : "var(--c-s2)",
          color: shellMode ? "var(--c-text)" : "var(--c-text3)",
        }}
      >
        <Terminal size={10} />
        Shell
        <Shield size={9} style={{ color: "var(--c-gold)" }} />
      </button>
    </div>
  );
}

export default ShellModeToggle;
