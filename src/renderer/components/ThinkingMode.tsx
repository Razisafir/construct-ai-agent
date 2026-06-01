import { useState } from "react";
import { Brain } from "lucide-react";

interface ThinkingModeProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  thinkingSteps?: string[];
}

export function ThinkingMode({ enabled, onToggle, thinkingSteps = [] }: ThinkingModeProps) {
  const [showSteps, setShowSteps] = useState(true);

  return (
    <div className="flex flex-col gap-1.5 font-mono">
      {/* Toggle button */}
      <button
        onClick={() => onToggle(!enabled)}
        className="flex items-center gap-1.5 px-2.5 py-[5px] rounded-sm text-[10px] font-medium tracking-wider uppercase cursor-pointer font-mono border-none"
        style={{
          border: enabled ? "1px solid var(--c-accent)" : "1px solid var(--c-s3)",
          background: enabled ? "var(--c-s2)" : "var(--c-s1)",
          color: enabled ? "var(--c-accent)" : "var(--c-text3)",
          transition: "none",
        }}
      >
        <Brain size={14} />
        <span>DEEP THINK {enabled ? "ON" : "OFF"}</span>
      </button>

      {/* Thinking steps visualization */}
      {enabled && thinkingSteps.length > 0 && (
        <div
          className="px-2 py-1.5"
          style={{ background: "var(--c-s2)", borderLeft: "2px solid var(--c-accent)", borderRadius: 0, display: showSteps ? "block" : "none" }}
        >
          <div
            onClick={() => setShowSteps(!showSteps)}
            className="text-[10px] tracking-wider uppercase cursor-pointer select-none mb-1"
            style={{ color: "var(--c-text3)" }}
          >
            {showSteps ? "[-]" : "[+]"} REASONING TRACE ({thinkingSteps.length})
          </div>

          {showSteps && (
            <div className="flex flex-col gap-[3px]">
              {thinkingSteps.map((step, i) => (
                <div key={i} className="text-[11px] leading-[14px] font-mono" style={{ color: "var(--c-accent)" }}>
                  <span className="mr-1" style={{ color: "var(--c-text4)" }}>{String(i + 1).padStart(2, "0")}</span>
                  <span className="mr-1" style={{ color: "var(--c-text4)" }}>&gt;</span>
                  {step}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ThinkingMode;
