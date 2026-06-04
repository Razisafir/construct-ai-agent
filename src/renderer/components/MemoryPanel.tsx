import { useState, useCallback, useEffect } from "react";

/* ─────────────────────── types ─────────────────────── */

type MemoryType = "EPI" | "SEM" | "PRC" | "REF";

interface MemoryEntry {
  id: string;
  type: MemoryType;
  timestamp: string;
  relativeTime: string;
  source: string;
  content: string;
  fullContent: string;
  confidence?: number;
  relatedFiles?: string[];
}

interface MemoryState {
  entries: MemoryEntry[];
  selectedId: string | null;
  query: string;
}

/* ─────────────────────── colors ─────────────────────── */

const typeColor: Record<MemoryType, string> = {
  EPI: "#3b82f6",
  SEM: "#a855f7",
  PRC: "var(--c-gold)",
  REF: "var(--c-running)",
};

/* ─────────────────────── api helpers ─────────────────────── */

const API_BASE = "http://127.0.0.1:8000";

function mapSourceType(source: string): MemoryType {
  switch (source) {
    case "conversation":
      return "EPI";
    case "code":
      return "SEM";
    case "preference":
      return "PRC";
    default:
      return "REF";
  }
}

interface ApiMemoryResult {
  id: string;
  text: string;
  source: string;
  distance: number;
  relevance_score: number;
  metadata?: Record<string, unknown>;
}

function mapApiResult(item: ApiMemoryResult): MemoryEntry {
  const type = mapSourceType(item.source);
  const metadata = item.metadata ?? {};
  const now = new Date();
  const ts = typeof metadata.timestamp === "string" ? metadata.timestamp : now.toISOString();

  const relativeTime = (() => {
    try {
      const diff = now.getTime() - new Date(ts).getTime();
      const minutes = Math.floor(diff / 60000);
      if (minutes < 1) return "just now";
      if (minutes < 60) return `${minutes}m ago`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours}h ago`;
      const days = Math.floor(hours / 24);
      return `${days}d ago`;
    } catch {
      return "just now";
    }
  })();

  const truncatedContent =
    item.text.length > 80 ? item.text.slice(0, 80) + "..." : item.text;

  const relatedFiles: string[] | undefined =
    typeof metadata.file_path === "string" && metadata.file_path
      ? [metadata.file_path]
      : Array.isArray(metadata.related_files)
        ? (metadata.related_files as string[])
        : undefined;

  return {
    id: item.id,
    type,
    timestamp: ts,
    relativeTime,
    source: item.source || "--",
    content: truncatedContent,
    fullContent: item.text,
    confidence: item.relevance_score,
    relatedFiles,
  };
}

/* ─────────────────────── sub-components ─────────────────────── */

function TypeBadge({ type }: { type: MemoryType }) {
  return (
    <span
      className="text-[9px] font-bold tracking-wider inline-block text-center min-w-[28px] rounded-sm px-[5px] py-[1px] font-mono"
      style={{ color: typeColor[type], backgroundColor: "var(--c-s2)" }}
    >
      {type}
    </span>
  );
}

function SearchInput({
  value,
  onChange,
  onSearch,
}: {
  value: string;
  onChange: (v: string) => void;
  onSearch: () => void;
}) {
  return (
    <div
      className="flex items-center gap-1.5 px-3 py-1.5"
      style={{ borderBottom: "1px solid var(--c-border)" }}
    >
      <span className="text-[10px] uppercase tracking-wider font-mono" style={{ color: "var(--c-text4)" }}>
        QUERY:
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onSearch()}
        className="flex-1 px-2 py-[3px] text-[11px] font-mono outline-none rounded-none"
        style={{ backgroundColor: "var(--c-base)", border: "1px solid var(--c-border)", color: "var(--c-text)", caretColor: "var(--c-accent)" }}
        spellCheck={false}
        autoComplete="off"
      />
      <button
        onClick={onSearch}
        className="text-[10px] font-semibold uppercase tracking-wider px-2.5 py-[3px] cursor-pointer rounded-sm font-mono border-none"
        style={{ backgroundColor: "var(--c-s2)", color: "var(--c-text2)" }}
        onMouseEnter={(e) => { (e.target as HTMLElement).style.backgroundColor = "var(--c-s3)"; }}
        onMouseLeave={(e) => { (e.target as HTMLElement).style.backgroundColor = "var(--c-s2)"; }}
      >
        SEARCH
      </button>
    </div>
  );
}

function DetailPanel({ entry }: { entry: MemoryEntry }) {
  return (
    <div
      className="mx-3 my-1.5 px-2.5 py-2 font-mono"
      style={{ backgroundColor: "var(--c-s2)", border: "1px solid var(--c-border)" }}
    >
      {/* metadata row */}
      <div className="flex items-center gap-4 text-[10px] mb-1.5 flex-wrap" style={{ color: "var(--c-text3)" }}>
        <span>
          TYPE:{" "}
          <span style={{ color: typeColor[entry.type] }}>{entry.type}</span>
        </span>
        <span>
          TIME:{" "}
          <span style={{ color: "var(--c-text2)" }}>{entry.timestamp}</span>
        </span>
        <span>
          CONFIDENCE:{" "}
          <span style={{ color: "var(--c-text2)" }}>{(entry.confidence ?? 0).toFixed(2)}</span>
        </span>
        <span>
          SOURCE:{" "}
          <span style={{ color: "var(--c-text2)" }}>{entry.source}</span>
        </span>
      </div>

      {/* divider */}
      <div className="h-px my-1.5" style={{ backgroundColor: "var(--c-border)" }} />

      {/* content */}
      <div className="text-[11px] leading-4" style={{ color: "var(--c-text)", wordBreak: "break-word" }}>
        {entry.fullContent}
      </div>

      {/* related files */}
      {entry.relatedFiles && entry.relatedFiles.length > 0 && (
        <>
          <div className="h-px my-1.5" style={{ backgroundColor: "var(--c-border)" }} />
          <div className="text-[10px]" style={{ color: "var(--c-text3)" }}>
            RELATED:{" "}
            {entry.relatedFiles.map((f, i) => (
              <span key={f} style={{ color: "var(--c-text2)" }}>
                {f}
                {i < entry.relatedFiles!.length - 1 ? "  " : ""}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ─────────────────────── main component ─────────────────────── */

function MemoryPanel() {
  const [state, setState] = useState<MemoryState>({
    entries: [],
    selectedId: null,
    query: "",
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [totalMemories, setTotalMemories] = useState<number | null>(null);

  /* fetch stats on mount */
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/memory/stats`);
        if (res.ok) {
          const data = await res.json();
          setTotalMemories(
            typeof data.total_memories === "number" ? data.total_memories : null
          );
        }
      } catch {
        /* backend unreachable — keep totalMemories as null */
      }
    })();
  }, []);

  /* load recent memories on mount */
  useEffect(() => {
    loadRecent();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadRecent = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/memory/recent?limit=20`);
      if (res.ok) {
        const data = await res.json();
        const items: ApiMemoryResult[] = Array.isArray(data) ? data : (data.results ?? []);
        const entries: MemoryEntry[] = items.map(mapApiResult);
        setState((prev) => ({ ...prev, entries }));
      } else {
        setState((prev) => ({ ...prev, entries: [] }));
      }
    } catch {
      setState((prev) => ({ ...prev, entries: [] }));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSelect = useCallback((id: string) => {
    setState((prev) => ({
      ...prev,
      selectedId: prev.selectedId === id ? null : id,
    }));
  }, []);

  const handleSearch = useCallback(async () => {
    if (!state.query.trim()) {
      loadRecent();
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/memory/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: state.query,
          n_results: 20,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const items: ApiMemoryResult[] = Array.isArray(data) ? data : (data.results ?? []);
        const entries: MemoryEntry[] = items.map(mapApiResult);
        setState((prev) => ({ ...prev, entries }));
      } else {
        setState((prev) => ({ ...prev, entries: [] }));
      }
    } catch {
      setState((prev) => ({ ...prev, entries: [] }));
    } finally {
      setLoading(false);
    }
  }, [state.query, loadRecent]);

  const selectedEntry = state.entries.find((e) => e.id === state.selectedId);

  return (
    <div
      className="flex flex-col h-full overflow-hidden font-mono"
      style={{ backgroundColor: "var(--c-base)", border: "1px solid var(--c-border)" }}
    >
      {/* ── HEADER ── */}
      <div
        className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider flex justify-between items-center"
        style={{ color: "var(--c-text3)", borderBottom: "1px solid var(--c-border)" }}
      >
        <span>MEMORY</span>
        {totalMemories !== null && (
          <span style={{ color: "var(--c-text4)" }}>
            {totalMemories} entries
          </span>
        )}
      </div>

      {/* ── SEARCH ── */}
      <SearchInput
        value={state.query}
        onChange={(v) => setState((prev) => ({ ...prev, query: v }))}
        onSearch={handleSearch}
      />

      {/* ── TABLE HEADER ── */}
      <div
        className="grid gap-2 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider"
        style={{ gridTemplateColumns: "44px 80px 100px 1fr", color: "var(--c-text4)", borderBottom: "1px solid var(--c-border)" }}
      >
        <span>TYPE</span>
        <span>TIMESTAMP</span>
        <span>SOURCE</span>
        <span>CONTENT</span>
      </div>

      {/* ── TABLE BODY ── */}
      <div
        className="flex-1 overflow-auto"
        style={{ scrollbarWidth: "thin", scrollbarColor: "var(--c-s3) transparent" }}
      >
        {loading && (
          <div className="px-3 py-4 text-[10px] text-center" style={{ color: "var(--c-text4)" }}>
            loading...
          </div>
        )}

        {!loading &&
          state.entries.map((entry) => {
            const isSelected = state.selectedId === entry.id;
            return (
              <div key={entry.id}>
                <div
                  onClick={() => handleSelect(entry.id)}
                  className="grid gap-2 px-3 py-1 text-[11px] font-mono cursor-pointer items-center"
                  style={{
                    gridTemplateColumns: "44px 80px 100px 1fr",
                    color: "var(--c-text2)",
                    backgroundColor: isSelected ? "var(--c-s2)" : "transparent",
                    borderBottom: "1px solid var(--c-border)",
                    transition: "background-color 0.05s",
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = "var(--c-s1)";
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
                  }}
                >
                  <TypeBadge type={entry.type} />
                  <span className="text-[10px] whitespace-nowrap" style={{ color: "var(--c-text3)" }}>
                    {entry.relativeTime}
                  </span>
                  <span className="text-[10px] overflow-hidden text-ellipsis whitespace-nowrap" style={{ color: entry.source === "--" ? "var(--c-text4)" : "var(--c-text2)" }}>
                    {entry.source}
                  </span>
                  <span className="overflow-hidden text-ellipsis whitespace-nowrap" style={{ color: "var(--c-text2)" }}>
                    {entry.content}
                  </span>
                </div>

                {/* detail panel */}
                {isSelected && selectedEntry && (
                  <DetailPanel entry={selectedEntry} />
                )}
              </div>
            );
          })}

        {!loading && state.entries.length === 0 && (
          <div className="px-3 py-4 text-[10px] text-center" style={{ color: "var(--c-text4)" }}>
            no memories yet
          </div>
        )}
      </div>

      {/* scrollbar styles */}
      <style>{`
        div::-webkit-scrollbar { width: 4px; height: 4px; }
        div::-webkit-scrollbar-track { background: transparent; }
        div::-webkit-scrollbar-thumb { background: var(--c-s3); border-radius: 2px; }
        div::-webkit-scrollbar-thumb:hover { background: #3a3a4f; }
      `}</style>
    </div>
  );
}

export default MemoryPanel;
