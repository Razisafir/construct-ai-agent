import { useState } from "react";

export interface DiffHunk_ {
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
  hunks: DiffHunk_[];
  accepted: boolean | null;
}

interface InlineDiffProps {
  changes: PendingChange[];
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onAcceptAll: () => void;
  onRejectAll: () => void;
}

function DiffLineView({ line }: { line: DiffLine }) {
  const bgColor =
    line.type === "add"
      ? "var(--c-ok-bg)"
      : line.type === "remove"
      ? "var(--c-err-bg)"
      : "transparent";

  const gutterColor =
    line.type === "add"
      ? "var(--c-ok)"
      : line.type === "remove"
      ? "var(--c-err)"
      : "var(--c-text4)";

  const sign = line.type === "add" ? "+" : line.type === "remove" ? "-" : " ";

  return (
    <div
      className="flex font-mono text-[10px] leading-4 whitespace-pre overflow-hidden"
      style={{ backgroundColor: bgColor }}
    >
      <span className="w-8 pl-1.5 shrink-0 text-right select-none" style={{ color: "var(--c-text4)" }}>
        {line.lineNumber ?? ""}
      </span>
      <span className="w-[14px] pl-1 shrink-0 select-none font-semibold" style={{ color: gutterColor }}>
        {sign}
      </span>
      <span className="flex-1 pl-1 overflow-hidden text-ellipsis" style={{ color: line.type === "add" ? "var(--c-ok)" : line.type === "remove" ? "var(--c-err)" : "var(--c-text2)" }}>
        {line.content}
      </span>
    </div>
  );
}

function DiffHunkView({ hunk }: { hunk: DiffHunk_ }) {
  return (
    <div className="ml-2" style={{ borderLeft: "2px solid var(--c-accent)" }}>
      <div className="py-[2px] px-2 font-mono text-[9px]" style={{ color: "var(--c-text4)", backgroundColor: "var(--c-s1)", borderTop: "1px solid var(--c-border)", borderBottom: "1px solid var(--c-border)" }}>
        @@ -{hunk.oldStart},{hunk.oldLines} +{hunk.newStart},{hunk.newLines}
      </div>
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
    <div className="border mb-1 bg-c-base rounded-md overflow-hidden" style={{ borderColor: "var(--c-border)" }}>
      <div
        className="flex items-center gap-2 px-2 py-1 cursor-pointer select-none"
        style={{ backgroundColor: "var(--c-s1)" }}
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-[9px] font-mono" style={{ color: "var(--c-text4)" }}>[{index + 1}]</span>
        <span className="material-symbols-outlined text-[11px] shrink-0" style={{ color: "var(--c-text3)" }}>description</span>
        <span className="flex-1 font-mono text-[10px] overflow-hidden text-ellipsis whitespace-nowrap" style={{ color: "var(--c-text2)" }} title={change.filePath}>{change.filePath}</span>
        <span className="font-mono text-[9px] shrink-0" style={{ color: "var(--c-text4)" }}>{change.hunks.reduce((acc, h) => acc + h.lines.length, 0)} lines</span>
        <span className="text-[8px] ml-1 inline-block" style={{ color: "var(--c-text4)", transform: expanded ? "rotate(0deg)" : "rotate(-90deg)", transition: "transform 0.1s" }}>▼</span>
      </div>

      {expanded && (
        <>
          {change.description && (
            <div className="px-2 py-1 font-mono text-[10px] italic" style={{ color: "var(--c-text3)", borderBottom: "1px solid var(--c-border)" }}>{change.description}</div>
          )}
          <div className="max-h-[200px] overflow-auto">
            {change.hunks.map((hunk, i) => (<DiffHunkView key={i} hunk={hunk} />))}
          </div>
          <div className="flex gap-1.5 px-2 py-1 justify-end" style={{ borderTop: "1px solid var(--c-border)" }}>
            <button onClick={() => onReject(change.id)} className="flex items-center gap-1 h-5 px-2 bg-transparent border font-mono text-[9px] font-semibold tracking-wider cursor-pointer rounded" style={{ borderColor: "rgba(248,113,113,0.2)", color: "var(--c-err)" }}>
              <span className="material-symbols-outlined text-[10px]">close</span> REJECT
            </button>
            <button onClick={() => onAccept(change.id)} className="flex items-center gap-1 h-5 px-2 bg-transparent border font-mono text-[9px] font-semibold tracking-wider cursor-pointer rounded" style={{ borderColor: "rgba(74,222,128,0.2)", color: "var(--c-ok)" }}>
              <span className="material-symbols-outlined text-[10px]">check</span> ACCEPT
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function InlineDiff({ changes, onAccept, onReject, onAcceptAll, onRejectAll }: InlineDiffProps) {
  const pendingCount = changes.filter((c) => c.accepted === null).length;
  if (changes.length === 0) return null;

  return (
    <div className="flex flex-col h-full bg-bg-onyx font-mono">
      <div className="flex items-center gap-2 px-2 py-1 shrink-0" style={{ borderBottom: "1px solid var(--c-border)" }}>
        <span className="text-[10px] font-semibold tracking-wider text-accent-cyan">
          {pendingCount} pending {pendingCount === 1 ? "change" : "changes"}
        </span>
        {pendingCount > 0 && (
          <>
            <div className="flex-1" />
            <button onClick={onRejectAll} className="h-5 px-2 bg-transparent border font-mono text-[9px] font-semibold tracking-wider cursor-pointer rounded" style={{ borderColor: "rgba(248,113,113,0.2)", color: "var(--c-err)" }}>REJECT ALL</button>
            <button onClick={onAcceptAll} className="h-5 px-2 bg-transparent border font-mono text-[9px] font-semibold tracking-wider cursor-pointer rounded" style={{ borderColor: "rgba(74,222,128,0.2)", color: "var(--c-ok)" }}>ACCEPT ALL</button>
          </>
        )}
      </div>
      <div className="flex-1 overflow-auto p-1" style={{ scrollbarWidth: "thin", scrollbarColor: "var(--c-s3) transparent" }}>
        {changes.map((change, i) => (<ChangeCard key={change.id} change={change} index={i} onAccept={onAccept} onReject={onReject} />))}
      </div>
    </div>
  );
}

export default InlineDiff;
