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
  epi: "#3b82f6",
  sem: "#a855f7",
  prc: "#f59e0b",
  ref: "#22c55e",
};

const typeColor: Record<MemoryType, string> = {
  EPI: C.epi,
  SEM: C.sem,
  PRC: C.prc,
  REF: C.ref,
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
      style={{
        fontSize: "9px",
        fontWeight: 700,
        letterSpacing: "0.06em",
        color: typeColor[type],
        backgroundColor: C.s2,
        borderRadius: "2px",
        padding: "1px 5px",
        fontFamily: '"Geist Mono", "JetBrains Mono", monospace',
        minWidth: "28px",
        textAlign: "center",
        display: "inline-block",
      }}
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
      style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        padding: "6px 12px",
        borderBottom: "1px solid rgba(255,255,255,0.04)",
      }}
    >
      <span
        style={{
          fontSize: "10px",
          color: C.t4,
          fontFamily: '"Geist Mono", "JetBrains Mono", monospace',
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        QUERY:
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onSearch()}
        style={{
          flex: 1,
          backgroundColor: C.base,
          border: "1px solid rgba(255,255,255,0.04)",
          outline: "none",
          fontSize: "11px",
          color: C.t1,
          fontFamily: '"Geist Mono", "JetBrains Mono", monospace',
          padding: "3px 8px",
          borderRadius: "0px",
          caretColor: C.accent,
        }}
        spellCheck={false}
        autoComplete="off"
      />
      <button
        onClick={onSearch}
        style={{
          fontSize: "10px",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          backgroundColor: C.s2,
          color: C.t2,
          border: "1px solid rgba(255,255,255,0.04)",
          borderRadius: "2px",
          padding: "3px 10px",
          cursor: "pointer",
          fontFamily: '"Geist Mono", "JetBrains Mono", monospace',
        }}
        onMouseEnter={(e) => {
          (e.target as HTMLElement).style.backgroundColor = C.s3;
        }}
        onMouseLeave={(e) => {
          (e.target as HTMLElement).style.backgroundColor = C.s2;
        }}
      >
        SEARCH
      </button>
    </div>
  );
}

function DetailPanel({ entry }: { entry: MemoryEntry }) {
  return (
    <div
      style={{
        backgroundColor: C.s2,
        border: "1px solid rgba(255,255,255,0.04)",
        margin: "6px 12px 6px 12px",
        padding: "8px 10px",
        fontFamily: '"Geist Mono", "JetBrains Mono", monospace',
      }}
    >
      {/* metadata row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "16px",
          fontSize: "10px",
          color: C.t3,
          marginBottom: "6px",
          flexWrap: "wrap",
        }}
      >
        <span>
          TYPE:{" "}
          <span style={{ color: typeColor[entry.type] }}>{entry.type}</span>
        </span>
        <span>
          TIME:{" "}
          <span style={{ color: C.t2 }}>{entry.timestamp}</span>
        </span>
        <span>
          CONFIDENCE:{" "}
          <span style={{ color: C.t2 }}>{(entry.confidence ?? 0).toFixed(2)}</span>
        </span>
        <span>
          SOURCE:{" "}
          <span style={{ color: C.t2 }}>{entry.source}</span>
        </span>
      </div>

      {/* divider */}
      <div
        style={{
          height: "1px",
          backgroundColor: "rgba(255,255,255,0.04)",
          margin: "6px 0",
        }}
      />

      {/* content */}
      <div
        style={{
          fontSize: "11px",
          color: C.t1,
          lineHeight: "16px",
          wordBreak: "break-word",
        }}
      >
        {entry.fullContent}
      </div>

      {/* related files */}
      {entry.relatedFiles && entry.relatedFiles.length > 0 && (
        <>
          <div
            style={{
              height: "1px",
              backgroundColor: "rgba(255,255,255,0.04)",
              margin: "6px 0",
            }}
          />
          <div
            style={{
              fontSize: "10px",
              color: C.t3,
            }}
          >
            RELATED:{" "}
            {entry.relatedFiles.map((f, i) => (
              <span key={f} style={{ color: C.t2 }}>
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
        // API returns a flat array of SearchResultItem
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
        // API returns a flat array of SearchResultItem
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
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        backgroundColor: C.base,
        border: "1px solid rgba(255,255,255,0.04)",
        fontFamily: '"Geist Mono", "JetBrains Mono", monospace',
        overflow: "hidden",
      }}
    >
      {/* ── HEADER ── */}
      <div
        style={{
          padding: "8px 12px",
          fontSize: "10px",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: C.t3,
          borderBottom: "1px solid rgba(255,255,255,0.04)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span>MEMORY</span>
        {totalMemories !== null && (
          <span style={{ color: C.t4 }}>
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
        style={{
          display: "grid",
          gridTemplateColumns: "44px 80px 100px 1fr",
          gap: "8px",
          padding: "4px 12px",
          fontSize: "10px",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: C.t4,
          borderBottom: "1px solid rgba(255,255,255,0.04)",
        }}
      >
        <span>TYPE</span>
        <span>TIMESTAMP</span>
        <span>SOURCE</span>
        <span>CONTENT</span>
      </div>

      {/* ── TABLE BODY ── */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          scrollbarWidth: "thin",
          scrollbarColor: `${C.s3} transparent`,
        }}
      >
        {loading && (
          <div
            style={{
              padding: "16px 12px",
              fontSize: "10px",
              color: C.t4,
              textAlign: "center",
            }}
          >
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
                  style={{
                    display: "grid",
                    gridTemplateColumns: "44px 80px 100px 1fr",
                    gap: "8px",
                    padding: "4px 12px",
                    fontSize: "11px",
                    fontFamily: '"Geist Mono", "JetBrains Mono", monospace',
                    color: C.t2,
                    backgroundColor: isSelected ? C.s2 : "transparent",
                    borderBottom: "1px solid rgba(255,255,255,0.04)",
                    cursor: "pointer",
                    alignItems: "center",
                    transition: "background-color 0.05s",
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      (e.currentTarget as HTMLElement).style.backgroundColor = C.s1;
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
                    }
                  }}
                >
                  <TypeBadge type={entry.type} />
                  <span
                    style={{
                      fontSize: "10px",
                      color: C.t3,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {entry.relativeTime}
                  </span>
                  <span
                    style={{
                      fontSize: "10px",
                      color: entry.source === "--" ? C.t4 : C.t2,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {entry.source}
                  </span>
                  <span
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      color: C.t2,
                    }}
                  >
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
          <div
            style={{
              padding: "16px 12px",
              fontSize: "10px",
              color: C.t4,
              textAlign: "center",
            }}
          >
            no memories yet
          </div>
        )}
      </div>

      {/* scrollbar styles */}
      <style>{`
        div::-webkit-scrollbar { width: 4px; height: 4px; }
        div::-webkit-scrollbar-track { background: transparent; }
        div::-webkit-scrollbar-thumb { background: ${C.s3}; border-radius: 2px; }
        div::-webkit-scrollbar-thumb:hover { background: #3a3a4f; }
      `}</style>
    </div>
  );
}

export default MemoryPanel;
