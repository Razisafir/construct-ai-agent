import { useDiffStore } from "../stores/useDiffStore";
import { DiffViewer } from "./DiffViewer";

function DiffPanel() {
  const sessions = useDiffStore((s) => s.sessions);
  const activeSessionId = useDiffStore((s) => s.activeSessionId);
  const activeSession = activeSessionId ? sessions.get(activeSessionId) : null;

  if (!activeSession || activeSession.fileDiffs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full font-mono gap-2" style={{ color: "var(--c-text3)" }}>
        <span className="material-symbols-outlined text-2xl opacity-50" style={{ color: "var(--c-text4)" }}>commit</span>
        <span className="text-[11px] font-semibold tracking-wider">
          No pending changes
        </span>
        <span className="text-[10px]" style={{ color: "var(--c-text4)" }}>
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
    <div className="flex flex-col h-full bg-bg-onyx font-mono">
      <div
        className="flex items-center justify-between px-2 py-1 shrink-0"
        style={{ borderBottom: "1px solid var(--c-border)" }}
      >
        <div>
          <span className="text-[10px] font-semibold tracking-wider text-text-primary">CHANGES</span>
          <span className="text-[9px] ml-2" style={{ color: "var(--c-text4)" }}>session {activeSession.sessionId.slice(0, 8)}</span>
        </div>
        <div className="flex items-center gap-2">
          {pendingCount > 0 && (
            <span className="flex items-center gap-[3px] text-[9px] text-accent-gold">
              <span className="material-symbols-outlined text-[10px]">error_outline</span>
              {pendingCount} pending
            </span>
          )}
          {acceptedCount > 0 && (
            <span className="flex items-center gap-[3px] text-[9px] text-diff-add">
              <span className="material-symbols-outlined text-[10px]">check_circle</span>
              {acceptedCount} accepted
            </span>
          )}
          {rejectedCount > 0 && (
            <span className="flex items-center gap-[3px] text-[9px] text-diff-remove">
              <span className="material-symbols-outlined text-[10px]">cancel</span>
              {rejectedCount} rejected
            </span>
          )}
        </div>
      </div>
      <div
        className="flex-1 overflow-auto p-1"
        style={{ scrollbarWidth: "thin", scrollbarColor: "var(--c-s3) transparent" }}
      >
        {activeSession.fileDiffs.map((fileDiff) => (
          <DiffViewer key={fileDiff.filePath} sessionId={activeSession.id} fileDiff={fileDiff} />
        ))}
      </div>
    </div>
  );
}

export default DiffPanel;
