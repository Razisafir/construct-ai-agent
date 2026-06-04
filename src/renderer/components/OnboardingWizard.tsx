import React, { useState, useEffect } from "react";

// Backend port — matches CONSTRUCT_PORT default
const BACKEND_PORT = 8000;

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
  const [llmConnected, setLlmConnected] = useState<boolean | null>(null); // null = checking
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

  // Detect LLM connection on mount
  useEffect(() => {
    const checkLlm = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:${BACKEND_PORT}/health`);
        const data = await res.json();
        setLlmConnected(data.llm_ready === true);
      } catch {
        setLlmConnected(false);
      }
    };
    checkLlm();
    // Re-check every 30 seconds in case the user starts Ollama
    const interval = setInterval(checkLlm, 30000);
    return () => clearInterval(interval);
  }, []);

  const update = <K extends keyof OnboardingState>(key: K, val: OnboardingState[K]) =>
    setState((p) => ({ ...p, [key]: val }));

  const next = () => step < 5 && setStep((s) => (s + 1) as Step);
  const back = () => step > 1 && setStep((s) => (s - 1) as Step);

  // ─── LLM Status Banner ────────────────────────────────────────────

  const renderLlmStatusBanner = () => {
    if (llmConnected === null) {
      return (
        <div className="border border-c-border rounded p-2.5 mb-4" style={{ background: "var(--c-s2)" }}>
          <p className="text-[10px] font-mono m-0" style={{ color: "var(--c-text3)" }}>
            Checking LLM connection...
          </p>
        </div>
      );
    }

    if (!llmConnected) {
      return (
        <div className="rounded p-2.5 mb-4" style={{ background: "var(--c-gold-dim)", border: "1px solid rgba(234, 179, 8, 0.25)" }}>
          <p className="text-[10px] font-semibold font-mono m-0 mb-1" style={{ color: "var(--c-gold)" }}>
            Demo Mode
          </p>
          <p className="text-[10px] font-mono m-0 leading-relaxed" style={{ color: "var(--c-text3)" }}>
            No LLM connected. Go to Settings to connect OpenAI, Anthropic, Ollama, or another
            provider to enable real agent execution. You can still explore the interface.
          </p>
        </div>
      );
    }

    return (
      <div className="rounded p-2.5 mb-4" style={{ background: "var(--c-running-bg)", border: "1px solid rgba(34, 197, 94, 0.25)" }}>
        <p className="text-[10px] font-semibold font-mono m-0 mb-1" style={{ color: "var(--c-running)" }}>
          Ready
        </p>
        <p className="text-[10px] font-mono m-0 leading-relaxed" style={{ color: "var(--c-text3)" }}>
          Agent is connected and ready. Type a goal to start.
        </p>
      </div>
    );
  };

  // ─── Step Renderers ────────────────────────────────────────────────

  const renderWelcome = () => (
    <div className="text-center py-8">
      <div className="text-sm font-bold tracking-widest" style={{ color: "var(--c-text)" }}>
        CONSTRUCT
      </div>
      <div className="text-[11px] leading-relaxed" style={{ color: "var(--c-text3)" }}>
        The AI that never forgets and never stops
      </div>
      {renderLlmStatusBanner()}
    </div>
  );

  const renderProject = () => (
    <div>
      {renderLlmStatusBanner()}
      <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>Project Path</div>
      <div className="flex gap-2 mb-5">
        <input
          type="text"
          value={state.projectPath}
          onChange={(e) => update("projectPath", e.target.value)}
          placeholder="/path/to/project"
          className="flex-1 px-3 py-2.5 text-[11px] font-mono bg-c-base border border-c-border outline-none rounded-sm"
          style={{ color: "var(--c-text)" }}
        />
        <button className="px-4 py-2.5 text-[10px] font-medium uppercase tracking-wider font-mono border cursor-pointer rounded-sm" style={{ background: "var(--c-s2)", color: "var(--c-text2)", borderColor: "var(--c-s3)" }} onClick={() => console.log("browse")}>Browse</button>
      </div>

      <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>Recent Folders</div>
      <div className="mb-5">
        {recentFolders.map(({ path, modified }) => (
          <button
            key={path}
            onClick={() => update("projectPath", path)}
            className="flex w-full items-center justify-between text-left bg-transparent border-none py-2 font-mono text-[11px] cursor-pointer"
            style={{ color: "var(--c-text2)", borderBottom: "1px solid var(--c-s2)" }}
          >
            <span>{path}</span>
            <span className="text-[10px]" style={{ color: "var(--c-text3)" }}>{modified}</span>
          </button>
        ))}
      </div>

      <button className="text-[10px] font-mono tracking-wider cursor-pointer underline underline-offset-1" style={{ background: "transparent", color: "var(--c-text3)", border: "none", padding: "6px 0" }} onClick={() => update("projectPath", "~/new-project")}>
        Create new folder
      </button>
    </div>
  );

  const renderAIConfig = () => (
    <div>
      {renderLlmStatusBanner()}
      <div className="mb-4">
        <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>OpenAI API Key</div>
        <input
          type="password"
          value={state.openaiKey}
          onChange={(e) => update("openaiKey", e.target.value)}
          placeholder="sk-..."
          className="w-full px-3 py-2.5 text-[11px] font-mono bg-c-base border border-c-border outline-none rounded-sm"
          style={{ color: "var(--c-text)" }}
        />
      </div>

      <div className="mb-4">
        <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>Anthropic API Key</div>
        <input
          type="password"
          value={state.anthropicKey}
          onChange={(e) => update("anthropicKey", e.target.value)}
          placeholder="sk-ant-..."
          className="w-full px-3 py-2.5 text-[11px] font-mono bg-c-base border border-c-border outline-none rounded-sm"
          style={{ color: "var(--c-text)" }}
        />
      </div>

      <div className="mb-4">
        <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>Google API Key</div>
        <input
          type="password"
          value={state.googleKey}
          onChange={(e) => update("googleKey", e.target.value)}
          placeholder="AIza..."
          className="w-full px-3 py-2.5 text-[11px] font-mono bg-c-base border border-c-border outline-none rounded-sm"
          style={{ color: "var(--c-text)" }}
        />
      </div>

      <div className="mb-5">
        <label className="flex items-center gap-2 cursor-pointer text-[11px] font-mono" style={{ color: "var(--c-text2)" }}>
          <input
            type="checkbox"
            checked={state.useLocalAI}
            onChange={(e) => update("useLocalAI", e.target.checked)}
            style={{ accentColor: "var(--c-accent)" }}
          />
          Use Local AI (Ollama)
        </label>
        <div className="text-[10px] ml-[22px] mt-1" style={{ color: "var(--c-text3)" }}>
          Free, offline, no API keys needed
        </div>
      </div>

      <div className="flex gap-2.5 items-center">
        <button
          className="px-4 py-2.5 text-[10px] font-medium uppercase tracking-wider font-mono border cursor-pointer rounded-sm"
          style={{ background: "var(--c-s2)", color: "var(--c-text2)", borderColor: "var(--c-s3)" }}
          onClick={async () => {
            try {
              const res = await fetch(`http://127.0.0.1:${BACKEND_PORT}/health`);
              const data = await res.json();
              setLlmConnected(data.llm_ready === true);
              alert(data.llm_ready ? "LLM connected!" : "No LLM detected. Start Ollama or configure an API key.");
            } catch {
              setLlmConnected(false);
              alert("Backend not reachable. Start the Python server first.");
            }
          }}
        >
          Test Connection
        </button>
        <button className="text-[10px] font-mono tracking-wider cursor-pointer underline underline-offset-1" style={{ background: "transparent", color: "var(--c-text3)", border: "none", padding: "6px 0" }} onClick={next}>
          Skip for now
        </button>
      </div>
    </div>
  );

  const optBtn = (active: boolean): React.CSSProperties => ({
    background: active ? "var(--c-accent)" : "var(--c-s2)",
    color: active ? "var(--c-base)" : "var(--c-text2)",
    borderColor: active ? "var(--c-accent)" : "var(--c-s3)",
  });

  const renderPreferences = () => (
    <div>
      {renderLlmStatusBanner()}
      <div className="mb-5">
        <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>Theme</div>
        <div className="flex gap-2">
          {(["dark", "light", "system"] as const).map((t) => (
            <button key={t} onClick={() => update("theme", t)} className="px-4 py-2.5 text-[10px] font-medium uppercase tracking-wider font-mono border-none rounded-sm cursor-pointer" style={optBtn(state.theme === t)}>
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-5">
        <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>Font Size</div>
        <div className="flex gap-2">
          {(["small", "medium", "large"] as const).map((s) => (
            <button key={s} onClick={() => update("fontSize", s)} className="px-4 py-2.5 text-[10px] font-medium uppercase tracking-wider font-mono border-none rounded-sm cursor-pointer" style={optBtn(state.fontSize === s)}>
              {s}
            </button>
          ))}
        </div>
      </div>

      <div>
        <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>Agent Mode</div>
        <div className="flex gap-2">
          {(["code", "architect", "debug", "review"] as const).map((m) => (
            <button key={m} onClick={() => update("agentMode", m)} className="px-4 py-2.5 text-[10px] font-medium uppercase tracking-wider font-mono border-none rounded-sm cursor-pointer" style={optBtn(state.agentMode === m)}>
              {m}
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  const renderReady = () => (
    <div>
      {renderLlmStatusBanner()}
      <div className="text-xs mb-6 leading-relaxed" style={{ color: "var(--c-text2)" }}>
        {llmConnected
          ? "Construct is configured and ready to work"
          : "Construct is in Demo Mode — connect an LLM in Settings to enable the agent"}
      </div>
      <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>Quick Tips</div>
      <div className="mb-6">
        {quickTips.map((tip) => (
          <div
            key={tip}
            className="text-[11px] font-mono py-[7px]"
            style={{ color: "var(--c-text2)", borderBottom: "1px solid var(--c-s2)" }}
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
    <div className="flex flex-col items-center justify-center w-screen h-screen font-mono" style={{ background: "var(--c-base)", color: "var(--c-text)" }}>
      <div className="border rounded-md" style={{ width: 520, background: "var(--c-s1)", borderColor: "var(--c-s3)", padding: "40px 44px" }}>
        {/* Step Indicator */}
        {step > 1 && (
          <div className="text-[10px] font-medium uppercase tracking-wider mb-6" style={{ color: "var(--c-accent)" }}>
            [{step}/5] {stepLabels[step]}
          </div>
        )}

        {/* Step Content */}
        {renderStep()}

        {/* Navigation Bar */}
        <div className="flex items-center justify-between mt-8 pt-5" style={{ borderTop: "1px solid var(--c-s2)" }}>
          <div className="flex gap-2.5">
            {step > 1 && (
              <button className="px-4 py-2.5 text-[10px] font-medium uppercase tracking-wider font-mono border cursor-pointer rounded-sm" style={{ background: "var(--c-s2)", color: "var(--c-text2)", borderColor: "var(--c-s3)" }} onClick={back}>
                &lt; Back
              </button>
            )}
            {step < 5 && (
              <button className="px-5 py-2.5 text-[10px] font-semibold uppercase tracking-wider font-mono border-none rounded-sm cursor-pointer" style={{ background: "var(--c-accent)", color: "var(--c-base)" }} onClick={next}>
                Next &gt;
              </button>
            )}
            {step === 5 && (
              <button className="px-5 py-2.5 text-[10px] font-semibold uppercase tracking-wider font-mono border-none rounded-sm cursor-pointer" style={{ background: "var(--c-accent)", color: "var(--c-base)" }} onClick={onComplete}>
                {llmConnected ? "Launch Construct" : "Continue in Demo Mode"}
              </button>
            )}
          </div>

          <div className="flex items-center gap-4">
            {/* Progress Indicators */}
            <div className="flex gap-[5px]">
              {([1, 2, 3, 4, 5] as Step[]).map((s) => (
                <div
                  key={s}
                  className="rounded-sm"
                  style={{
                    width: 7, height: 7,
                    background: s === step ? "var(--c-accent)" : s < step ? "var(--c-text4)" : "var(--c-s3)",
                  }}
                />
              ))}
            </div>

            <button className="text-[10px] font-mono tracking-wider cursor-pointer underline underline-offset-1" style={{ background: "transparent", color: "var(--c-text3)", border: "none", padding: "6px 0" }} onClick={onSkip}>Skip</button>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-4 text-[10px] font-mono tracking-wider" style={{ color: "var(--c-text3)" }}>
        Construct v0.1.0-beta
      </div>
    </div>
  );
}
