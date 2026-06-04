import { useState, useEffect, useRef, useCallback } from "react";

/* ─── Types ─── */
interface Agent { id: string; role: string; name: string; status: string; task: string; progress: number; description?: string; messages?: AgentMsg[]; }
interface AgentMsg { msg_id: string; from: string; to: string; type: string; content: string; timestamp: number; }

const ACCENT = "var(--c-accent)";
const GREEN = "var(--c-running)";
const RED = "var(--c-err)";
const AMBER = "var(--c-gold)";
const CYAN = "var(--c-info)";

const roleColors: Record<string, string> = {
  code_engineer: ACCENT, test_engineer: "#a855f7", security_auditor: GREEN,
  ui_designer: AMBER, devops_engineer: "#ec4899", researcher: CYAN,
  project_manager: "#f97316", legal_reviewer: "#64748b",
  code: ACCENT, security: GREEN, ui: AMBER, research: CYAN, devops: "#ec4899", test: "#a855f7",
};

const typeColors: Record<string, string> = {
  delegation: ACCENT, completion: GREEN, broadcast: CYAN, request: ACCENT,
  response: GREEN, conflict: RED, REQ: ACCENT, RES: GREEN, CMP: CYAN, ERR: RED,
};

const API_BASE = "http://127.0.0.1:8000";

const AVAILABLE_ROLES = [
  { id: "code_engineer", label: "Code Engineer", color: ACCENT },
  { id: "test_engineer", label: "Test Engineer", color: "#a855f7" },
  { id: "security_auditor", label: "Security Auditor", color: GREEN },
  { id: "ui_designer", label: "UI Designer", color: AMBER },
  { id: "devops_engineer", label: "DevOps Engineer", color: "#ec4899" },
  { id: "researcher", label: "Researcher", color: CYAN },
  { id: "project_manager", label: "Project Manager", color: "#f97316" },
  { id: "legal_reviewer", label: "Legal Reviewer", color: "#64748b" },
];

export default function MultiAgentPanel() {
  const [teamId, setTeamId] = useState<string | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [messages, setMessages] = useState<AgentMsg[]>([]);
  const [goal, setGoal] = useState("");
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [teamStatus, setTeamStatus] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [selectedRoles, setSelectedRoles] = useState<string[]>(["code_engineer", "test_engineer", "security_auditor"]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => { return () => { if (pollRef.current) clearInterval(pollRef.current); }; }, []);

  const startPolling = useCallback((tid: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/orchestrate/team/${tid}/status`);
        if (!res.ok) { setError(`Status fetch failed: ${res.status}`); return; }
        const data = await res.json();
        setAgents(data.agents || []); setMessages(data.messages || []); setTeamStatus(data.status || "");
        if (data.status === "completed" || data.status === "failed") { if (pollRef.current) clearInterval(pollRef.current); pollRef.current = null; }
      } catch (err: any) { setError(`Poll error: ${err.message}`); }
    }, 1500);
  }, []);

  const startTeam = async () => {
    if (!goal.trim()) return; setIsLoading(true); setError("");
    try {
      const res = await fetch(`${API_BASE}/orchestrate/team`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ goal: goal.trim(), roles: selectedRoles, project_path: "~/construct-projects/default", max_parallel: selectedRoles.length }) });
      if (!res.ok) { const errData = await res.json().catch(() => ({})); setError(`Failed to start team: ${errData.detail || res.status}`); setIsLoading(false); return; }
      const data = await res.json(); setTeamId(data.team_id); setAgents(data.agents || []); setTeamStatus(data.status || "running"); setIsLoading(false); startPolling(data.team_id);
    } catch (err: any) { setError(`Connection error: ${err.message}`); setIsLoading(false); }
  };

  const handleSend = async () => {
    if (!input.trim() || !teamId) return;
    let toAgent: string | null = null; let content = input.trim();
    const mentionMatch = content.match(/^@(\w+)\s+(.*)/);
    if (mentionMatch) { toAgent = mentionMatch[1]; content = mentionMatch[2]; }
    try { await fetch(`${API_BASE}/orchestrate/team/${teamId}/message`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ from_agent: "user", to_agent: toAgent, content }) }); } catch { /* Non-critical */ }
    setInput("");
  };

  const asciiBar = (pct: number): string => { if (pct <= 0) return "--"; const filled = Math.round(pct / 10); return `[${"=".repeat(filled)}${" ".repeat(10 - filled)}] ${pct}%`; };
  const formatTimestamp = (ts: number): string => { if (!ts) return "--"; const d = new Date(ts * 1000); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`; };
  const workingCount = agents.filter((a) => a.status === "working" || a.status === "active").length;

  const border = "1px solid var(--c-border)";

  return (
    <div className="flex flex-col h-full overflow-hidden font-mono bg-c-base text-c-text">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 shrink-0" style={{ borderBottom: border, background: "var(--c-s1)" }}>
        <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--c-text2)" }}>Agent Team</span>
        <span className="text-[10px]" style={{ color: "var(--c-text3)" }}>{teamId ? `${workingCount}/${agents.length} active` : "no team"}</span>
      </div>

      {/* Goal Input */}
      <div className="flex items-center gap-2 px-3 py-1.5 shrink-0" style={{ borderBottom: border, background: "var(--c-s1)" }}>
        <span className="text-[10px] font-medium uppercase tracking-wider shrink-0" style={{ color: "var(--c-text3)" }}>Goal</span>
        {teamId ? (
          <span className="text-[11px] flex-1" style={{ color: "var(--c-text2)" }}>{goal}</span>
        ) : (
          <input type="text" value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="Enter team goal (e.g., 'Build a React dashboard')" className="flex-1 px-2 py-1 text-[11px] font-mono outline-none rounded-sm" style={{ background: "var(--c-s2)", color: "var(--c-text)", border: `1px solid var(--c-border)`, borderRadius: "2px" }} onKeyDown={(e) => { if (e.key === "Enter") startTeam(); }} />
        )}
        {!teamId && (
          <button onClick={startTeam} disabled={isLoading || !goal.trim()} className="px-3 py-[3px] text-[10px] font-mono uppercase tracking-wider font-semibold border-none rounded-sm" style={{ background: "var(--c-accent)", color: "var(--c-base)", cursor: isLoading || !goal.trim() ? "default" : "pointer", opacity: isLoading || !goal.trim() ? 0.5 : 1 }}>
            {isLoading ? "Starting..." : "Start Team"}
          </button>
        )}
        {teamId && <span className="text-[10px] px-1.5 py-[2px] rounded-sm font-semibold" style={{ color: teamStatus === "completed" ? GREEN : teamStatus === "failed" ? RED : ACCENT, background: "var(--c-s2)" }}>{teamStatus}</span>}
      </div>

      {/* Role Picker */}
      {!teamId && (
        <div className="flex flex-wrap gap-1 px-3 py-1 shrink-0 items-center" style={{ borderBottom: border, background: "var(--c-s1)" }}>
          {AVAILABLE_ROLES.map((role) => {
            const isSelected = selectedRoles.includes(role.id);
            return (
              <button key={role.id} onClick={() => { if (isSelected && selectedRoles.length <= 1) return; setSelectedRoles((prev) => isSelected ? prev.filter((r) => r !== role.id) : [...prev, role.id]); }}
                className="text-[9px] font-semibold tracking-wider px-2 py-[2px] rounded-sm uppercase font-mono cursor-pointer"
                style={{ background: isSelected ? role.color : "var(--c-s2)", color: isSelected ? "var(--c-base)" : "var(--c-text3)", border: isSelected ? "none" : `1px solid var(--c-border)`, opacity: isSelected ? 1 : 0.6, transition: "opacity 0.15s, background 0.15s" }}>
                {role.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Error */}
      {error && <div className="px-3 py-1 text-[10px]" style={{ color: "var(--c-err)", background: "var(--c-err-bg)", borderBottom: border }}>{error}</div>}

      {/* Agent Table */}
      <div className="shrink-0" style={{ borderBottom: border }}>
        <div className="flex items-center" style={{ background: "var(--c-s1)" }}>
          {["ROLE", "STATUS", "TASK", "PROGRESS"].map((h) => (
            <div key={h} className="px-2 py-1.5 text-[10px] font-medium uppercase tracking-wider whitespace-nowrap" style={{ flex: h === "TASK" ? 2 : 1, color: "var(--c-text3)" }}>{h}</div>
          ))}
        </div>
        {agents.length === 0 ? (
          <div className="px-3 py-4 text-[11px] text-center" style={{ color: "var(--c-text3)" }}>No agents yet. Enter a goal and click "Start Team".</div>
        ) : agents.map((agent) => (
          <div key={agent.id} className="flex items-center">
            <div className="px-2 py-[5px] text-[11px] font-semibold font-mono" style={{ flex: 1, color: roleColors[agent.role] || roleColors[agent.id] || "var(--c-text2)" }}>{agent.name || agent.role || agent.id}</div>
            <div className="px-2 py-[5px] text-[11px] font-mono" style={{ flex: 1, color: agent.status === "working" || agent.status === "active" ? ACCENT : agent.status === "completed" ? GREEN : agent.status === "failed" ? RED : "var(--c-text3)" }}>{agent.status}</div>
            <div className="px-2 py-[5px] text-[11px] font-mono whitespace-nowrap overflow-hidden text-ellipsis" style={{ flex: 2, color: agent.task ? "var(--c-text2)" : "var(--c-text3)" }}>{agent.task || "--"}</div>
            <div className="px-2 py-[5px] text-[10px] font-mono whitespace-nowrap" style={{ flex: 1, color: agent.progress > 0 ? ACCENT : "var(--c-text3)" }}>{asciiBar(agent.progress)}</div>
          </div>
        ))}
      </div>

      {/* Messages Section */}
      <div className="flex-1 overflow-auto flex flex-col">
        <div className="px-3 py-1.5 text-[10px] font-medium uppercase tracking-wider sticky top-0 z-[1]" style={{ color: "var(--c-text3)", borderBottom: border, background: "var(--c-s1)" }}>
          Messages {messages.length > 0 && `(${messages.length})`}
        </div>
        <div className="flex-1">
          {messages.length === 0 ? (
            <div className="px-3 py-4 text-[11px] text-center" style={{ color: "var(--c-text3)" }}>{teamId ? "Waiting for agent messages..." : "Start a team to see messages"}</div>
          ) : messages.map((msg) => (
            <div key={msg.msg_id} className="flex items-baseline px-3 py-[3px] text-[11px]" style={{ borderBottom: border }}>
              <span className="shrink-0 font-mono min-w-[56px]" style={{ color: "var(--c-text4)" }}>{formatTimestamp(msg.timestamp)}</span>
              <span className="font-semibold shrink-0 min-w-[80px]" style={{ color: roleColors[msg.from] || "var(--c-text2)" }}>{msg.from}</span>
              <span className="mx-1" style={{ color: "var(--c-text4)" }}>→</span>
              <span className="shrink-0 min-w-[80px]" style={{ color: roleColors[msg.to] || "var(--c-text2)" }}>{msg.to}</span>
              <span className="text-[9px] font-semibold px-1 py-[1px] rounded-sm mr-2 min-w-[56px] text-center shrink-0" style={{ color: typeColors[msg.type] || "var(--c-text3)", background: "var(--c-s2)" }}>{msg.type}</span>
              <span style={{ color: "var(--c-text2)" }}>{msg.content}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="flex items-center gap-2 px-3 py-1.5 shrink-0" style={{ borderTop: border, background: "var(--c-s1)" }}>
        <span className="text-xs font-semibold" style={{ color: "var(--c-accent)" }}>{" > "}</span>
        <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") handleSend(); }} placeholder={teamId ? "@role message (or just message to broadcast)" : "Start a team first"} disabled={!teamId}
          className="flex-1 px-0 py-1 text-[11px] font-mono bg-transparent border-none outline-none" style={{ color: "var(--c-text)", opacity: teamId ? 1 : 0.4 }} />
        <button onClick={handleSend} disabled={!input.trim() || !teamId} className="px-2.5 py-[3px] text-[10px] font-mono uppercase tracking-wider border-none rounded-sm"
          style={{ background: "var(--c-s2)", color: input.trim() && teamId ? "var(--c-accent)" : "var(--c-text3)", cursor: input.trim() && teamId ? "pointer" : "default" }}>SEND</button>
      </div>
    </div>
  );
}
