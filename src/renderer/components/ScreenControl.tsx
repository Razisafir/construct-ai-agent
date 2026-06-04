import { useState } from "react";
import type { ReactNode } from "react";
import {
  Monitor, Shield, ShieldCheck, Play, Pause, Square, Repeat,
  MousePointer, Keyboard, Type, ScrollText, Move, Camera, Clock,
  CheckCircle, AlertTriangle, ChevronDown, ChevronRight, Zap, Eye, Trash2,
} from "lucide-react";

const ff = '"Geist Mono", "JetBrains Mono", monospace';

interface ScreenAction { id: string; actionType: string; params: Record<string, unknown>; timestamp: number; approved: boolean; }
interface Screenshot { id: string; timestamp: number; label: string; }

const actionTypeIcons: Record<string, ReactNode> = {
  click: <MousePointer size={12} />, type: <Type size={12} />, key: <Keyboard size={12} />,
  scroll: <ScrollText size={12} />, drag: <Move size={12} />, screenshot: <Camera size={12} />,
};

const actionTypeColors: Record<string, string> = {
  click: "var(--c-accent)", type: "var(--c-running)", key: "#cba6f7",
  scroll: "var(--c-gold)", drag: "#fab387", screenshot: "#94e2d5",
};

const demoActions: ScreenAction[] = [
  { id: "1", actionType: "click", params: { x: 482, y: 315, target: "submit-button" }, timestamp: Date.now() - 300000, approved: true },
  { id: "2", actionType: "type", params: { text: "admin@example.com", target: "email-input" }, timestamp: Date.now() - 240000, approved: true },
  { id: "3", actionType: "key", params: { key: "Enter" }, timestamp: Date.now() - 180000, approved: true },
  { id: "4", actionType: "scroll", params: { direction: "down", amount: 300 }, timestamp: Date.now() - 120000, approved: true },
  { id: "5", actionType: "screenshot", params: { fullPage: false }, timestamp: Date.now() - 60000, approved: true },
];

const demoScreenshots: Screenshot[] = [
  { id: "s1", timestamp: Date.now() - 60000, label: "Login page" },
  { id: "s2", timestamp: Date.now() - 300000, label: "Dashboard" },
  { id: "s3", timestamp: Date.now() - 600000, label: "Settings modal" },
];

const demoAuditLog = [
  { id: "a1", action: "Safety mode enabled", timestamp: Date.now() - 3600000, level: "info" },
  { id: "a2", action: "Screen access granted", timestamp: Date.now() - 3300000, level: "success" },
  { id: "a3", action: "Action requires approval: click at (482, 315)", timestamp: Date.now() - 3000000, level: "warning" },
  { id: "a4", action: "Action approved by user", timestamp: Date.now() - 2950000, level: "success" },
  { id: "a5", action: "Recording session started", timestamp: Date.now() - 2000000, level: "info" },
];

export default function ScreenControl() {
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [loopEnabled, setLoopEnabled] = useState(false);
  const [sandboxMode, setSandboxMode] = useState(true);
  const [consentRequired, setConsentRequired] = useState(true);
  const [rateLimit, setRateLimit] = useState(10);
  const [actions, setActions] = useState<ScreenAction[]>(demoActions);
  const [expandedAction, setExpandedAction] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"recorder" | "screenshots" | "audit">("recorder");

  const formatTime = (ts: number) => { const d = new Date(ts); return d.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" }); };
  const toggleRecording = () => { setIsRecording(!isRecording); if (!isRecording) { setActions([...actions, { id: `action-${Date.now()}`, actionType: "key", params: { key: "Record started" }, timestamp: Date.now(), approved: true }]); } };
  const deleteAction = (id: string) => { setActions(actions.filter((a) => a.id !== id)); };

  const smallBtn = (bg: string, color: string): React.CSSProperties => ({
    display: "flex", alignItems: "center", gap: "4px", padding: "4px 10px", borderRadius: "2px",
    fontSize: "10px", fontWeight: 500, fontFamily: ff, border: "none", cursor: "pointer",
    backgroundColor: bg, color: color, transition: "background-color 0.15s",
  });

  return (
    <div className="flex flex-col h-full overflow-auto font-mono">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--c-s3)", backgroundColor: "var(--c-s1)" }}>
        <div className="flex items-center gap-2">
          <Monitor size={16} style={{ color: "var(--c-accent)" }} />
          <span className="text-[13px] font-semibold" style={{ color: "var(--c-text)" }}>Screen Control</span>
          <span className="inline-flex items-center gap-1 px-2 py-[2px] rounded-sm text-[9px] font-semibold uppercase tracking-wider" style={{ backgroundColor: sandboxMode ? "var(--c-running-bg)" : "var(--c-gold-dim)", color: sandboxMode ? "var(--c-running)" : "var(--c-gold)" }}>
            {sandboxMode ? "Sandbox" : "Unsafe"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {sandboxMode ? <ShieldCheck size={14} style={{ color: "var(--c-running)" }} /> : <Shield size={14} style={{ color: "var(--c-gold)" }} />}
        </div>
      </div>

      {/* Safety Settings */}
      <div className="px-4 py-2" style={{ borderBottom: "1px solid var(--c-s3)", backgroundColor: "var(--c-s1)" }}>
        <div className="text-[10px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--c-text3)" }}>Safety Settings</div>
        <div className="flex items-center gap-4 flex-wrap">
          <label className="flex items-center gap-2 cursor-pointer">
            <button onClick={() => setSandboxMode(!sandboxMode)} className="relative w-8 h-4 rounded-lg border-none cursor-pointer" style={{ backgroundColor: sandboxMode ? "rgba(34,197,94,0.25)" : "rgba(107,107,115,0.13)", transition: "background-color 0.15s" }}>
              <div className="absolute top-[2px] w-3 h-3 rounded-full" style={{ backgroundColor: sandboxMode ? "var(--c-running)" : "var(--c-text3)", left: sandboxMode ? "16px" : "2px", transition: "left 0.15s, background-color 0.15s" }} />
            </button>
            <span className="text-[10px]" style={{ color: "var(--c-text)" }}>Sandbox</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <button onClick={() => setConsentRequired(!consentRequired)} className="relative w-8 h-4 rounded-lg border-none cursor-pointer" style={{ backgroundColor: consentRequired ? "var(--c-accent-dim)" : "rgba(107,107,115,0.13)", transition: "background-color 0.15s" }}>
              <div className="absolute top-[2px] w-3 h-3 rounded-full" style={{ backgroundColor: consentRequired ? "var(--c-accent)" : "var(--c-text3)", left: consentRequired ? "16px" : "2px", transition: "left 0.15s, background-color 0.15s" }} />
            </button>
            <span className="text-[10px]" style={{ color: "var(--c-text)" }}>Require consent</span>
          </label>
          <div className="flex items-center gap-1.5">
            <Zap size={10} style={{ color: "var(--c-text3)" }} />
            <span className="text-[10px]" style={{ color: "var(--c-text3)" }}>Rate:</span>
            <input type="range" min={1} max={60} value={rateLimit} onChange={(e) => setRateLimit(Number(e.target.value))} className="w-16 h-1" style={{ accentColor: "var(--c-accent)" }} />
            <span className="text-[10px] font-mono" style={{ color: "var(--c-accent)" }}>{rateLimit}/min</span>
          </div>
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="flex items-center gap-1 px-4 py-1" style={{ borderBottom: "1px solid var(--c-s3)", backgroundColor: "var(--c-s1)" }}>
        {[
          { id: "recorder" as const, label: "Recorder", icon: <MousePointer size={10} /> },
          { id: "screenshots" as const, label: "Screenshots", icon: <Camera size={10} /> },
          { id: "audit" as const, label: "Audit Log", icon: <Eye size={10} /> },
        ].map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} className="flex items-center gap-1 px-2.5 py-1 rounded-sm text-[10px] font-medium font-mono border-none cursor-pointer" style={{
            backgroundColor: activeTab === tab.id ? "var(--c-accent-dim)" : "transparent",
            color: activeTab === tab.id ? "var(--c-accent)" : "var(--c-text3)",
            transition: "background-color 0.15s, color 0.15s",
          }}>
            {tab.icon}{tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto px-4 py-3" style={{ backgroundColor: "var(--c-base)" }}>
        {activeTab === "recorder" && (
          <div className="flex flex-col gap-3">
            <div className="p-3 border" style={{ borderColor: "var(--c-s3)", backgroundColor: "var(--c-s1)" }}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <button onClick={toggleRecording} style={smallBtn(isRecording ? "var(--c-err)" : "var(--c-accent)", "var(--c-text)")}>
                    <div className="w-2 h-2" style={{ borderRadius: isRecording ? "0px" : "4px", backgroundColor: "var(--c-text)" }} />{isRecording ? "Stop" : "Record"}
                  </button>
                  <div className="flex items-center gap-1 ml-2">
                    <button onClick={() => setIsPlaying(!isPlaying)} disabled={actions.length === 0} style={{ ...smallBtn("var(--c-s3)", "var(--c-text2)"), opacity: actions.length === 0 ? 0.4 : 1, cursor: actions.length === 0 ? "not-allowed" : "pointer" }}>
                      {isPlaying ? <Pause size={10} /> : <Play size={10} />}
                    </button>
                    <button disabled={actions.length === 0} style={{ ...smallBtn("var(--c-s3)", "var(--c-text2)"), opacity: actions.length === 0 ? 0.4 : 1, cursor: actions.length === 0 ? "not-allowed" : "pointer" }}>
                      <Square size={10} />
                    </button>
                    <button onClick={() => setLoopEnabled(!loopEnabled)} style={smallBtn(loopEnabled ? "var(--c-accent)" : "var(--c-s3)", loopEnabled ? "var(--c-text)" : "var(--c-text2)")}>
                      <Repeat size={10} />
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px]" style={{ color: "var(--c-text3)" }}>Speed:</span>
                  <select value={playbackSpeed} onChange={(e) => setPlaybackSpeed(Number(e.target.value))} className="h-6 px-1.5 font-mono text-[10px] outline-none rounded-sm" style={{ backgroundColor: "var(--c-s1)", border: "1px solid var(--c-s3)", color: "var(--c-text)" }}>
                    <option value={0.25}>0.25x</option><option value={0.5}>0.5x</option><option value={1}>1x</option><option value={2}>2x</option><option value={4}>4x</option>
                  </select>
                </div>
              </div>
              {actions.length > 0 && (
                <div className="mt-2">
                  <div className="flex items-center justify-between text-[10px] mb-1">
                    <span style={{ color: "var(--c-text3)" }}>{actions.length} actions</span>
                    <span style={{ color: "var(--c-accent)" }}>{isPlaying ? "Playing..." : isRecording ? "Recording..." : "Ready"}</span>
                  </div>
                  <div className="h-1 overflow-hidden" style={{ backgroundColor: "var(--c-s2)" }}>
                    <div className="h-full" style={{ width: isRecording ? "60%" : isPlaying ? "100%" : "0%", background: `linear-gradient(90deg, var(--c-accent), var(--c-running))`, transition: "width 0.3s linear" }} />
                  </div>
                </div>
              )}
            </div>
            <div className="flex flex-col gap-[2px]">
              {actions.map((action) => (
                <div key={action.id} className="flex items-center gap-2 px-2 py-1.5 rounded-sm cursor-default"
                  onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "var(--c-s1)"; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}>
                  <div className="w-6 h-6 rounded-sm flex items-center justify-center shrink-0" style={{ backgroundColor: `${actionTypeColors[action.actionType]}20`, color: actionTypeColors[action.actionType] }}>
                    {actionTypeIcons[action.actionType]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-medium capitalize" style={{ color: "var(--c-text)" }}>{action.actionType}</span>
                      <span className="text-[9px] font-mono" style={{ color: "var(--c-text3)" }}>{formatTime(action.timestamp)}</span>
                    </div>
                    <div className="text-[10px] overflow-hidden text-ellipsis whitespace-nowrap" style={{ color: "var(--c-text3)" }}>
                      {Object.entries(action.params).map(([k, v]) => `${k}: ${String(v)}`).join(", ")}
                    </div>
                  </div>
                  <div className="flex items-center gap-[2px]">
                    <button onClick={() => setExpandedAction(expandedAction === action.id ? null : action.id)} className="p-1 rounded-sm border-none bg-transparent cursor-pointer flex items-center justify-center" style={{ color: "var(--c-text3)" }}>
                      {expandedAction === action.id ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                    </button>
                    <button onClick={() => deleteAction(action.id)} className="p-1 rounded-sm border-none bg-transparent cursor-pointer flex items-center justify-center"
                      style={{ color: "var(--c-text3)" }}
                      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--c-err)"; }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--c-text3)"; }}>
                      <Trash2 size={10} />
                    </button>
                  </div>
                  {action.approved ? <CheckCircle size={12} className="shrink-0" style={{ color: "var(--c-running)" }} /> : <AlertTriangle size={12} className="shrink-0" style={{ color: "var(--c-gold)" }} />}
                </div>
              ))}
            </div>
            {actions.length === 0 && (
              <div className="flex flex-col items-center justify-center py-8" style={{ color: "var(--c-text3)" }}>
                <MousePointer size={24} className="mb-2 opacity-50" />
                <p className="text-xs">No recorded actions</p>
                <p className="text-[10px] mt-1">Click Record to start capturing</p>
              </div>
            )}
          </div>
        )}
        {activeTab === "screenshots" && (
          <div className="grid grid-cols-3 gap-2">
            {demoScreenshots.map((shot) => (
              <div key={shot.id} className="p-2 border cursor-pointer" style={{ borderColor: "var(--c-s3)", backgroundColor: "var(--c-s1)", transition: "border-color 0.15s" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--c-accent)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--c-s3)"; }}>
                <div className="aspect-video flex items-center justify-center mb-1.5 border" style={{ backgroundColor: "var(--c-s2)", borderColor: "var(--c-s3)" }}>
                  <Camera size={20} style={{ color: "var(--c-text4)" }} />
                </div>
                <div className="text-[10px] font-medium" style={{ color: "var(--c-text)" }}>{shot.label}</div>
                <div className="text-[9px] font-mono" style={{ color: "var(--c-text3)" }}>{formatTime(shot.timestamp)}</div>
              </div>
            ))}
          </div>
        )}
        {activeTab === "audit" && (
          <div className="flex flex-col gap-[2px]">
            {demoAuditLog.map((log) => (
              <div key={log.id} className="flex items-center gap-2 px-2 py-1.5 rounded-sm"
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "var(--c-s1)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.backgroundColor = "transparent"; }}>
                <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: log.level === "success" ? "var(--c-running)" : log.level === "warning" ? "var(--c-gold)" : "var(--c-accent)" }} />
                <Clock size={10} className="shrink-0" style={{ color: "var(--c-text3)" }} />
                <span className="text-[9px] font-mono w-16 shrink-0" style={{ color: "var(--c-text3)" }}>{formatTime(log.timestamp)}</span>
                <span className="text-[11px]" style={{ color: "var(--c-text)" }}>{log.action}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
