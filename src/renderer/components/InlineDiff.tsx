import { useState } from "react";
import { Check, X, FileCode } from "lucide-react";

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
  border: "rgba(255,255,255,0.04)",
};

const ff = '"Geist Mono", "JetBrains Mono", monospace';

/* ─────────────────────── types ─────────────────────── */

export interface DiffHunk {
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  lines: DiffLine[];
}

export interface DiffLine {
  type: "context" | "add" | "remove";
  content: string;
  lineNumber?: number;
}

export interface PendingChange {
  id: string;
  filePath: string;
  description: string;
  hunks: DiffHunk[];
  accepted: boolean | null; // null = pending, true = accepted, false = rejected
}

interface InlineDiffProps {
  changes: PendingChange[];
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onAcceptAll: () => void;
  onRejectAll: () => void;
}

/* ─────────────────────── sub-components ─────────────────────── */

function DiffLineView({ line }: { line: DiffLine }) {
  const bgColor =
    line.type === "add"
      ? "rgba(16,185,129,0.08)"
      : line.type === "remove"
      ? "rgba(239,68,68,0.08)"
      : "transparent";

  const gutterColor =
    line.type === "add"
      ? C.ok
      : line.type === "remove"
      ? C.err
      : C.t4;

  const sign =
    line.type === "add" ? "+" : line.type === "remove" ? "-" : " ";

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
        {line.lineNumber ?? ""}
      </span>
      {/* +/- sign */}
      <span
        style={{
          width: 14,
          paddingLeft: 4,
          color: gutterColor,
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
          color:
            line.type === "add"
              ? C.ok
              : line.type === "remove"
              ? C.err
              : C.t2,
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {line.content}
      </span>
    </div>
  );
}

function DiffHunkView({ hunk }: { hunk: DiffHunk }) {
  return (
    <div style={{ borderLeft: `2px solid ${C.accent}`, marginLeft: 8 }}>
      {/* Hunk header */}
      <div
        style={{
          padding: "2px 8px",
          fontFamily: ff,
          fontSize: 9,
          color: C.t4,
          backgroundColor: C.s1,
          borderTop: `1px solid ${C.border}`,
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        @@ -{hunk.oldStart},{hunk.oldLines} +{hunk.newStart},{hunk.newLines}
      </div>
      {/* Hunk lines */}
      {hunk.lines.map((line, i) => (
        <DiffLineView key={i} line={line} />
      ))}
    </div>
  );
}

function ChangeCard({
  change,
  onAccept,
  onReject,
  index,
}: {
  change: PendingChange;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  index: number;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div
      style={{
        border: `1px solid ${C.border}`,
        marginBottom: 4,
        backgroundColor: C.base,
      }}
    >
      {/* Change header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "4px 8px",
          backgroundColor: C.s1,
          cursor: "pointer",
          userSelect: "none",
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <span style={{ fontSize: 9, color: C.t4, fontFamily: ff }}>
          [{index + 1}]
        </span>
        <FileCode size={11} style={{ color: C.t3, flexShrink: 0 }} />
        <span
          style={{
            flex: 1,
            fontFamily: ff,
            fontSize: 10,
            color: C.t2,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={change.filePath}
        >
          {change.filePath}
        </span>
        <span
          style={{
            fontFamily: ff,
            fontSize: 9,
            color: C.t4,
            flexShrink: 0,
          }}
        >
          {change.hunks.reduce((acc, h) => acc + h.lines.length, 0)} lines
        </span>
        <span
          style={{
            fontSize: 8,
            color: C.t4,
            marginLeft: 4,
            transition: "transform 0.1s",
            transform: expanded ? "rotate(0deg)" : "rotate(-90deg)",
            display: "inline-block",
          }}
        >
          ▼
        </span>
      </div>

      {/* Expandable diff content */}
      {expanded && (
        <>
          {change.description && (
            <div
              style={{
                padding: "4px 8px",
                fontFamily: ff,
                fontSize: 10,
                color: C.t3,
                borderBottom: `1px solid ${C.border}`,
                fontStyle: "italic",
              }}
            >
              {change.description}
            </div>
          )}
          <div style={{ maxHeight: 200, overflow: "auto" }}>
            {change.hunks.map((hunk, i) => (
              <DiffHunkView key={i} hunk={hunk} />
            ))}
          </div>

          {/* Action buttons */}
          <div
            style={{
              display: "flex",
              gap: 6,
              padding: "4px 8px",
              borderTop: `1px solid ${C.border}`,
              justifyContent: "flex-end",
            }}
          >
            <ActionBtn
              icon={<X size={10} />}
              label="REJECT"
              color={C.err}
              onClick={() => onReject(change.id)}
            />
            <ActionBtn
              icon={<Check size={10} />}
              label="ACCEPT"
              color={C.ok}
              onClick={() => onAccept(change.id)}
            />
          </div>
        </>
      )}
    </div>
  );
}

function ActionBtn({
  icon,
  label,
  color,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  color: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 4,
        height: 20,
        padding: "0 8px",
        backgroundColor: "transparent",
        border: `1px solid ${color}33`,
        color: color,
        fontFamily: ff,
        fontSize: 9,
        fontWeight: 600,
        letterSpacing: "0.06em",
        cursor: "pointer",
        transition: "background-color 0.1s",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.backgroundColor = `${color}22`;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
      }}
    >
      {icon}
      {label}
    </button>
  );
}

/* ─────────────────────── main component ─────────────────────── */

function InlineDiff({
  changes,
  onAccept,
  onReject,
  onAcceptAll,
  onRejectAll,
}: InlineDiffProps) {
  const pendingCount = changes.filter((c) => c.accepted === null).length;

  if (changes.length === 0) return null;

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
      {/* Header with count + bulk actions */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "4px 8px",
          borderBottom: `1px solid ${C.border}`,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.06em",
            color: C.accent,
          }}
        >
          {pendingCount} pending {pendingCount === 1 ? "change" : "changes"}
        </span>
        {pendingCount > 0 && (
          <>
            <div style={{ flex: 1 }} />
            <BulkBtn label="REJECT ALL" color={C.err} onClick={onRejectAll} />
            <BulkBtn label="ACCEPT ALL" color={C.ok} onClick={onAcceptAll} />
          </>
        )}
      </div>

      {/* Changes list */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          padding: 4,
          scrollbarWidth: "thin",
          scrollbarColor: `${C.s3} transparent`,
        }}
      >
        {changes.map((change, i) => (
          <ChangeCard
            key={change.id}
            change={change}
            index={i}
            onAccept={onAccept}
            onReject={onReject}
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

function BulkBtn({
  label,
  color,
  onClick,
}: {
  label: string;
  color: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        height: 20,
        padding: "0 8px",
        backgroundColor: "transparent",
        border: `1px solid ${color}33`,
        color: color,
        fontFamily: ff,
        fontSize: 9,
        fontWeight: 600,
        letterSpacing: "0.06em",
        cursor: "pointer",
        transition: "background-color 0.1s",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.backgroundColor = `${color}22`;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
      }}
    >
      {label}
    </button>
  );
}

export default InlineDiff;
