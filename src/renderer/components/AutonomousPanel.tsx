import { useState, useCallback, useEffect } from "react";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import { TerminalOutput } from "./TerminalOutput";
import type { LogEntry } from "./TerminalOutput";

/* ─────────────────────── types ─────────────────────── */

type TaskStatus = "OK" | "WRK" | "ERR" | "PND";

interface Task {
  id: string;
  number: number;
  status: TaskStatus;
  description: string;
  time: string;
  agent: string;
}

interface ResourceMetrics {
  cpu: number;
  memUsed: number;
  memTotal: number;
  diskSpeed: string;
}

interface AutonomousState {
  goal: string;
  progress: number;
  tasksCompleted: number;
  totalTasks: number;
  eta: string;
  autoMode: boolean;
  tasks: Task[];
  resources: ResourceMetrics;
  logs: LogEntry[];
}

/* ─────────────────────── colors ─────────────────────── */

const statusColor: Record<TaskStatus, string> = {
  OK: "var(--c-running)",
  WRK: "var(--c-gold)",
  ERR: "var(--c-err)",
  PND: "var(--c-text4)",
};

/* ─────────────────────── sub-components ─────────────────────── */

function ControlButton({ label, onClick }: { label: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-[10px] font-semibold uppercase tracking-wider px-2 py-[3px] cursor-pointer font-mono rounded-sm border-none"
      style={{ backgroundColor: "var(--c-s2)", color: "var(--c-text2)", transition: "background-color 0.1s" }}
      onMouseEnter={(e) => { (e.target as HTMLElement).style.backgroundColor = "var(--c-s3)"; }}
      onMouseLeave={(e) => { (e.target as HTMLElement).style.backgroundColor = "var(--c-s2)"; }}
    >
      {label}
    </button>
  );
}

function AutoToggle({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className="text-[10px] font-semibold uppercase tracking-wider px-2 py-[3px] cursor-pointer font-mono rounded-sm ml-auto border-none"
      style={{
        backgroundColor: enabled ? "var(--c-s2)" : "var(--c-base)",
        color: enabled ? "var(--c-running)" : "var(--c-text4)",
        border: `1px solid ${enabled ? "rgba(34,197,94,0.2)" : "var(--c-border)"}`,
      }}
    >
      AUTO:{enabled ? "ON" : "OFF"}
    </button>
  );
}

function StatusBadge({ status }: { status: TaskStatus }) {
  return (
    <span className="text-[9px] font-bold tracking-wider inline-block min-w-[28px] font-mono" style={{ color: statusColor[status] }}>
      [{status}]
    </span>
  );
}

function ASCIIProgressBar({ percent }: { percent: number }) {
  const total = 20;
  const filled = Math.round((percent / 100) * total);
  const empty = total - filled;
  const bar = "█".repeat(filled) + "░".repeat(empty);
  return (
    <span className="text-[10px] font-mono whitespace-nowrap" style={{ color: "var(--c-text2)" }}>
      {bar}  {percent}%
    </span>
  );
}

/* ─────────────────────── main component ─────────────────────── */

function AutonomousPanel() {
  const [state, setState] = useState<AutonomousState>({
    goal: "", progress: 0, tasksCompleted: 0, totalTasks: 0, eta: "--:--:--",
    autoMode: false, tasks: [], resources: { cpu: 0, memUsed: 0, memTotal: 0, diskSpeed: "0MB/s" }, logs: [],
  });
  const [showLog, setShowLog] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const unlisteners: UnlistenFn[] = [];
    const fetchStatus = async () => {
      try {
        const status = await invoke<{ current_goal?: string; progress_percent: number; tasks_completed: number; queue_size: number; enabled: boolean; resource_cpu: number; resource_memory: number; }>("get_autonomous_status");
        if (cancelled) return;
        setState((prev) => ({ ...prev, goal: status.current_goal ?? "", progress: Math.round(status.progress_percent), tasksCompleted: status.tasks_completed, totalTasks: status.queue_size, autoMode: status.enabled, resources: { cpu: Math.round(status.resource_cpu), memUsed: Math.round(status.resource_memory), memTotal: 2048, diskSpeed: "0MB/s" } }));
      } catch { /* Backend may not have autonomous manager initialized yet */ }
    };
    const fetchLogs = async () => {
      try {
        const logs = await invoke<{ timestamp: number; level: string; message: string; source: string; }[]>("get_agent_log", { lines: 100 });
        if (cancelled) return;
        const mapped: LogEntry[] = logs.map((l) => ({ timestamp: new Date(l.timestamp * 1000).toTimeString().slice(0, 8), level: l.level === "error" ? "ERR" : l.level === "warn" ? "WRK" : l.level === "ok" ? "OK" : "INF", message: l.message, source: l.source }));
        setState((prev) => ({ ...prev, logs: mapped }));
      } catch { /* Backend may not have logs yet */ }
    };
    const setupListeners = async () => {
      const events = ["autonomous:started", "autonomous:paused", "autonomous:resumed", "autonomous:checkpoint", "autonomous:completed", "autonomous:error"];
      for (const eventName of events) { const unlisten = await listen(eventName, () => { if (cancelled) return; void fetchStatus(); void fetchLogs(); }); unlisteners.push(unlisten); }
      await fetchStatus(); await fetchLogs();
    };
    void setupListeners();
    return () => { cancelled = true; unlisteners.forEach((u) => u()); };
  }, []);

  const toggleAuto = useCallback(() => { setState((prev) => ({ ...prev, autoMode: !prev.autoMode })); }, []);
  const handleCommand = useCallback((cmd: string) => {
    setState((prev) => ({ ...prev, logs: [...prev.logs, { timestamp: new Date().toLocaleTimeString("en-US", { hour12: false }), level: "INF", message: `> ${cmd}`, source: "user" }] }));
  }, []);

  return (
    <div className="flex flex-col h-full overflow-hidden font-mono" style={{ backgroundColor: "var(--c-base)", border: "1px solid var(--c-border)" }}>
      <div className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--c-text3)", borderBottom: "1px solid var(--c-border)" }}>AUTONOMOUS MODE</div>
      <div className="px-3 py-1.5 text-xs font-semibold whitespace-nowrap overflow-hidden text-ellipsis" style={{ color: "var(--c-text)", borderBottom: "1px solid var(--c-border)" }} title={state.goal}>GOAL: {state.goal}</div>
      <div className="flex items-center gap-6 px-3 py-1.5 text-[10px] font-mono flex-wrap" style={{ color: "var(--c-text3)", borderBottom: "1px solid var(--c-border)" }}>
        <span>PROGRESS: <ASCIIProgressBar percent={state.progress} /></span>
        <span>TASKS: <span style={{ color: "var(--c-text2)" }}>{state.tasksCompleted}/{state.totalTasks}</span></span>
        <span>ETA: <span style={{ color: "var(--c-text2)" }}>{state.eta}</span></span>
      </div>
      <div className="grid gap-2 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider" style={{ gridTemplateColumns: "24px 36px 1fr 48px 60px", color: "var(--c-text4)", borderBottom: "1px solid var(--c-border)" }}>
        <span>#</span><span>STATUS</span><span>TASK</span><span>TIME</span><span>AGENT</span>
      </div>
      <div className="max-h-[160px] overflow-auto" style={{ scrollbarWidth: "thin", scrollbarColor: "var(--c-s3) transparent", borderBottom: "1px solid var(--c-border)" }}>
        {state.tasks.map((task) => (
          <div key={task.id} className="grid gap-2 px-3 py-[3px] text-[11px] font-mono items-center" style={{ gridTemplateColumns: "24px 36px 1fr 48px 60px", color: "var(--c-text2)", borderBottom: "1px solid rgba(255,255,255,0.02)" }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "var(--c-s1)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}>
            <span className="text-[10px]" style={{ color: "var(--c-text3)" }}>{task.number}</span>
            <StatusBadge status={task.status} />
            <span className="overflow-hidden text-ellipsis whitespace-nowrap">{task.description}</span>
            <span className="text-[10px]" style={{ color: "var(--c-text3)" }}>{task.time}</span>
            <span className="text-[10px]" style={{ color: task.agent === "--" ? "var(--c-text4)" : "var(--c-text2)" }}>{task.agent}</span>
          </div>
        ))}
      </div>
      <div className={`flex items-center gap-1.5 px-3 py-1.5 ${showLog ? "border-b border-c-border" : ""}`}>
        <ControlButton label="PAUSE" /><ControlButton label="STOP" /><ControlButton label="FORCE-CHECKPOINT" /><ControlButton label="VIEW-LOG" onClick={() => setShowLog(!showLog)} />
        <AutoToggle enabled={state.autoMode} onToggle={toggleAuto} />
      </div>
      {showLog && <div className="h-[140px]" style={{ borderBottom: "1px solid var(--c-border)" }}><TerminalOutput logs={state.logs} onCommand={handleCommand} showInput /></div>}
      <div className="flex items-center gap-5 px-3 py-1.5 text-[10px] font-mono mt-auto" style={{ color: "var(--c-text3)" }}>
        <span>RESOURCE:</span>
        <span>CPU: <span style={{ color: "var(--c-text2)" }}>{state.resources.cpu}%</span></span>
        <span>MEM: <span style={{ color: "var(--c-text2)" }}>{state.resources.memUsed}MB/{state.resources.memTotal}GB</span></span>
        <span>DISK: <span style={{ color: "var(--c-text2)" }}>{state.resources.diskSpeed}</span></span>
      </div>
      <style>{`
        div::-webkit-scrollbar { width: 4px; height: 4px; }
        div::-webkit-scrollbar-track { background: transparent; }
        div::-webkit-scrollbar-thumb { background: var(--c-s3); border-radius: 2px; }
        div::-webkit-scrollbar-thumb:hover { background: #3a3a4f; }
      `}</style>
    </div>
  );
}

export default AutonomousPanel;
