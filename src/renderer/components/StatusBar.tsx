import { useState, useEffect } from "react";
import useAppStore from "../stores/useAppStore";

const BACKEND_URL = "http://127.0.0.1:8000";

interface LSPStatus {
  servers: Record<string, {
    installed: boolean;
    running: boolean;
    languages: string[];
    install_hint: string;
  }>;
}

interface CompletionStats {
  available: boolean;
  total_requests: number;
  successful: number;
  accepted: number;
  dismissed: number;
  avg_latency_ms: number;
  providers: {
    groq: boolean;
    ollama: boolean;
    openai: boolean;
  };
}

function StatusBar() {
  const branch = "feat/plan-act-mode";
  const skills = useAppStore((s) => s.skills);
  const activeSkillCount = skills.filter((s) => s.installed).length;
  const cursorPosition = useAppStore((s) => s.cursorPosition);
  const agentMode = useAppStore((s) => s.agentMode);

  const [lspStatus, setLspStatus] = useState<LSPStatus | null>(null);
  const [completionStats, setCompletionStats] = useState<CompletionStats | null>(null);

  const openSkillSettings = () => {
    window.dispatchEvent(new CustomEvent("construct:open-settings"));
  };

  // Fetch LSP status periodically
  useEffect(() => {
    const fetchLSPStatus = async () => {
      try {
        const resp = await fetch(`${BACKEND_URL}/lsp/status`, {
          signal: AbortSignal.timeout(3000),
        });
        if (resp.ok) {
          const data = await resp.json();
          setLspStatus(data);
        }
      } catch {
        // Backend not available — that's fine, LSP is optional
      }
    };

    fetchLSPStatus();
    const interval = setInterval(fetchLSPStatus, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // Fetch completion stats periodically
  useEffect(() => {
    const fetchCompletionStats = async () => {
      try {
        const resp = await fetch(`${BACKEND_URL}/completions/stats`, {
          signal: AbortSignal.timeout(3000),
        });
        if (resp.ok) {
          const data = await resp.json();
          setCompletionStats(data);
        }
      } catch {
        // Backend not available
      }
    };

    fetchCompletionStats();
    const interval = setInterval(fetchCompletionStats, 30000);
    return () => clearInterval(interval);
  }, []);

  // Determine active LSP languages
  const runningLSPs = lspStatus
    ? Object.entries(lspStatus.servers)
        .filter(([, s]) => s.running)
        .map(([key, s]) => s.languages[0] ?? key)
    : [];

  // Determine if AI completions are available
  const aiAvailable = completionStats?.available ?? false;

  return (
    <footer className="h-8 flex-shrink-0 bg-bg-onyx border-t border-border-subtle flex items-center justify-between px-4 text-xs font-mono text-text-secondary relative z-50">
      {/* Left section */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 text-status-running">
          <span className="w-2 h-2 rounded-full bg-status-running" />
          memory active
        </div>
        <div className="flex items-center gap-2 text-accent-cyan">
          <span className="w-2 h-2 rounded-full bg-accent-cyan" />
          Kimi K2.5 · local
        </div>
        <div className="text-text-secondary">
          main.py · line {cursorPosition.line}
        </div>

        {/* LSP indicator */}
        {runningLSPs.length > 0 && (
          <div className="flex items-center gap-1.5 text-status-running">
            <span className="w-1.5 h-1.5 rounded-full bg-status-running animate-pulse" />
            <span className="text-[10px] uppercase tracking-wider font-semibold">
              {runningLSPs.map((l) => l.toUpperCase()).join(" · ")} LSP
            </span>
          </div>
        )}

        {/* LSP not installed indicator */}
        {lspStatus && runningLSPs.length === 0 && (
          <div className="flex items-center gap-1.5 text-text-secondary/50">
            <span className="w-1.5 h-1.5 rounded-full bg-text-secondary/30" />
            <span className="text-[10px]">No LSP</span>
          </div>
        )}
      </div>

      {/* Right section */}
      <div className="flex items-center gap-6">
        {/* Security mode indicator */}
        {agentMode === "security" && (
          <span className="flex items-center gap-1.5 text-emerald-400 cursor-default" title="Security mode active — Nmap scanning available">
            <span className="material-symbols-outlined text-[12px]">shield</span>
            <span className="text-[10px] font-mono uppercase tracking-wider font-semibold">Security</span>
          </span>
        )}

        {/* AI Completions indicator */}
        {aiAvailable ? (
          <span className="flex items-center gap-1.5 text-[#00E5FF] cursor-default" title={`AI completions active · ${completionStats?.successful ?? 0} suggestions · avg ${Math.round(completionStats?.avg_latency_ms ?? 0)}ms`}>
            <svg className="w-3 h-3 animate-pulse" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 2a8 8 0 100 16 8 8 0 000-16z"/>
            </svg>
            <span className="text-[10px]">AI Ready</span>
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-text-secondary/50" title="No AI completion provider configured. Set GROQ_API_KEY or run Ollama.">
            <span className="w-1.5 h-1.5 rounded-full bg-text-secondary/30" />
            <span className="text-[10px]">AI Off</span>
          </span>
        )}

        {/* Skills indicator */}
        <span
          className="cursor-pointer hover:text-white flex items-center gap-1.5 transition-colors"
          onClick={openSkillSettings}
          title={`${activeSkillCount} skills active — click to manage`}
        >
          <span className="material-symbols-outlined text-[14px]">settings_suggest</span>
          {activeSkillCount} skills
        </span>
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[14px]">edit_note</span>
          {branch}
        </div>
        <div>
          2 pending · 0 errors
        </div>
      </div>
    </footer>
  );
}

export default StatusBar;
