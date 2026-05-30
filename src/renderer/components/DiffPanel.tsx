import { useDiffStore } from "../stores/useDiffStore";
import { DiffViewer } from "./DiffViewer";
import { GitPullRequest, CheckCircle, XCircle, AlertCircle } from "lucide-react";

const C = {
  base: "#0c0c10",
  s1: "#12121a",
  s2: "#1a1a24",
  s3: "#22222e",
  accent: "#6366f1",
  t1: "#e8e8ec",
  t2: "#94949c",
  t3: "#6b6b73",
  t4: "#4a4a52",
  ok: "#10b981",
  err: "#ef4444",
  wrn: "#f59e0b",
  border: "rgba(255,255,255,0.04)",
};

const ff = '"Geist Mono", "JetBrains Mono", monospace';

/* ─────────────────────── component ─────────────────────── */

function DiffPanel() {
  const sessions = useDiffStore((s) => s.sessions);
  const activeSessionId = useDiffStore((s) => s.activeSessionId);

  const activeSession = activeSessionId ? sessions.get(activeSessionId) : null;

  if (!activeSession || activeSession.fileDiffs.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          color: C.t3,
          fontFamily: ff,
          gap: 8,
        }}
      >
        <GitPullRequest size={24} style={{ color: C.t4, opacity: 0.5 }} />
        <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.06em" }}>
          No pending changes
        </span>
        <span style={{ fontSize: 10, color: C.t4 }}>
          Agent changes will appear here for review
        </span>
      </div>
    );
  }

  const pendingCount = activeSession.fileDiffs.reduce(
    (acc, fd) => acc + fd.hunks.filter((h) => h.accepted === null).length,
    0
  );

  const acceptedCount = activeSession.fileDiffs.reduce(
    (acc, fd) => acc + fd.hunks.filter((h) => h.accepted === true).length,
    0
  );

  const rejectedCount = activeSession.fileDiffs.reduce(
    (acc, fd) => acc + fd.hunks.filter((h) => h.accepted === false).length,
    0
  );

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        backgroundColor: C.base,
        fontFamily: ff,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "4px 8px",
          borderBottom: `1px solid ${C.border}`,
          flexShrink: 0,
        }}
      >
        <div>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              letterSpacing: "0.06em",
              color: C.t1,
            }}
          >
            CHANGES
          </span>
          <span
            style={{
              fontSize: 9,
              color: C.t4,
              marginLeft: 8,
            }}
          >
            session {activeSession.sessionId.slice(0, 8)}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {pendingCount > 0 && (
            <span
              style={{
                display: "flex",
                alignItems: "center",
                gap: 3,
                fontSize: 9,
                color: C.wrn,
              }}
            >
              <AlertCircle size={10} />
              {pendingCount} pending
            </span>
          )}
          {acceptedCount > 0 && (
            <span
              style={{
                display: "flex",
                alignItems: "center",
                gap: 3,
                fontSize: 9,
                color: C.ok,
              }}
            >
              <CheckCircle size={10} />
              {acceptedCount} accepted
            </span>
          )}
          {rejectedCount > 0 && (
            <span
              style={{
                display: "flex",
                alignItems: "center",
                gap: 3,
                fontSize: 9,
                color: C.err,
              }}
            >
              <XCircle size={10} />
              {rejectedCount} rejected
            </span>
          )}
        </div>
      </div>

      {/* File diffs */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          padding: 4,
          scrollbarWidth: "thin",
          scrollbarColor: `${C.s3} transparent`,
        }}
      >
        {activeSession.fileDiffs.map((fileDiff) => (
          <DiffViewer
            key={fileDiff.filePath}
            sessionId={activeSession.id}
            fileDiff={fileDiff}
          />
        ))}
      </div>

      {/* Scrollbar styles */}
      <style>{`
        div::-webkit-scrollbar { width: 4px; height: 4px; }
        div::-webkit-scrollbar-track { background: transparent; }
        div::-webkit-scrollbar-thumb { background: ${C.s3}; border-radius: 2px; }
      `}</style>
    </div>
  );
}

export default DiffPanel;
