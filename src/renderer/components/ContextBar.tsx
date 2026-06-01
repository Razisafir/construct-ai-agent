import { Brain } from "lucide-react";

interface ContextBarProps {
  percent: number;
  onClick?: () => void;
}

export function ContextBar({ percent, onClick }: ContextBarProps) {
  const barColor =
    percent < 70 ? "var(--c-ok)" : percent < 90 ? "var(--c-gold)" : "var(--c-err)";

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1 bg-transparent border-none cursor-pointer font-mono"
      title="Context window usage"
    >
      <Brain size={10} style={{ color: "var(--c-text3)" }} />
      <span className="text-[10px] tabular-nums" style={{ color: "var(--c-text3)" }}>
        {Math.round(percent)}%
      </span>
      <div className="w-8 h-1 overflow-hidden" style={{ background: "var(--c-border)" }}>
        <div
          className="h-full rounded-none"
          style={{
            background: barColor,
            width: `${percent}%`,
            transition: "width 100ms ease-in-out",
          }}
        />
      </div>
    </button>
  );
}

export default ContextBar;
