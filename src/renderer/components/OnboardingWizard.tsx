import React, { useState } from "react";

const C = {
  base: "#0a0a10", s1: "#12121a", s2: "#1a1a24", s3: "#22222e",
  accent: "#6366f1", t1: "#e8e8ec", t2: "#94949c", t3: "#6b6b73", t4: "#4a4a52",
};

const ff = '"Geist Mono", "JetBrains Mono", monospace';

interface OnboardingWizardProps {
  onComplete: () => void;
  onSkip: () => void;
}

type Step = 1 | 2 | 3 | 4 | 5;

interface OnboardingState {
  projectPath: string;
  openaiKey: string;
  anthropicKey: string;
  googleKey: string;
  useLocalAI: boolean;
  theme: "dark" | "light" | "system";
  fontSize: "small" | "medium" | "large";
  agentMode: "code" | "architect" | "debug" | "review";
}

const stepLabels: Record<Step, string> = {
  1: "WELCOME", 2: "PROJECT", 3: "AI CONFIGURATION", 4: "PREFERENCES", 5: "READY",
};

const recentFolders = [
  { path: "~/workspace/acme", modified: "2d ago" },
  { path: "~/projects/my-app", modified: "1w ago" },
  { path: "/var/www/site", modified: "3w ago" },
];

const quickTips = [
  "Ctrl+Shift+P — command palette",
  "@filename — reference files in chat",
  "Agent works in background — check status bar",
];

export default function OnboardingWizard({ onComplete, onSkip }: OnboardingWizardProps) {
  const [step, setStep] = useState<Step>(1);
  const [state, setState] = useState<OnboardingState>({
    projectPath: "",
    openaiKey: "",
    anthropicKey: "",
    googleKey: "",
    useLocalAI: false,
    theme: "dark",
    fontSize: "medium",
    agentMode: "code",
  });

  const update = <K extends keyof OnboardingState>(key: K, val: OnboardingState[K]) =>
    setState((p) => ({ ...p, [key]: val }));

  const next = () => step < 5 && setStep((s) => (s + 1) as Step);
  const back = () => step > 1 && setStep((s) => (s - 1) as Step);

  // ─── Style Constants ───────────────────────────────────────────────

  const panel: React.CSSProperties = {
    width: 520, background: C.s1, border: `1px solid ${C.s3}`,
    borderRadius: 0, padding: "40px 44px",
  };

  const stepHeader: React.CSSProperties = {
    fontSize: 10, fontWeight: 500, letterSpacing: "0.08em",
    textTransform: "uppercase" as const, color: C.accent, marginBottom: 24,
  };

  const lbl: React.CSSProperties = {
    display: "block", fontSize: 10, fontWeight: 500,
    letterSpacing: "0.08em", textTransform: "uppercase" as const,
    color: C.t3, marginBottom: 6,
  };

  const inp: React.CSSProperties = {
    width: "100%", background: C.base, border: `1px solid ${C.s3}`,
    borderRadius: 0, padding: "9px 12px", fontSize: 11, fontFamily: ff,
    color: C.t1, outline: "none", boxSizing: "border-box",
  };

  const btnP: React.CSSProperties = {
    background: C.accent, color: "#fff", border: "none", borderRadius: 2,
    padding: "9px 20px", fontSize: 10, fontWeight: 600, fontFamily: ff,
    letterSpacing: "0.08em", textTransform: "uppercase" as const, cursor: "pointer",
  };

  const btnS: React.CSSProperties = {
    background: C.s2, color: C.t2, border: `1px solid ${C.s3}`,
    borderRadius: 2, padding: "9px 16px", fontSize: 10, fontWeight: 500,
    fontFamily: ff, letterSpacing: "0.08em", textTransform: "uppercase" as const,
    cursor: "pointer",
  };

  const btnF: React.CSSProperties = {
    background: "transparent", color: C.t3, border: "none", fontSize: 10,
    fontFamily: ff, letterSpacing: "0.06em", cursor: "pointer",
    padding: "6px 0", textDecoration: "underline", textUnderlineOffset: 3,
  };

  const optBtn = (active: boolean): React.CSSProperties => ({
    ...btnS, background: active ? C.accent : C.s2,
    color: active ? "#fff" : C.t2, borderColor: active ? C.accent : C.s3,
  });

  // ─── Step Renderers ────────────────────────────────────────────────

  const renderWelcome = () => (
    <div style={{ textAlign: "center", padding: "32px 0" }}>
      <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: "0.12em", color: C.t1, marginBottom: 10 }}>
        CONSTRUCT
      </div>
      <div style={{ fontSize: 11, color: C.t3, lineHeight: 1.4 }}>
        The AI that never forgets and never stops
      </div>
    </div>
  );

  const renderProject = () => (
    <div>
      <div style={lbl}>Project Path</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input
          type="text"
          value={state.projectPath}
          onChange={(e) => update("projectPath", e.target.value)}
          placeholder="/path/to/project"
          style={{ ...inp, flex: 1 }}
        />
        <button style={btnS} onClick={() => console.log("browse")}>Browse</button>
      </div>

      <div style={lbl}>Recent Folders</div>
      <div style={{ marginBottom: 20 }}>
        {recentFolders.map(({ path, modified }) => (
          <button
            key={path}
            onClick={() => update("projectPath", path)}
            style={{
              display: "flex", width: "100%", alignItems: "center",
              justifyContent: "space-between", textAlign: "left",
              background: "transparent", border: "none",
              borderBottom: `1px solid ${C.s2}`, padding: "8px 0",
              fontSize: 11, fontFamily: ff, color: C.t2, cursor: "pointer",
            }}
          >
            <span>{path}</span>
            <span style={{ fontSize: 10, color: C.t3 }}>{modified}</span>
          </button>
        ))}
      </div>

      <button style={btnF} onClick={() => update("projectPath", "~/new-project")}>
        Create new folder
      </button>
    </div>
  );

  const renderAIConfig = () => (
    <div>
      <div style={{ marginBottom: 16 }}>
        <div style={lbl}>OpenAI API Key</div>
        <input
          type="password"
          value={state.openaiKey}
          onChange={(e) => update("openaiKey", e.target.value)}
          placeholder="sk-..."
          style={inp}
        />
      </div>

      <div style={{ marginBottom: 16 }}>
        <div style={lbl}>Anthropic API Key</div>
        <input
          type="password"
          value={state.anthropicKey}
          onChange={(e) => update("anthropicKey", e.target.value)}
          placeholder="sk-ant-..."
          style={inp}
        />
      </div>

      <div style={{ marginBottom: 16 }}>
        <div style={lbl}>Google API Key</div>
        <input
          type="password"
          value={state.googleKey}
          onChange={(e) => update("googleKey", e.target.value)}
          placeholder="AIza..."
          style={inp}
        />
      </div>

      <div style={{ marginBottom: 20 }}>
        <label style={{
          display: "flex", alignItems: "center", gap: 8,
          cursor: "pointer", fontSize: 11, fontFamily: ff, color: C.t2,
        }}>
          <input
            type="checkbox"
            checked={state.useLocalAI}
            onChange={(e) => update("useLocalAI", e.target.checked)}
            style={{ accentColor: C.accent }}
          />
          Use Local AI (Ollama)
        </label>
        <div style={{ fontSize: 10, color: C.t3, marginLeft: 22, marginTop: 4 }}>
          Free, offline, no API keys needed
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <button style={btnS} onClick={() => console.log("test connection")}>
          Test Connection
        </button>
        <button style={btnF} onClick={next}>
          Skip for now
        </button>
      </div>
    </div>
  );

  const renderPreferences = () => (
    <div>
      <div style={{ marginBottom: 20 }}>
        <div style={lbl}>Theme</div>
        <div style={{ display: "flex", gap: 8 }}>
          {(["dark", "light", "system"] as const).map((t) => (
            <button key={t} onClick={() => update("theme", t)} style={optBtn(state.theme === t)}>
              {t}
            </button>
          ))}
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <div style={lbl}>Font Size</div>
        <div style={{ display: "flex", gap: 8 }}>
          {(["small", "medium", "large"] as const).map((s) => (
            <button key={s} onClick={() => update("fontSize", s)} style={optBtn(state.fontSize === s)}>
              {s}
            </button>
          ))}
        </div>
      </div>

      <div>
        <div style={lbl}>Agent Mode</div>
        <div style={{ display: "flex", gap: 8 }}>
          {(["code", "architect", "debug", "review"] as const).map((m) => (
            <button key={m} onClick={() => update("agentMode", m)} style={optBtn(state.agentMode === m)}>
              {m}
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  const renderReady = () => (
    <div>
      <div style={{ fontSize: 12, color: C.t2, marginBottom: 24, lineHeight: 1.5 }}>
        Construct is configured and ready to work
      </div>
      <div style={lbl}>Quick Tips</div>
      <div style={{ marginBottom: 24 }}>
        {quickTips.map((tip) => (
          <div
            key={tip}
            style={{
              fontSize: 11, color: C.t2, padding: "7px 0",
              borderBottom: `1px solid ${C.s2}`, fontFamily: ff,
            }}
          >
            {tip}
          </div>
        ))}
      </div>
    </div>
  );

  const renderStep = () => {
    switch (step) {
      case 1: return renderWelcome();
      case 2: return renderProject();
      case 3: return renderAIConfig();
      case 4: return renderPreferences();
      case 5: return renderReady();
    }
  };

  // ─── Main Render ───────────────────────────────────────────────────

  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", width: "100vw", height: "100vh",
      background: C.base, fontFamily: ff, color: C.t1,
    }}>
      <div style={panel}>
        {/* Step Indicator */}
        {step > 1 && (
          <div style={stepHeader}>
            [{step}/5] {stepLabels[step]}
          </div>
        )}

        {/* Step Content */}
        {renderStep()}

        {/* Navigation Bar */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          marginTop: 32, paddingTop: 20, borderTop: `1px solid ${C.s2}`,
        }}>
          <div style={{ display: "flex", gap: 10 }}>
            {step > 1 && (
              <button style={btnS} onClick={back}>
                &lt; Back
              </button>
            )}
            {step < 5 && (
              <button style={btnP} onClick={next}>
                Next &gt;
              </button>
            )}
            {step === 5 && (
              <button style={btnP} onClick={onComplete}>
                Launch Construct
              </button>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            {/* Progress Indicators */}
            <div style={{ display: "flex", gap: 5 }}>
              {([1, 2, 3, 4, 5] as Step[]).map((s) => (
                <div
                  key={s}
                  style={{
                    width: 7, height: 7, borderRadius: 1,
                    background: s === step ? C.accent : s < step ? C.t4 : C.s3,
                  }}
                />
              ))}
            </div>

            <button style={btnF} onClick={onSkip}>Skip</button>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div style={{ marginTop: 16, fontSize: 10, color: C.t3, letterSpacing: "0.06em", fontFamily: ff }}>
        Construct v1.0.0
      </div>
    </div>
  );
}
