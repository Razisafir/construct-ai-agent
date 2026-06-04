import { useState, useRef, useEffect, useCallback } from "react";

/* ─────────────────────── types ─────────────────────── */

export interface LogEntry {
  timestamp: string;
  level: "INF" | "OK" | "WRN" | "ERR" | "WRK" | "DBG";
  message: string;
  source?: string;
}

export interface TerminalOutputProps {
  logs: LogEntry[];
  maxHeight?: string;
  onCommand?: (cmd: string) => void;
  showInput?: boolean;
}

/* ─────────────────────── styles ─────────────────────── */

const levelColor: Record<LogEntry["level"], string> = {
  INF: "var(--c-accent)",
  OK: "var(--c-ok)",
  WRN: "var(--c-gold)",
  ERR: "var(--c-err)",
  WRK: "var(--c-accent)",
  DBG: "var(--c-text4)",
};

/* ─────────────────────── component ─────────────────────── */

export function TerminalOutput({
  logs,
  maxHeight = "100%",
  onCommand,
  showInput = false,
}: TerminalOutputProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs.length]);

  const handleSubmit = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" && inputValue.trim() && onCommand) {
        onCommand(inputValue.trim());
        setInputValue("");
      }
    },
    [inputValue, onCommand]
  );

  const focusInput = useCallback(() => {
    if (inputRef.current) inputRef.current.focus();
  }, []);

  return (
    <div
      className="flex flex-col h-full glass-panel font-mono"
    >
      <div
        ref={scrollRef}
        onClick={focusInput}
        className="flex-1 overflow-auto px-2 py-1.5"
        style={{
          maxHeight,
          scrollbarWidth: "thin",
          scrollbarColor: "var(--c-s3) transparent",
        }}
      >
        {logs.length === 0 && (
          <div className="text-[10px] font-mono" style={{ color: "var(--c-text4)" }}>
            -- no output --
          </div>
        )}

        {logs.map((log, i) => (
          <div
            key={i}
            className="flex items-start gap-2 py-[1px] font-mono"
          >
            <span
              className="text-[10px] whitespace-nowrap min-w-[56px] select-none font-mono"
              style={{ color: "var(--c-text4)" }}
            >
              {log.timestamp}
            </span>

            <span
              className="text-[9px] font-semibold whitespace-nowrap min-w-[28px] text-center tracking-wider font-mono rounded px-1 py-[1px]"
              style={{ color: levelColor[log.level], backgroundColor: "var(--c-s2)" }}
            >
              {log.level}
            </span>

            {log.source && (
              <span
                className="text-[9px] whitespace-nowrap min-w-[60px] text-right select-none font-mono"
                style={{ color: "var(--c-text4)" }}
              >
                {log.source}
              </span>
            )}

            <span
              className="text-[11px] flex-1 font-mono leading-4"
              style={{ color: "var(--c-text)", wordBreak: "break-all" }}
            >
              {log.message}
            </span>
          </div>
        ))}

        {showInput && (
          <div
            className="flex items-center gap-1.5 mt-1 font-mono"
          >
            <span
              className="text-xs select-none font-mono"
              style={{ color: "var(--c-accent)" }}
            >
              &gt;
            </span>
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleSubmit}
              className="flex-1 bg-transparent border-none outline-none text-xs font-mono p-0"
              style={{ color: "var(--c-text)", caretColor: "var(--c-accent)" }}
              spellCheck={false}
              autoComplete="off"
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default TerminalOutput;
