import { useState } from "react";
import type { FileDiff, DiffHunk } from "../types/diff";
import { useDiffStore } from "../stores/useDiffStore";
import {
  Check,
  X,
  FileCode,
  FilePlus,
  FileMinus,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

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

/* ─────────────────────── sub-components ─────────────────────── */

function HunkActions({
  hunk,
  onAccept,
  onReject,
}: {
  hunk: DiffHunk;
  onAccept: () => void;
  onReject: () => void;
}) {
  if (hunk.accepted === true) {
    return (
      <span
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          fontSize: 10,
          color: C.ok,
          fontFamily: ff,
        }}
      >
        <Check size={11} />
        Accepted
      </span>
    );
  }

  if (hunk.accepted === false) {
    return (
      <span
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          fontSize: 10,
          color: C.err,
          fontFamily: ff,
        }}
      >
        <X size={11} />
        Rejected
      </span>
    );
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <button
        onClick={onAccept}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 3,
          padding: "2px 8px",
          backgroundColor: "transparent",
          border: `1px solid ${C.ok}33`,
          color: C.ok,
          fontFamily: ff,
          fontSize: 9,
          fontWeight: 600,
          letterSpacing: "0.06em",
          cursor: "pointer",
          transition: "background-color 0.1s",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLElement).style.backgroundColor = `${C.ok}22`;
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
        }}
      >
        <Check size={10} />
        ACCEPT
      </button>
      <button
        onClick={onReject}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 3,
          padding: "2px 8px",
          backgroundColor: "transparent",
          border: `1px solid ${C.err}33`,
          color: C.err,
          fontFamily: ff,
          fontSize: 9,
          fontWeight: 600,
          letterSpacing: "0.06em",
          cursor: "pointer",
          transition: "background-color 0.1s",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLElement).style.backgroundColor = `${C.err}22`;
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
        }}
      >
        <X size={10} />
        REJECT
      </button>
    </div>
  );
}

function DiffLineView({
  type,
  content,
  lineNum,
}: {
  type: "context" | "added" | "removed";
  content: string;
  lineNum: number;
}) {
  const bgColor =
    type === "added"
      ? "rgba(16,185,129,0.08)"
      : type === "removed"
        ? "rgba(239,68,68,0.08)"
        : "transparent";

  const textColor =
    type === "added" ? C.ok : type === "removed" ? C.err : C.t2;

  const sign = type === "added" ? "+" : type === "removed" ? "-" : " ";

  return (
    <div
      style={{
        display: "flex",
        fontFamily: ff,
        fontSize: 10,
        lineHeight: "16px",
        backgroundColor: bgColor,
        whiteSpace: "pre",
        overflow: "hidden",
      }}
    >
      {/* Line number gutter */}
      <span
        style={{
          width: 32,
          paddingLeft: 6,
          color: C.t4,
          flexShrink: 0,
          textAlign: "right",
          userSelect: "none",
        }}
      >
        {lineNum || ""}
      </span>
      {/* +/- sign */}
      <span
        style={{
          width: 14,
          paddingLeft: 4,
          color: textColor,
          flexShrink: 0,
          userSelect: "none",
          fontWeight: 600,
        }}
      >
        {sign}
      </span>
      {/* Code content */}
      <span
        style={{
          flex: 1,
          paddingLeft: 4,
          color: textColor,
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {content}
      </span>
    </div>
  );
}

function HunkView({
  hunk,
  filePath,
  sessionId,
}: {
  hunk: DiffHunk;
  filePath: string;
  sessionId: string;
}) {
  const acceptHunk = useDiffStore((s) => s.acceptHunk);
  const rejectHunk = useDiffStore((s) => s.rejectHunk);
  const [expanded, setExpanded] = useState(true);

  // Interleave old and new content for display
  const lines: {
    type: "context" | "added" | "removed";
    content: string;
    oldLine?: number;
    newLine?: number;
  }[] = [];

  let oldLineNum = hunk.oldStart;
  let newLineNum = hunk.newStart;

  // Simple interleaving: show removed then added, context lines once
  const maxLines = Math.max(hunk.oldContent.length, hunk.newContent.length);
  for (let idx = 0; idx < maxLines; idx++) {
    const oldLine = hunk.oldContent[idx];
    const newLine = hunk.newContent[idx];

    if (oldLine === newLine && oldLine !== undefined) {
      lines.push({
        type: "context",
        content: oldLine,
        oldLine: oldLineNum,
        newLine: newLineNum,
      });
      oldLineNum++;
      newLineNum++;
    } else {
      if (oldLine !== undefined) {
        lines.push({ type: "removed", content: oldLine, oldLine: oldLineNum });
        oldLineNum++;
      }
      if (newLine !== undefined) {
        lines.push({ type: "added", content: newLine, newLine: newLineNum });
        newLineNum++;
      }
    }
  }

  return (
    <div
      style={{
        border: `1px solid ${C.border}`,
        marginBottom: 4,
        backgroundColor: C.base,
      }}
    >
      {/* Hunk header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "3px 8px",
          backgroundColor: C.s1,
          borderBottom: `1px solid ${C.border}`,
          cursor: "pointer",
          userSelect: "none",
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {expanded ? (
            <ChevronDown size={10} style={{ color: C.t4 }} />
          ) : (
            <ChevronRight size={10} style={{ color: C.t4 }} />
          )}
          <span style={{ fontFamily: ff, fontSize: 9, color: C.t3 }}>
            {hunk.header}
          </span>
        </div>
        <div onClick={(e) => e.stopPropagation()}>
          <HunkActions
            hunk={hunk}
            onAccept={() => acceptHunk(sessionId, filePath, hunk.id)}
            onReject={() => rejectHunk(sessionId, filePath, hunk.id)}
          />
        </div>
      </div>

      {/* Hunk content */}
      {expanded && (
        <div
          style={{
            borderLeft: `2px solid ${C.accent}`,
            marginLeft: 8,
            maxHeight: 200,
            overflow: "auto",
            scrollbarWidth: "thin",
            scrollbarColor: `${C.s3} transparent`,
          }}
        >
          {lines.map((line, i) => (
            <DiffLineView
              key={i}
              type={line.type}
              content={line.content}
              lineNum={line.oldLine || line.newLine || 0}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FileIcon({ status }: { status: FileDiff["status"] }) {
  switch (status) {
    case "added":
      return <FilePlus size={11} style={{ color: C.ok, flexShrink: 0 }} />;
    case "deleted":
      return <FileMinus size={11} style={{ color: C.err, flexShrink: 0 }} />;
    default:
      return <FileCode size={11} style={{ color: C.t3, flexShrink: 0 }} />;
  }
}

/* ─────────────────────── main component ─────────────────────── */

export function DiffViewer({
  sessionId,
  fileDiff,
}: {
  sessionId: string;
  fileDiff: FileDiff;
}) {
  const acceptAll = useDiffStore((s) => s.acceptAll);
  const rejectAll = useDiffStore((s) => s.rejectAll);
  const pendingCount = fileDiff.hunks.filter((h) => h.accepted === null).length;

  return (
    <div>
      {/* File header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "4px 8px",
          backgroundColor: C.s1,
          border: `1px solid ${C.border}`,
          marginBottom: 4,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <FileIcon status={fileDiff.status} />
          <span
            style={{
              fontFamily: ff,
              fontSize: 10,
              color: C.t1,
              fontWeight: 600,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
            title={fileDiff.filePath}
          >
            {fileDiff.filePath}
          </span>
          <span style={{ fontFamily: ff, fontSize: 9, color: C.t4 }}>
            {fileDiff.hunks.length} hunks, {pendingCount} pending
          </span>
        </div>

        {pendingCount > 0 && (
          <div style={{ display: "flex", gap: 6 }}>
            <button
              onClick={() => rejectAll(sessionId)}
              style={{
                height: 18,
                padding: "0 6px",
                backgroundColor: "transparent",
                border: `1px solid ${C.err}33`,
                color: C.err,
                fontFamily: ff,
                fontSize: 8,
                fontWeight: 600,
                letterSpacing: "0.06em",
                cursor: "pointer",
                transition: "background-color 0.1s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.backgroundColor = `${C.err}22`;
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
              }}
            >
              REJECT ALL
            </button>
            <button
              onClick={() => acceptAll(sessionId)}
              style={{
                height: 18,
                padding: "0 6px",
                backgroundColor: "transparent",
                border: `1px solid ${C.ok}33`,
                color: C.ok,
                fontFamily: ff,
                fontSize: 8,
                fontWeight: 600,
                letterSpacing: "0.06em",
                cursor: "pointer",
                transition: "background-color 0.1s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.backgroundColor = `${C.ok}22`;
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
              }}
            >
              ACCEPT ALL
            </button>
          </div>
        )}
      </div>

      {/* Hunks */}
      {fileDiff.hunks.map((hunk) => (
        <HunkView
          key={hunk.id}
          hunk={hunk}
          filePath={fileDiff.filePath}
          sessionId={sessionId}
        />
      ))}
    </div>
  );
}
