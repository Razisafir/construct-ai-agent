import { useState, useEffect } from "react";

interface SplashScreenProps {
  onReady: () => void;
}

type SplashPhase = "loading" | "starting-backend" | "error" | "ready";

const STATUS_MESSAGES = [
  "Loading memory system...",
  "Connecting to agent backend...",
  "Scanning project files...",
  "Initializing tool registry...",
  "Loading skills library...",
  "Ready",
];

export function SplashScreen({ onReady }: SplashScreenProps) {
  const [phase, setPhase] = useState<SplashPhase>("loading");
  const [progress, setProgress] = useState(0);
  const [statusIndex, setStatusIndex] = useState(0);
  const [error, setError] = useState<string>("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const progressInterval = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) { clearInterval(progressInterval); return 100; }
        const increment = p < 30 ? 2 : p < 70 ? 5 : 1;
        return Math.min(100, p + increment);
      });
    }, 80);

    const statusInterval = setInterval(() => {
      setStatusIndex((i) => { if (i < STATUS_MESSAGES.length - 1) return i + 1; return i; });
    }, 400);

    checkBackend();

    return () => { clearInterval(progressInterval); clearInterval(statusInterval); };
  }, []);

  async function checkBackend() {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      const res = await fetch("http://localhost:8000/health", { signal: controller.signal });
      clearTimeout(timeout);
      if (res.ok) { setPhase("ready"); setProgress(100); setTimeout(onReady, 500); }
      else { setPhase("starting-backend"); startBackend(); }
    } catch { setPhase("starting-backend"); startBackend(); }
  }

  async function startBackend() {
    setAttempt((a) => a + 1);
    if (attempt >= 2) { setPhase("error"); setError("Python backend is not running. Install dependencies and start agent-backend/app.py"); }
    else { setTimeout(checkBackend, 2000); }
  }

  if (phase === "ready") {
    return (
      <div className="fixed inset-0 flex items-center justify-center font-mono z-[9999]" style={{ background: "var(--c-base)", opacity: progress >= 100 ? 0 : 1, transition: "opacity 300ms ease", pointerEvents: progress >= 100 ? "none" : "auto" as const }}>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center font-mono z-[9999] gap-6" style={{ background: "var(--c-base)" }}>
      {/* Logo */}
      <div className="w-16 h-16 border-[3px] border-r-0 rounded-full relative" style={{ borderColor: "var(--c-text)", borderRight: "none" }}>
        <div className="absolute top-2 left-2 right-0 bottom-2 border-2 border-r-0 rounded-full" style={{ borderColor: "var(--c-accent)", borderRight: "none" }} />
      </div>

      <div className="text-[13px] font-semibold tracking-wider" style={{ color: "var(--c-text)" }}>
        CONSTRUCT
      </div>

      <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--c-text3)" }}>
        {phase === "starting-backend" ? "Starting backend..." : STATUS_MESSAGES[statusIndex]}
      </div>

      <div className="w-[200px] h-[2px]" style={{ background: "var(--c-s1)" }}>
        <div className="h-full" style={{ width: `${progress}%`, background: "var(--c-accent)", transition: "width 80ms linear" }} />
      </div>

      {phase === "error" && (
        <div className="mt-4 p-3 max-w-[400px] text-center" style={{ background: "var(--c-s1)", border: "1px solid var(--c-border)" }}>
          <div className="text-[11px] mb-2" style={{ color: "var(--c-err)" }}>
            {error}
          </div>
          <div className="flex gap-2 justify-center">
            <button onClick={() => { setPhase("loading"); setAttempt(0); checkBackend(); }}
              className="px-3 py-1 text-[10px] font-mono uppercase cursor-pointer" style={{ background: "var(--c-s1)", border: "1px solid var(--c-border)", color: "var(--c-text3)" }}>
              Retry
            </button>
            <button onClick={onReady}
              className="px-3 py-1 text-[10px] font-mono uppercase cursor-pointer border-none" style={{ background: "var(--c-accent)", color: "var(--c-base)" }}>
              Continue Offline
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default SplashScreen;
