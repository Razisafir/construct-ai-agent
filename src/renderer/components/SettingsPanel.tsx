import React, { useState } from "react";

const C = {
  base: "#0a0a10", s1: "#12121a", s2: "#1a1a24", s3: "#22222e",
  accent: "#6366f1", t1: "#e8e8ec", t2: "#94949c", t3: "#6b6b73", t4: "#4a4a52",
  err: "#ef4444", ok: "#10b981",
};
const ff = '"Geist Mono", "JetBrains Mono", monospace';

type Category = "general" | "ai" | "agent" | "memory" | "security" | "shortcuts" | "advanced";

const CATEGORIES: { id: Category; label: string }[] = [
  { id: "general", label: "General" },
  { id: "ai", label: "AI / LLM" },
  { id: "agent", label: "Agent" },
  { id: "memory", label: "Memory" },
  { id: "security", label: "Security" },
  { id: "shortcuts", label: "Shortcuts" },
  { id: "advanced", label: "Advanced" },
];

interface Settings {
  theme: "dark" | "light" | "system";
  font: "jetbrains" | "fira" | "cascadia";
  fontSize: 12 | 14 | 16 | 18;
  lineHeight: 1.2 | 1.5 | 1.8 | 2.0;
  wordWrap: boolean;
  minimap: boolean;
  breadcrumbs: boolean;
  primaryProvider: "openai" | "anthropic" | "google" | "ollama";
  openaiKey: string;
  anthropicKey: string;
  googleKey: string;
  ollamaUrl: string;
  temperature: number;
  maxTokens: number;
  streaming: boolean;
  fallbackProvider: "none" | "openai" | "anthropic" | "google" | "ollama";
  agentMode: "code" | "architect" | "debug" | "review" | "docs" | "test";
  autoStart: boolean;
  backgroundExecution: boolean;
  checkpointInterval: 1 | 5 | 15 | 30;
  maxRetries: number;
  approveDelete: boolean;
  approveGitPush: boolean;
  approveShell: boolean;
  maxConversations: 100 | 500 | 1000;
  autoCompact: boolean;
  compactThreshold: 50 | 70 | 80 | 90;
  agentShield: boolean;
  autoScanCommit: boolean;
  secretsDetection: boolean;
  backendPort: number;
  logLevel: "debug" | "info" | "warning" | "error";
  autoUpdate: boolean;
  betaFeatures: boolean;
}

const DEFAULT_SETTINGS: Settings = {
  theme: "dark", font: "jetbrains", fontSize: 12, lineHeight: 1.5,
  wordWrap: true, minimap: true, breadcrumbs: true,
  primaryProvider: "anthropic", openaiKey: "", anthropicKey: "", googleKey: "", ollamaUrl: "http://localhost:11434",
  temperature: 0.7, maxTokens: 128000, streaming: true, fallbackProvider: "none",
  agentMode: "code", autoStart: false, backgroundExecution: true,
  checkpointInterval: 5, maxRetries: 3,
  approveDelete: true, approveGitPush: true, approveShell: true,
  maxConversations: 500, autoCompact: true, compactThreshold: 80,
  agentShield: true, autoScanCommit: true, secretsDetection: true,
  backendPort: 8000, logLevel: "info", autoUpdate: true, betaFeatures: false,
};

const SHORTCUTS = [
  { action: "New Chat", key: "Ctrl+N" },
  { action: "Send Message", key: "Enter" },
  { action: "New Line", key: "Shift+Enter" },
  { action: "Open Settings", key: "Ctrl+," },
  { action: "Toggle Sidebar", key: "Ctrl+B" },
  { action: "Accept Suggestion", key: "Tab" },
  { action: "Reject Suggestion", key: "Esc" },
  { action: "Open Command Palette", key: "Ctrl+Shift+P" },
  { action: "Search Chats", key: "Ctrl+K" },
  { action: "Toggle Agent Mode", key: "Ctrl+M" },
  { action: "Interrupt Agent", key: "Ctrl+C" },
  { action: "Clear Chat", key: "Ctrl+Shift+X" },
];

const sectionSx: React.CSSProperties = {
  fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em",
  color: C.t3, marginBottom: "8px", marginTop: "24px", fontWeight: 600,
};

const rowSx: React.CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between",
  padding: "8px 0", borderBottom: `1px solid ${C.s1}`,
};

const labelSx: React.CSSProperties = {
  fontSize: "11px", color: C.t1, fontFamily: ff,
};

const inputSx: React.CSSProperties = {
  background: C.s1, border: "1px solid rgba(255,255,255,0.04)",
  borderRadius: 0, color: C.t1, fontFamily: ff, fontSize: "11px",
  padding: "6px 10px", outline: "none", width: "200px",
};

const selectSx: React.CSSProperties = {
  background: C.s1, border: "1px solid rgba(255,255,255,0.04)",
  borderRadius: 0, color: C.t1, fontFamily: ff, fontSize: "10px",
  padding: "6px 10px", outline: "none", minWidth: "140px",
};

const btnSx: React.CSSProperties = {
  background: C.s2, border: "1px solid rgba(255,255,255,0.04)",
  borderRadius: "2px", color: C.t1, fontFamily: ff, fontSize: "10px",
  textTransform: "uppercase", padding: "6px 14px", cursor: "pointer",
  letterSpacing: "0.04em",
};

const dangerBtnSx: React.CSSProperties = {
  ...btnSx, color: C.err, border: `1px solid ${C.err}33`,
};

const checkboxSx: React.CSSProperties = {
  width: "12px", height: "12px", accentColor: C.accent, cursor: "pointer",
};

const sliderSx: React.CSSProperties = {
  width: "140px", height: "2px", accentColor: C.accent,
};

function RadioRow<T extends string | number>({ label, value, options, onChange }: {
  label: string; value: T; options: T[]; onChange: (v: T) => void;
}) {
  return (
    <div style={rowSx}>
      <span style={labelSx}>{label}</span>
      <div style={{ display: "flex", gap: "14px" }}>
        {options.map((o) => (
          <label key={o} style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer", fontSize: "11px", color: C.t2, fontFamily: ff }}>
            <input type="radio" checked={value === o} onChange={() => onChange(o)}
              style={{ accentColor: C.accent, width: "12px", height: "12px", cursor: "pointer" }} />
            {String(o).charAt(0).toUpperCase() + String(o).slice(1)}
          </label>
        ))}
      </div>
    </div>
  );
}

function CheckboxRow({ label, checked, onChange }: {
  label: string; checked: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div style={rowSx}>
      <span style={labelSx}>{label}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} style={checkboxSx} />
    </div>
  );
}

function SliderRow({ label, value, min, max, step, display, onChange }: {
  label: string; value: number; min: number; max: number; step: number;
  display: string; onChange: (v: number) => void;
}) {
  return (
    <div style={rowSx}>
      <span style={labelSx}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <input type="range" min={min} max={max} step={step} value={value}
          onChange={(e) => onChange(Number(e.target.value))} style={sliderSx} />
        <span style={{ fontSize: "11px", color: C.t2, fontFamily: ff, minWidth: "50px", textAlign: "right" }}>{display}</span>
      </div>
    </div>
  );
}

export default function SettingsPanel() {
  const [cat, setCat] = useState<Category>("general");
  const [s, setS] = useState<Settings>(DEFAULT_SETTINGS);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const update = <K extends keyof Settings>(key: K, val: Settings[K]) => setS((p) => ({ ...p, [key]: val }));

  const panelBase: React.CSSProperties = {
    display: "flex", height: "100%", background: C.base,
    fontFamily: ff, fontSize: "12px", color: C.t1,
  };
  const sidebar: React.CSSProperties = {
    width: "200px", background: C.s1, borderRight: "1px solid rgba(255,255,255,0.04)",
    display: "flex", flexDirection: "column", padding: "8px 0",
  };
  const content: React.CSSProperties = {
    flex: 1, overflowY: "auto", padding: "24px 32px",
  };

  return (
    <div style={panelBase}>
      {/* LEFT SIDEBAR */}
      <div style={sidebar}>
        <div style={{ padding: "8px 12px 16px", fontSize: "10px", textTransform: "uppercase",
          letterSpacing: "0.1em", color: C.t3, fontWeight: 700 }}>Settings</div>
        {CATEGORIES.map((c) => {
          const active = cat === c.id;
          return (
            <button key={c.id} onClick={() => setCat(c.id)} style={{
              display: "block", width: "100%", textAlign: "left", padding: "8px 12px",
              fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.06em",
              fontFamily: ff, cursor: "pointer", border: "none",
              background: active ? C.s2 : "transparent", color: active ? C.t1 : C.t3,
              borderLeft: active ? `2px solid ${C.accent}` : "2px solid transparent",
            }}>{c.label}</button>
          );
        })}
      </div>

      {/* RIGHT CONTENT */}
      <div style={content}>

        {/* ─── GENERAL ─── */}
        {cat === "general" && (
          <div>
            <div style={{ fontSize: "14px", fontWeight: 600, marginBottom: "4px" }}>General</div>
            <div style={{ ...sectionSx, marginTop: 0 }}>Appearance</div>
            <RadioRow label="Theme" value={s.theme} options={["dark", "light", "system"]} onChange={(v) => update("theme", v)} />
            <div style={rowSx}>
              <span style={labelSx}>Font Family</span>
              <select value={s.font} onChange={(e) => update("font", e.target.value as Settings["font"])} style={selectSx}>
                <option value="jetbrains">JetBrains Mono</option>
                <option value="fira">Fira Code</option>
                <option value="cascadia">Cascadia Code</option>
              </select>
            </div>
            <RadioRow label="Font Size" value={s.fontSize} options={[12, 14, 16, 18]} onChange={(v) => update("fontSize", v)} />
            <RadioRow label="Line Height" value={s.lineHeight} options={[1.2, 1.5, 1.8, 2.0]} onChange={(v) => update("lineHeight", v)} />
            <div style={sectionSx}>Editor</div>
            <CheckboxRow label="Word Wrap" checked={s.wordWrap} onChange={(v) => update("wordWrap", v)} />
            <CheckboxRow label="Minimap" checked={s.minimap} onChange={(v) => update("minimap", v)} />
            <CheckboxRow label="Breadcrumbs" checked={s.breadcrumbs} onChange={(v) => update("breadcrumbs", v)} />
          </div>
        )}

        {/* ─── AI / LLM ─── */}
        {cat === "ai" && (
          <div>
            <div style={{ fontSize: "14px", fontWeight: 600, marginBottom: "4px" }}>AI / LLM</div>
            <div style={{ ...sectionSx, marginTop: 0 }}>Provider</div>
            <div style={rowSx}>
              <span style={labelSx}>Primary Provider</span>
              <select value={s.primaryProvider} onChange={(e) => update("primaryProvider", e.target.value as Settings["primaryProvider"])} style={selectSx}>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
                <option value="ollama">Ollama</option>
              </select>
            </div>
            <div style={rowSx}>
              <span style={labelSx}>Fallback Provider</span>
              <select value={s.fallbackProvider} onChange={(e) => update("fallbackProvider", e.target.value as Settings["fallbackProvider"])} style={selectSx}>
                <option value="none">None</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
                <option value="ollama">Ollama</option>
              </select>
            </div>
            <div style={sectionSx}>API Keys</div>
            <div style={rowSx}>
              <span style={labelSx}>OpenAI API Key</span>
              <input type="password" value={s.openaiKey} onChange={(e) => update("openaiKey", e.target.value)} placeholder="sk-..." style={inputSx} />
            </div>
            <div style={rowSx}>
              <span style={labelSx}>Anthropic API Key</span>
              <input type="password" value={s.anthropicKey} onChange={(e) => update("anthropicKey", e.target.value)} placeholder="sk-ant-..." style={inputSx} />
            </div>
            <div style={rowSx}>
              <span style={labelSx}>Google API Key</span>
              <input type="password" value={s.googleKey} onChange={(e) => update("googleKey", e.target.value)} placeholder="AIza..." style={inputSx} />
            </div>
            <div style={rowSx}>
              <span style={labelSx}>Ollama URL</span>
              <input type="text" value={s.ollamaUrl} onChange={(e) => update("ollamaUrl", e.target.value)} placeholder="http://localhost:11434" style={inputSx} />
            </div>
            <div style={sectionSx}>Parameters</div>
            <SliderRow label="Temperature" value={s.temperature} min={0} max={1} step={0.05}
              display={s.temperature.toFixed(2)} onChange={(v) => update("temperature", v)} />
            <SliderRow label="Max Tokens" value={s.maxTokens} min={1000} max={128000} step={1000}
              display={`${(s.maxTokens / 1000).toFixed(0)}k`} onChange={(v) => update("maxTokens", v)} />
            <CheckboxRow label="Streaming" checked={s.streaming} onChange={(v) => update("streaming", v)} />
          </div>
        )}

        {/* ─── AGENT ─── */}
        {cat === "agent" && (
          <div>
            <div style={{ fontSize: "14px", fontWeight: 600, marginBottom: "4px" }}>Agent</div>
            <div style={{ ...sectionSx, marginTop: 0 }}>Behavior</div>
            <div style={rowSx}>
              <span style={labelSx}>Default Mode</span>
              <select value={s.agentMode} onChange={(e) => update("agentMode", e.target.value as Settings["agentMode"])} style={selectSx}>
                <option value="code">Code</option>
                <option value="architect">Architect</option>
                <option value="debug">Debug</option>
                <option value="review">Review</option>
                <option value="docs">Docs</option>
                <option value="test">Test</option>
              </select>
            </div>
            <CheckboxRow label="Auto-start Agent" checked={s.autoStart} onChange={(v) => update("autoStart", v)} />
            <CheckboxRow label="Background Execution" checked={s.backgroundExecution} onChange={(v) => update("backgroundExecution", v)} />
            <RadioRow label="Checkpoint Interval" value={s.checkpointInterval} options={[1, 5, 15, 30]} onChange={(v) => update("checkpointInterval", v)} />
            <div style={rowSx}>
              <span style={labelSx}>Max Retries</span>
              <input type="number" min={1} max={10} value={s.maxRetries} onChange={(e) => update("maxRetries", Number(e.target.value))} style={{ ...inputSx, width: "60px" }} />
            </div>
            <div style={sectionSx}>Approval Required</div>
            <CheckboxRow label="Delete Files" checked={s.approveDelete} onChange={(v) => update("approveDelete", v)} />
            <CheckboxRow label="Git Push" checked={s.approveGitPush} onChange={(v) => update("approveGitPush", v)} />
            <CheckboxRow label="Shell Commands" checked={s.approveShell} onChange={(v) => update("approveShell", v)} />
          </div>
        )}

        {/* ─── MEMORY ─── */}
        {cat === "memory" && (
          <div>
            <div style={{ fontSize: "14px", fontWeight: 600, marginBottom: "4px" }}>Memory</div>
            <div style={{ ...sectionSx, marginTop: 0 }}>Context</div>
            <div style={rowSx}>
              <span style={labelSx}>Max Conversations</span>
              <select value={s.maxConversations} onChange={(e) => update("maxConversations", Number(e.target.value) as Settings["maxConversations"])} style={selectSx}>
                <option value={100}>100</option>
                <option value={500}>500</option>
                <option value={1000}>1000</option>
              </select>
            </div>
            <CheckboxRow label="Auto-compact Context" checked={s.autoCompact} onChange={(v) => update("autoCompact", v)} />
            <RadioRow label="Compact Threshold" value={s.compactThreshold} options={[50, 70, 80, 90]} onChange={(v) => update("compactThreshold", v)} />
            <div style={sectionSx}>Data</div>
            <div style={{ display: "flex", gap: "8px", padding: "8px 0" }}>
              <button style={btnSx}>Export Memory</button>
              {!showClearConfirm ? (
                <button style={dangerBtnSx} onClick={() => setShowClearConfirm(true)}>Clear Memory</button>
              ) : (
                <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  <span style={{ fontSize: "10px", color: C.err }}>Are you sure?</span>
                  <button style={{ ...btnSx, padding: "4px 10px" }} onClick={() => setShowClearConfirm(false)}>Cancel</button>
                  <button style={{ ...dangerBtnSx, padding: "4px 10px" }} onClick={() => setShowClearConfirm(false)}>Confirm</button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── SECURITY ─── */}
        {cat === "security" && (
          <div>
            <div style={{ fontSize: "14px", fontWeight: 600, marginBottom: "4px" }}>Security</div>
            <div style={{ ...sectionSx, marginTop: 0 }}>Protection</div>
            <CheckboxRow label="AgentShield" checked={s.agentShield} onChange={(v) => update("agentShield", v)} />
            <CheckboxRow label="Auto-scan on Commit" checked={s.autoScanCommit} onChange={(v) => update("autoScanCommit", v)} />
            <CheckboxRow label="Secrets Detection" checked={s.secretsDetection} onChange={(v) => update("secretsDetection", v)} />
            <div style={sectionSx}>Audit Log</div>
            <div style={{ display: "flex", gap: "8px", padding: "8px 0" }}>
              <button style={btnSx}>View</button>
              <button style={btnSx}>Export</button>
              <button style={dangerBtnSx}>Clear</button>
            </div>
          </div>
        )}

        {/* ─── SHORTCUTS ─── */}
        {cat === "shortcuts" && (
          <div>
            <div style={{ fontSize: "14px", fontWeight: 600, marginBottom: "4px" }}>Shortcuts</div>
            <div style={{ ...sectionSx, marginTop: 0 }}>Keyboard Bindings</div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: ff }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.s2}` }}>
                  <th style={{ textAlign: "left", padding: "6px 8px", fontSize: "10px", textTransform: "uppercase", color: C.t3, letterSpacing: "0.06em" }}>Action</th>
                  <th style={{ textAlign: "right", padding: "6px 8px", fontSize: "10px", textTransform: "uppercase", color: C.t3, letterSpacing: "0.06em" }}>Key</th>
                </tr>
              </thead>
              <tbody>
                {SHORTCUTS.map((sc) => (
                  <tr key={sc.action} style={{ borderBottom: `1px solid ${C.s1}` }}>
                    <td style={{ padding: "6px 8px", fontSize: "11px", color: C.t1 }}>{sc.action}</td>
                    <td style={{ padding: "6px 8px", fontSize: "11px", color: C.t2, textAlign: "right", fontFamily: ff }}>
                      <kbd style={{ background: C.s1, padding: "2px 6px", fontSize: "10px", border: `1px solid ${C.s3}` }}>{sc.key}</kbd>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ padding: "16px 0" }}>
              <button style={btnSx}>Reset to Defaults</button>
            </div>
          </div>
        )}

        {/* ─── ADVANCED ─── */}
        {cat === "advanced" && (
          <div>
            <div style={{ fontSize: "14px", fontWeight: 600, marginBottom: "4px" }}>Advanced</div>
            <div style={{ ...sectionSx, marginTop: 0 }}>System</div>
            <div style={rowSx}>
              <span style={labelSx}>Backend Port</span>
              <input type="number" min={1024} max={65535} value={s.backendPort} onChange={(e) => update("backendPort", Number(e.target.value))} style={{ ...inputSx, width: "80px" }} />
            </div>
            <div style={rowSx}>
              <span style={labelSx}>Log Level</span>
              <select value={s.logLevel} onChange={(e) => update("logLevel", e.target.value as Settings["logLevel"])} style={selectSx}>
                <option value="debug">Debug</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
              </select>
            </div>
            <CheckboxRow label="Auto-update" checked={s.autoUpdate} onChange={(v) => update("autoUpdate", v)} />
            <CheckboxRow label="Beta Features" checked={s.betaFeatures} onChange={(v) => update("betaFeatures", v)} />
            <div style={sectionSx}>Danger Zone</div>
            <div style={{ padding: "8px 0" }}>
              {!showResetConfirm ? (
                <button style={dangerBtnSx} onClick={() => setShowResetConfirm(true)}>Reset All Settings</button>
              ) : (
                <div style={{ display: "flex", gap: "8px", alignItems: "center", background: C.s1, padding: "10px 12px" }}>
                  <span style={{ fontSize: "11px", color: C.err }}>This will reset all settings to defaults. Are you sure?</span>
                  <button style={{ ...btnSx, padding: "4px 10px" }} onClick={() => setShowResetConfirm(false)}>Cancel</button>
                  <button style={{ ...dangerBtnSx, padding: "4px 10px" }} onClick={() => { setS(DEFAULT_SETTINGS); setShowResetConfirm(false); }}>Confirm Reset</button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
