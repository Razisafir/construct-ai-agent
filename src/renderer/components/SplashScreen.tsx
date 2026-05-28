import { useState, useEffect } from "react";

const C = {
  base: "#0a0a10",
  s1: "#12121a",
  accent: "#6366f1",
  t1: "#e8e8ec",
  t3: "#6b6b73",
  t4: "#4a4a52",
};
const ff = '"Geist Mono", "JetBrains Mono", monospace';

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
    // Animate progress bar and cycle status messages
    const progressInterval = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) {
          clearInterval(progressInterval);
          return 100;
        }
        // Non-linear progress: slow at start, fast in middle, slow at end
        const increment = p < 30 ? 2 : p < 70 ? 5 : 1;
        return Math.min(100, p + increment);
      });
    }, 80);

    // Cycle status messages
    const statusInterval = setInterval(() => {
      setStatusIndex((i) => {
        if (i < STATUS_MESSAGES.length - 1) return i + 1;
        return i;
      });
    }, 400);

    // Check backend health
    checkBackend();

    return () => {
      clearInterval(progressInterval);
      clearInterval(statusInterval);
    };
  }, []);

  async function checkBackend() {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      const res = await fetch("http://localhost:8000/health", {
        signal: controller.signal,
      });
      clearTimeout(timeout);
      if (res.ok) {
        setPhase("ready");
        setProgress(100);
        setTimeout(onReady, 500); // Brief pause at 100%
      } else {
        // Backend not running — try to start it
        setPhase("starting-backend");
        startBackend();
      }
    } catch {
      setPhase("starting-backend");
      startBackend();
    }
  }

  async function startBackend() {
    // In production, this would invoke a Tauri command to start Python
    // For now, show error after attempts
    setAttempt((a) => a + 1);
    if (attempt >= 2) {
      setPhase("error");
      setError("Python backend is not running. Install dependencies and start agent-backend/app.py");
    } else {
      // Retry after delay
      setTimeout(checkBackend, 2000);
    }
  }

  if (phase === "ready") {
    return (
      <div style={{
        position: "fixed", inset: 0, background: C.base,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: ff, zIndex: 9999,
        opacity: progress >= 100 ? 0 : 1,
        transition: "opacity 300ms ease",
        pointerEvents: progress >= 100 ? "none" : "auto",
      }}>
        {/* Ready state — fade out */}
      </div>
    );
  }

  return (
    <div style={{
      position: "fixed", inset: 0, background: C.base,
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      fontFamily: ff, zIndex: 9999, gap: "24px",
    }}>
      {/* Logo — geometric C using CSS */}
      <div style={{
        width: "64px", height: "64px",
        border: "3px solid #e8e8ec",
        borderRight: "none",
        borderRadius: "50%",
        position: "relative",
      }}>
        <div style={{
          position: "absolute",
          top: "8px", left: "8px", right: "0", bottom: "8px",
          border: "2px solid #6366f1",
          borderRight: "none",
          borderRadius: "50%",
        }} />
      </div>

      {/* Title */}
      <div style={{ fontSize: "13px", fontWeight: 600, letterSpacing: "0.02em", color: C.t1 }}>
        CONSTRUCT
      </div>

      {/* Status */}
      <div style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: C.t3 }}>
        {phase === "starting-backend" ? "Starting backend..." : STATUS_MESSAGES[statusIndex]}
      </div>

      {/* Progress bar */}
      <div style={{ width: "200px", height: "2px", background: C.s1 }}>
        <div style={{
          width: `${progress}%`, height: "100%",
          background: C.accent,
          transition: "width 80ms linear",
        }} />
      </div>

      {/* Error state */}
      {phase === "error" && (
        <div style={{
          marginTop: "16px", padding: "12px",
          background: C.s1, border: "1px solid rgba(255,255,255,0.04)",
          maxWidth: "400px", textAlign: "center",
        }}>
          <div style={{ fontSize: "11px", color: "#ef4444", marginBottom: "8px" }}>
            {error}
          </div>
          <div style={{ display: "flex", gap: "8px", justifyContent: "center" }}>
            <button onClick={() => { setPhase("loading"); setAttempt(0); checkBackend(); }}
              style={{ padding: "4px 12px", background: C.s1, border: "1px solid rgba(255,255,255,0.04)", color: C.t3, fontFamily: ff, fontSize: "10px", textTransform: "uppercase", cursor: "pointer" }}>
              Retry
            </button>
            <button onClick={onReady}
              style={{ padding: "4px 12px", background: C.accent, border: "none", color: "#fff", fontFamily: ff, fontSize: "10px", textTransform: "uppercase", cursor: "pointer" }}>
              Continue Offline
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default SplashScreen;
