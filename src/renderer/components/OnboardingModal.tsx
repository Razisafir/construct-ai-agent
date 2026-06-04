import { useState, useCallback } from "react";

interface OnboardingModalProps {
  onComplete?: () => void;
}

export default function OnboardingModal({ onComplete }: OnboardingModalProps) {
  const [step, setStep] = useState(0);
  const [projectPath, setProjectPath] = useState("");
  const [goal, setGoal] = useState("");
  const [llmProvider, setLlmProvider] = useState<"local" | "claude">("local");
  const [theme, setTheme] = useState<"dark" | "light" | "system">("dark");

  const totalSteps = 5;

  const goNext = useCallback(() => {
    if (step < totalSteps - 1) {
      setStep((s) => s + 1);
    }
  }, [step]);

  const goBack = useCallback(() => {
    if (step > 0) {
      setStep((s) => s - 1);
    }
  }, [step]);

  const handleSkip = useCallback(() => {
    onComplete?.();
  }, [onComplete]);

  const handleFinish = useCallback(() => {
    try {
      localStorage.setItem("construct_onboarding_complete", "true");
      localStorage.setItem("construct_theme", theme);
      localStorage.setItem("construct_llm", llmProvider);
      localStorage.setItem("construct_project_path", projectPath);
      localStorage.setItem("construct_goal", goal);
    } catch {
      // ignore storage errors
    }
    onComplete?.();
  }, [onComplete, theme, llmProvider, projectPath, goal]);

  const renderStep = () => {
    switch (step) {
      case 0:
        return (
          <div className="flex flex-col gap-3">
            <div className="text-[10px] text-c-text3 uppercase tracking-wider">
              [{step + 1}/{totalSteps}] Project
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-c-text3 uppercase tracking-wider min-w-[36px]">
                Path
              </span>
              <input
                type="text"
                value={projectPath}
                onChange={(e) => setProjectPath(e.target.value)}
                placeholder="/home/user/project"
                className="flex-1 px-2.5 py-1.5 text-[11px] font-mono bg-c-s1 text-c-text border border-c-border outline-none rounded-sm"
              />
              <button
                onClick={() => setProjectPath("/home/user/project")}
                className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider bg-c-s2 text-c-text2 border-none rounded-sm cursor-pointer"
              >
                Browse
              </button>
            </div>
          </div>
        );

      case 1:
        return (
          <div className="flex flex-col gap-3">
            <div className="text-[10px] text-c-text3 uppercase tracking-wider">
              [{step + 1}/{totalSteps}] Goal
            </div>
            <input
              type="text"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="Describe what you want to build..."
              className="w-full px-2.5 py-1.5 text-[11px] font-mono bg-c-s1 text-c-text border border-c-border outline-none rounded-sm"
            />
          </div>
        );

      case 2:
        return (
          <div className="flex flex-col gap-3">
            <div className="text-[10px] text-c-text3 uppercase tracking-wider">
              [{step + 1}/{totalSteps}] LLM Provider
            </div>
            <div className="flex flex-col gap-2">
              <button
                onClick={() => setLlmProvider("local")}
                className="flex items-center gap-2 px-2.5 py-2 text-[11px] font-mono border cursor-pointer text-left rounded-sm"
                style={{
                  background: llmProvider === "local" ? "var(--c-s2)" : "transparent",
                  color: llmProvider === "local" ? "var(--c-text)" : "var(--c-text3)",
                  borderColor: llmProvider === "local" ? "var(--c-border)" : "transparent",
                }}
              >
                <span style={{ color: llmProvider === "local" ? "var(--c-accent)" : "var(--c-text4)" }}>
                  {llmProvider === "local" ? "◉" : "○"}
                </span>
                <span>Local (Ollama)</span>
              </button>
              <button
                onClick={() => setLlmProvider("claude")}
                className="flex items-center gap-2 px-2.5 py-2 text-[11px] font-mono border cursor-pointer text-left rounded-sm"
                style={{
                  background: llmProvider === "claude" ? "var(--c-s2)" : "transparent",
                  color: llmProvider === "claude" ? "var(--c-text)" : "var(--c-text3)",
                  borderColor: llmProvider === "claude" ? "var(--c-border)" : "transparent",
                }}
              >
                <span style={{ color: llmProvider === "claude" ? "var(--c-accent)" : "var(--c-text4)" }}>
                  {llmProvider === "claude" ? "◉" : "○"}
                </span>
                <span>Claude (API key required)</span>
              </button>
            </div>
          </div>
        );

      case 3:
        return (
          <div className="flex flex-col gap-3">
            <div className="text-[10px] text-c-text3 uppercase tracking-wider">
              [{step + 1}/{totalSteps}] Theme
            </div>
            <div className="flex flex-col gap-2">
              {(["dark", "light", "system"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTheme(t)}
                  className="flex items-center gap-2 px-2.5 py-2 text-[11px] font-mono border cursor-pointer text-left capitalize rounded-sm"
                  style={{
                    background: theme === t ? "var(--c-s2)" : "transparent",
                    color: theme === t ? "var(--c-text)" : "var(--c-text3)",
                    borderColor: theme === t ? "var(--c-border)" : "transparent",
                  }}
                >
                  <span style={{ color: theme === t ? "var(--c-accent)" : "var(--c-text4)" }}>
                    {theme === t ? "◉" : "○"}
                  </span>
                  <span>{t}</span>
                </button>
              ))}
            </div>
          </div>
        );

      case 4:
        return (
          <div className="flex flex-col gap-3">
            <div className="text-[10px] text-c-text3 uppercase tracking-wider">
              [{step + 1}/{totalSteps}] Ready
            </div>
            <div className="text-[11px] text-c-text2 leading-relaxed">
              <div>All set. Press Enter to begin.</div>
              <div className="mt-2 flex flex-col gap-1">
                <div className="flex justify-between">
                  <span className="text-c-text3">Project</span>
                  <span className="text-c-text4">{projectPath || "Not set"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-c-text3">Goal</span>
                  <span className="text-c-text4">{goal || "Not set"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-c-text3">LLM</span>
                  <span className="text-c-text4">{llmProvider === "local" ? "Ollama" : "Claude"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-c-text3">Theme</span>
                  <span className="text-c-text4 capitalize">{theme}</span>
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 font-mono">
      <div className="w-full max-w-[480px] mx-4 bg-c-base border border-c-border flex flex-col rounded-md">
        {/* Title Section */}
        <div className="px-6 pt-5 pb-2 text-center">
          <div className="text-sm font-bold text-c-text tracking-wider uppercase">
            CONSTRUCT
          </div>
          <div className="text-[11px] text-c-text2 mt-1">
            Autonomous AI coding agent
          </div>
        </div>

        {/* Divider */}
        <div className="mx-6 my-2 border-t border-c-border" />

        {/* Step Content */}
        <div className="px-6 py-4 min-h-[140px]">
          {renderStep()}
        </div>

        {/* Divider */}
        <div className="mx-6 my-2 border-t border-c-border" />

        {/* Footer Buttons */}
        <div className="flex items-center justify-between px-6 py-2 pb-4">
          <button
            onClick={goBack}
            disabled={step === 0}
            className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider font-medium border-none rounded-sm"
            style={{
              background: "var(--c-s2)",
              color: step === 0 ? "var(--c-text4)" : "var(--c-text2)",
              cursor: step === 0 ? "default" : "pointer",
            }}
          >
            {" < Back "}
          </button>

          <button
            onClick={handleSkip}
            className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider font-medium bg-transparent text-c-text3 border-none cursor-pointer"
          >
            Skip
          </button>

          {step === totalSteps - 1 ? (
            <button
              onClick={handleFinish}
              className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider font-medium bg-c-accent text-c-base border-none rounded-sm cursor-pointer"
            >
              Begin
            </button>
          ) : (
            <button
              onClick={goNext}
              className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider font-medium border-none rounded-sm cursor-pointer"
              style={{ background: "var(--c-s2)", color: "var(--c-text)" }}
            >
              {" Next > "}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
