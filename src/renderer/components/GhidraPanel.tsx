/**
 * GhidraPanel — Binary analysis interface for CONSTRUCT IDE.
 *
 * Provides Ghidra integration UI with drag-and-drop binary loading,
 * real-time analysis progress, risk assessment, function/string/import
 * browsing, and decompiled C code viewing.
 *
 * Sub-components:
 * - BinaryDropZone: Drag-and-drop zone for binary files
 * - AnalysisProgress: Real-time progress bar with phase labels
 * - RiskAssessment: Severity-ordered risk findings with actions
 * - FunctionList: Sortable, filterable, searchable function table
 * - StringAnalysis: Categorized strings table with search/filter
 * - DecompiledView: C syntax-highlighted code viewer
 * - ImportTable: Imports grouped by DLL/library
 */

import { useState, useEffect, useCallback, useRef } from "react";

const BACKEND_URL = "http://127.0.0.1:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GhidraAnalysisResult {
  binary_path: string;
  metadata: Record<string, any>;
  functions: Array<{
    name: string;
    address: string;
    size: number;
    tags: string[];
    return_type?: string;
    parameter_count?: number;
    is_external?: boolean;
  }>;
  strings: Array<{
    value: string;
    address: string;
    length: number;
    category: string;
  }>;
  imports: Array<{
    name: string;
    address: string;
    library: string;
  }>;
  sections: Array<{
    name: string;
    start: string;
    end: string;
    size: number;
    permissions: string;
  }>;
  risk_indicators: Array<{
    severity: string;
    category: string;
    description: string;
    address?: string;
    function_name?: string;
    evidence?: string;
    recommendation?: string;
  }>;
  decompiled_functions: Array<{
    function_name: string;
    address: string;
    c_code: string;
    signature?: string;
  }>;
  status: string;
  progress_percent: number;
  error?: string;
  analysis_id?: string;
}

interface DecompileResult {
  pseudocode: string;
  language: string;
  function_name: string;
  address: string;
  signature: string;
}

type WsEvent =
  | { type: "progress"; phase: string; percent: number; message: string }
  | { type: "complete"; result: GhidraAnalysisResult }
  | { type: "error"; message: string };

type GhidraSubTab = "dropzone" | "progress" | "risk" | "functions" | "strings" | "decompiled" | "imports";

const ANALYSIS_PHASES = [
  { key: "import", label: "Import", icon: "upload_file" },
  { key: "analysis", label: "Analysis", icon: "psychology" },
  { key: "functions", label: "Functions", icon: "functions" },
  { key: "strings", label: "Strings", icon: "text_fields" },
  { key: "decompilation", label: "Decompilation", icon: "code" },
  { key: "report", label: "Report", icon: "summarize" },
];

const ACCEPTED_EXTENSIONS = [".exe", ".dll", ".elf", ".apk", ".so", ".dylib"];

const SEVERITY_ORDER: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

const SEVERITY_COLORS: Record<string, { text: string; bg: string; border: string }> = {
  CRITICAL: { text: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20" },
  HIGH: { text: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20" },
  MEDIUM: { text: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/20" },
  LOW: { text: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20" },
};

const STRING_CATEGORY_COLORS: Record<string, string> = {
  URL: "text-accent-cyan",
  API_KEY: "text-red-400",
  CRYPTO: "text-purple-400",
  SUSPICIOUS: "text-amber-400",
  MUTEX: "text-emerald-400",
  PATH: "text-blue-400",
  REGISTRY: "text-pink-400",
  COMMAND: "text-orange-400",
  NETWORK: "text-cyan-400",
  DEFAULT: "text-text-secondary",
};

const TAG_COLORS: Record<string, { text: string; bg: string }> = {
  suspicious: { text: "text-amber-400", bg: "bg-amber-500/10" },
  crypto: { text: "text-purple-400", bg: "bg-purple-500/10" },
  network: { text: "text-cyan-400", bg: "bg-cyan-500/10" },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function severityBadge(severity: string) {
  const colors = SEVERITY_COLORS[severity.toUpperCase()] ?? SEVERITY_COLORS.LOW;
  return (
    <span
      className={`
        inline-flex items-center px-1.5 py-0.5 text-[9px] font-mono font-semibold
        uppercase tracking-wider rounded ${colors.text} ${colors.bg} border ${colors.border}
      `}
    >
      {severity.toUpperCase()}
    </span>
  );
}

function tagBadge(tag: string) {
  const colors = TAG_COLORS[tag.toLowerCase()] ?? { text: "text-text-secondary", bg: "bg-c-s2" };
  return (
    <span
      className={`inline-flex items-center px-1 py-0.5 text-[9px] font-mono rounded ${colors.text} ${colors.bg}`}
    >
      {tag}
    </span>
  );
}

function stringCategoryColor(category: string): string {
  return STRING_CATEGORY_COLORS[category.toUpperCase()] ?? STRING_CATEGORY_COLORS.DEFAULT;
}

// ---------------------------------------------------------------------------
// BinaryDropZone
// ---------------------------------------------------------------------------

function BinaryDropZone({
  onFileSelected,
  analyzing,
}: {
  onFileSelected: (filePath: string) => void;
  analyzing: boolean;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isValidFile = (name: string): boolean =>
    ACCEPTED_EXTENSIONS.some((ext) => name.toLowerCase().endsWith(ext));

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      if (analyzing) return;

      const file = e.dataTransfer.files[0];
      if (file && isValidFile(file.name)) {
        onFileSelected(file.name);
      }
    },
    [onFileSelected, analyzing]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file && isValidFile(file.name)) {
        onFileSelected(file.name);
      }
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    [onFileSelected]
  );

  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 p-6">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          flex flex-col items-center justify-center gap-4 w-full max-w-md
          border-2 border-dashed rounded-lg p-8 transition-all duration-150 cursor-pointer
          ${isDragging
            ? "border-accent-cyan bg-accent-cyan/5"
            : "border-border-subtle bg-bg-onyx/30 hover:border-accent-cyan/40 hover:bg-accent-cyan/5"
          }
          ${analyzing ? "opacity-50 pointer-events-none" : ""}
        `}
        onClick={() => fileInputRef.current?.click()}
      >
        <span
          className={`material-symbols-outlined text-[40px] ${
            isDragging ? "text-accent-cyan" : "text-text-secondary/40"
          }`}
        >
          {isDragging ? "download" : "upload_file"}
        </span>
        <div className="flex flex-col items-center gap-1">
          <span className="text-[12px] font-mono text-text-primary font-semibold">
            Drop binary file here
          </span>
          <span className="text-[10px] font-mono text-text-secondary">
            .exe .dll .elf .apk .so .dylib
          </span>
        </div>
        <button
          type="button"
          disabled={analyzing}
          onClick={(e) => {
            e.stopPropagation();
            fileInputRef.current?.click();
          }}
          className="
            h-7 px-3 text-[10px] font-mono uppercase tracking-wider font-semibold rounded
            bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan
            hover:bg-accent-cyan/20 hover:border-accent-cyan/50 transition-colors
            disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer
          "
        >
          Browse Files
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          onChange={handleFileInput}
          className="hidden"
        />
      </div>
      <span className="text-[9px] font-mono text-text-secondary/40">
        Binary will be analyzed locally via Ghidra headless mode
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AnalysisProgress
// ---------------------------------------------------------------------------

function AnalysisProgress({
  phase,
  percent,
  message,
  analysisId,
}: {
  phase: string;
  percent: number;
  message: string;
  analysisId: string;
}) {
  const phaseIndex = ANALYSIS_PHASES.findIndex((p) => p.key === phase.toLowerCase());
  const currentIdx = phaseIndex >= 0 ? phaseIndex : 0;

  return (
    <div className="flex flex-col gap-3 p-3">
      {/* Phase indicator */}
      <div className="flex items-center gap-1.5 mb-1">
        {ANALYSIS_PHASES.map((p, i) => {
          const isActive = i === currentIdx;
          const isComplete = i < currentIdx;
          return (
            <div key={p.key} className="flex items-center gap-1">
              <div
                className={`
                  flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono
                  uppercase tracking-wider font-semibold transition-colors
                  ${isActive
                    ? "bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30"
                    : isComplete
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "bg-bg-onyx text-text-secondary/40 border border-border-subtle"
                  }
                `}
              >
                <span className="material-symbols-outlined text-[10px]">{p.icon}</span>
                {p.label}
              </div>
              {i < ANALYSIS_PHASES.length - 1 && (
                <span
                  className={`material-symbols-outlined text-[10px] ${
                    isComplete ? "text-emerald-400" : "text-text-secondary/20"
                  }`}
                >
                  chevron_right
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-mono text-accent-cyan uppercase tracking-wider font-semibold">
            {phase}
          </span>
          <span className="text-[10px] font-mono text-text-secondary tabular">
            {Math.round(percent)}%
          </span>
        </div>
        <div className="w-full h-2 bg-bg-onyx rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-accent-cyan to-emerald-400 rounded-full transition-all duration-300 ease-out"
            style={{ width: `${Math.min(percent, 100)}%` }}
          />
        </div>
      </div>

      {/* Message */}
      {message && (
        <span className="text-[10px] font-mono text-text-secondary truncate">{message}</span>
      )}

      {/* Analysis ID */}
      <span className="text-[9px] font-mono text-text-secondary/40">ID: {analysisId}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RiskAssessment
// ---------------------------------------------------------------------------

function RiskAssessment({
  indicators,
  onDecompile,
}: {
  indicators: GhidraAnalysisResult["risk_indicators"];
  onDecompile: (address: string) => void;
}) {
  const [filter, setFilter] = useState<string>("ALL");

  const sorted = [...indicators].sort(
    (a, b) =>
      (SEVERITY_ORDER[a.severity.toUpperCase()] ?? 99) -
      (SEVERITY_ORDER[b.severity.toUpperCase()] ?? 99)
  );

  const filtered = filter === "ALL" ? sorted : sorted.filter((i) => i.severity.toUpperCase() === filter);

  const counts: Record<string, number> = { ALL: indicators.length };
  for (const ind of indicators) {
    const key = ind.severity.toUpperCase();
    counts[key] = (counts[key] ?? 0) + 1;
  }

  if (indicators.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 py-12">
        <span className="material-symbols-outlined text-[32px] text-emerald-400/40">verified_user</span>
        <span className="text-[11px] font-mono text-emerald-400">No risk indicators found</span>
        <span className="text-[10px] font-mono text-text-secondary/50">
          Binary appears clean based on analysis
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-border-subtle bg-bg-onyx/50">
        <span className="material-symbols-outlined text-[12px] text-text-secondary">warning</span>
        <span className="text-[10px] font-mono text-text-secondary uppercase tracking-wider font-semibold">
          Risk Assessment
        </span>
        <div className="flex gap-1 ml-2">
          {Object.entries(counts).map(([key, count]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`
                text-[9px] font-mono px-1.5 py-0.5 rounded transition-colors cursor-pointer
                ${filter === key
                  ? "bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30"
                  : "text-text-secondary hover:text-text-primary border border-transparent"
                }
              `}
            >
              {key} ({count})
            </button>
          ))}
        </div>
      </div>

      {/* Findings list */}
      <div className="flex-1 overflow-auto">
        {filtered.map((ind, i) => {
          const colors = SEVERITY_COLORS[ind.severity.toUpperCase()] ?? SEVERITY_COLORS.LOW;
          return (
            <div
              key={i}
              className={`flex flex-col gap-1.5 px-3 py-2 border-b border-border-subtle/50 ${colors.bg}`}
            >
              <div className="flex items-center gap-2">
                {severityBadge(ind.severity)}
                <span className="text-[9px] font-mono text-text-secondary uppercase tracking-wider">
                  {ind.category}
                </span>
              </div>
              <span className="text-[11px] font-mono text-text-primary">{ind.description}</span>
              {(ind.address || ind.function_name) && (
                <div className="flex items-center gap-2">
                  {ind.function_name && (
                    <span className="text-[10px] font-mono text-accent-cyan">{ind.function_name}</span>
                  )}
                  {ind.address && (
                    <span className="text-[10px] font-mono text-text-secondary tabular">
                      0x{ind.address.replace(/^0x/i, "")}
                    </span>
                  )}
                </div>
              )}
              {ind.evidence && (
                <span className="text-[10px] font-mono text-text-secondary/70 break-all">
                  Evidence: {ind.evidence}
                </span>
              )}
              {ind.recommendation && (
                <span className="text-[10px] font-mono text-text-secondary/50 italic">
                  {ind.recommendation}
                </span>
              )}
              <div className="flex items-center gap-2 mt-1">
                {ind.address && (
                  <button
                    onClick={() => onDecompile(ind.address!)}
                    className="text-[9px] font-mono px-2 py-0.5 bg-accent-cyan/10 border border-accent-cyan/20 rounded text-accent-cyan hover:bg-accent-cyan/20 transition-colors cursor-pointer"
                  >
                    View Decompiled
                  </button>
                )}
                {ind.function_name && (
                  <button
                    className="text-[9px] font-mono px-2 py-0.5 bg-purple-500/10 border border-purple-500/20 rounded text-purple-400 hover:bg-purple-500/20 transition-colors cursor-pointer"
                  >
                    Trace Xrefs
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FunctionList
// ---------------------------------------------------------------------------

function FunctionList({
  functions,
  onDecompile,
}: {
  functions: GhidraAnalysisResult["functions"];
  onDecompile: (address: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"name" | "address" | "size">("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [tagFilter, setTagFilter] = useState<string>("ALL");
  const [expandedAddr, setExpandedAddr] = useState<string | null>(null);

  const allTags = Array.from(new Set(functions.flatMap((f) => f.tags)));

  const filtered = functions
    .filter((f) => {
      if (search && !f.name.toLowerCase().includes(search.toLowerCase()) && !f.address.includes(search))
        return false;
      if (tagFilter !== "ALL" && !f.tags.includes(tagFilter)) return false;
      return true;
    })
    .sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case "name":
          cmp = a.name.localeCompare(b.name);
          break;
        case "address":
          cmp = a.address.localeCompare(b.address);
          break;
        case "size":
          cmp = a.size - b.size;
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

  const toggleSort = (col: typeof sortBy) => {
    if (sortBy === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("asc");
    }
  };

  const sortIcon = (col: typeof sortBy) =>
    sortBy === col ? (sortDir === "asc" ? "arrow_upward" : "arrow_downward") : "unfold_more";

  if (functions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 py-12">
        <span className="material-symbols-outlined text-[32px] text-text-secondary/20">functions</span>
        <span className="text-[11px] font-mono text-text-secondary">No functions found</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search and filter bar */}
      <div className="flex flex-col gap-1.5 px-3 py-2 border-b border-border-subtle bg-bg-onyx/50">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[12px] text-text-secondary">search</span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search functions..."
            className="flex-1 h-6 px-2 text-[11px] font-mono bg-bg-onyx border border-border-subtle rounded text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:border-accent-cyan transition-colors"
          />
          <span className="text-[9px] font-mono text-text-secondary tabular">
            {filtered.length}/{functions.length}
          </span>
        </div>
        {allTags.length > 0 && (
          <div className="flex items-center gap-1">
            <span className="text-[9px] font-mono text-text-secondary/50 uppercase tracking-wider">
              Tags:
            </span>
            <button
              onClick={() => setTagFilter("ALL")}
              className={`text-[9px] font-mono px-1.5 py-0.5 rounded cursor-pointer transition-colors ${
                tagFilter === "ALL"
                  ? "bg-accent-cyan/15 text-accent-cyan"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              All
            </button>
            {allTags.map((t) => (
              <button
                key={t}
                onClick={() => setTagFilter(t)}
                className={`text-[9px] font-mono px-1.5 py-0.5 rounded cursor-pointer transition-colors ${
                  tagFilter === t
                    ? `${TAG_COLORS[t.toLowerCase()]?.bg ?? "bg-accent-cyan/15"} ${TAG_COLORS[t.toLowerCase()]?.text ?? "text-accent-cyan"}`
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Table header */}
      <div className="flex items-center px-3 py-1 border-b border-border-subtle text-[9px] font-mono text-text-secondary/50 uppercase tracking-wider">
        <button onClick={() => toggleSort("name")} className="flex items-center gap-0.5 w-[40%] cursor-pointer hover:text-text-secondary transition-colors">
          Name <span className="material-symbols-outlined text-[10px]">{sortIcon("name")}</span>
        </button>
        <button onClick={() => toggleSort("address")} className="flex items-center gap-0.5 w-[20%] cursor-pointer hover:text-text-secondary transition-colors">
          Address <span className="material-symbols-outlined text-[10px]">{sortIcon("address")}</span>
        </button>
        <button onClick={() => toggleSort("size")} className="flex items-center gap-0.5 w-[12%] cursor-pointer hover:text-text-secondary transition-colors">
          Size <span className="material-symbols-outlined text-[10px]">{sortIcon("size")}</span>
        </button>
        <span className="w-[28%]">Tags</span>
      </div>

      {/* Table body */}
      <div className="flex-1 overflow-auto">
        {filtered.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <span className="text-[10px] font-mono text-text-secondary/50">No functions match filter</span>
          </div>
        ) : (
          filtered.map((fn) => {
            const isExpanded = expandedAddr === fn.address;
            return (
              <div key={fn.address} className="border-b border-border-subtle/30">
                <button
                  onClick={() => setExpandedAddr(isExpanded ? null : fn.address)}
                  className="w-full flex items-center px-3 py-1.5 hover:bg-bg-onyx/50 transition-colors cursor-pointer text-left"
                >
                  <span
                    className={`material-symbols-outlined text-[12px] text-text-secondary/40 transition-transform mr-1 ${
                      isExpanded ? "rotate-90" : ""
                    }`}
                  >
                    chevron_right
                  </span>
                  <span
                    className={`w-[38%] text-[11px] font-mono truncate ${
                      fn.is_external ? "text-purple-400" : "text-text-primary"
                    }`}
                  >
                    {fn.name}
                  </span>
                  <span className="w-[20%] text-[10px] font-mono text-accent-cyan tabular">
                    0x{fn.address.replace(/^0x/i, "")}
                  </span>
                  <span className="w-[12%] text-[10px] font-mono text-text-secondary tabular">
                    {fn.size}
                  </span>
                  <span className="w-[28%] flex items-center gap-1 flex-wrap">
                    {fn.tags.map((t) => tagBadge(t))}
                    {fn.is_external && (
                      <span className="inline-flex items-center px-1 py-0.5 text-[9px] font-mono rounded text-purple-400 bg-purple-500/10">
                        ext
                      </span>
                    )}
                  </span>
                </button>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="px-3 pb-2 pl-7 flex flex-col gap-1.5">
                    <div className="flex items-center gap-3">
                      {fn.return_type && (
                        <span className="text-[10px] font-mono text-emerald-400">
                          Returns: {fn.return_type}
                        </span>
                      )}
                      {fn.parameter_count !== undefined && (
                        <span className="text-[10px] font-mono text-text-secondary">
                          Params: {fn.parameter_count}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDecompile(fn.address);
                        }}
                        className="text-[9px] font-mono px-2 py-0.5 bg-accent-cyan/10 border border-accent-cyan/20 rounded text-accent-cyan hover:bg-accent-cyan/20 transition-colors cursor-pointer"
                      >
                        Decompile
                      </button>
                      <button className="text-[9px] font-mono px-2 py-0.5 bg-purple-500/10 border border-purple-500/20 rounded text-purple-400 hover:bg-purple-500/20 transition-colors cursor-pointer">
                        Xrefs
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StringAnalysis
// ---------------------------------------------------------------------------

function StringAnalysis({ strings }: { strings: GhidraAnalysisResult["strings"] }) {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");

  const categories = Array.from(new Set(strings.map((s) => s.category.toUpperCase())));

  const filtered = strings.filter((s) => {
    if (search && !s.value.toLowerCase().includes(search.toLowerCase()) && !s.address.includes(search))
      return false;
    if (categoryFilter !== "ALL" && s.category.toUpperCase() !== categoryFilter) return false;
    return true;
  });

  if (strings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 py-12">
        <span className="material-symbols-outlined text-[32px] text-text-secondary/20">text_fields</span>
        <span className="text-[11px] font-mono text-text-secondary">No strings found</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search and filter */}
      <div className="flex flex-col gap-1.5 px-3 py-2 border-b border-border-subtle bg-bg-onyx/50">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[12px] text-text-secondary">search</span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search strings..."
            className="flex-1 h-6 px-2 text-[11px] font-mono bg-bg-onyx border border-border-subtle rounded text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:border-accent-cyan transition-colors"
          />
          <span className="text-[9px] font-mono text-text-secondary tabular">
            {filtered.length}/{strings.length}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[9px] font-mono text-text-secondary/50 uppercase tracking-wider">
            Category:
          </span>
          <button
            onClick={() => setCategoryFilter("ALL")}
            className={`text-[9px] font-mono px-1.5 py-0.5 rounded cursor-pointer transition-colors ${
              categoryFilter === "ALL"
                ? "bg-accent-cyan/15 text-accent-cyan"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            All
          </button>
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategoryFilter(c)}
              className={`text-[9px] font-mono px-1.5 py-0.5 rounded cursor-pointer transition-colors ${
                categoryFilter === c
                  ? `${stringCategoryColor(c)} bg-slate-500/10`
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {/* Strings table */}
      <div className="flex-1 overflow-auto">
        {filtered.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <span className="text-[10px] font-mono text-text-secondary/50">No strings match filter</span>
          </div>
        ) : (
          <table className="w-full text-[10px] font-mono">
            <thead>
              <tr className="text-text-secondary/50 border-b border-border-subtle">
                <th className="text-left py-1 px-3 w-[50%]">Value</th>
                <th className="text-left py-1 px-2 w-[18%]">Address</th>
                <th className="text-right py-1 px-2 w-[10%]">Length</th>
                <th className="text-left py-1 px-2 w-[22%]">Category</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s, i) => (
                <tr
                  key={i}
                  className="border-b border-border-subtle/30 hover:bg-bg-onyx/50 transition-colors"
                >
                  <td className="py-1 px-3 text-text-primary truncate max-w-0" title={s.value}>
                    {s.value}
                  </td>
                  <td className="py-1 px-2 text-accent-cyan tabular">
                    0x{s.address.replace(/^0x/i, "")}
                  </td>
                  <td className="py-1 px-2 text-text-secondary text-right tabular">{s.length}</td>
                  <td className="py-1 px-2">
                    <span
                      className={`text-[9px] font-mono font-semibold uppercase tracking-wider ${stringCategoryColor(s.category)}`}
                    >
                      {s.category}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DecompiledView
// ---------------------------------------------------------------------------

function DecompiledView({
  result,
  onAddComment,
}: {
  result: DecompileResult | null;
  onAddComment: (address: string, comment: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [showCommentInput, setShowCommentInput] = useState(false);

  const handleCopy = useCallback(() => {
    if (!result) return;
    navigator.clipboard.writeText(result.pseudocode).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [result]);

  const handleAddComment = useCallback(() => {
    if (!result || !commentText.trim()) return;
    onAddComment(result.address, commentText.trim());
    setCommentText("");
    setShowCommentInput(false);
  }, [result, commentText, onAddComment]);

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 py-12">
        <span className="material-symbols-outlined text-[32px] text-text-secondary/20">code</span>
        <span className="text-[11px] font-mono text-text-secondary">No decompiled function</span>
        <span className="text-[10px] font-mono text-text-secondary/50">
          Click Decompile on a function to view pseudocode
        </span>
      </div>
    );
  }

  // Simple C syntax highlighting via CSS class names
  const highlightC = (code: string): string => {
    return code
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/(\/\/[^\n]*)/g, '<span class="c-comment">$1</span>')
      .replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="c-comment">$1</span>')
      .replace(
        /\b(void|int|char|long|short|unsigned|signed|float|double|const|static|extern|struct|enum|union|typedef|return|if|else|for|while|do|switch|case|break|continue|default|sizeof|goto)\b/g,
        '<span class="c-keyword">$1</span>'
      )
      .replace(
        /\b(undefined|FUN_[0-9a-f]+|null|NULL|true|false|TRUE|FALSE)\b/g,
        '<span class="c-literal">$1</span>'
      )
      .replace(/\b(0x[0-9a-fA-F]+)\b/g, '<span class="c-number">$1</span>')
      .replace(/\b(\d+)\b/g, '<span class="c-number">$1</span>')
      .replace(/"([^"\\]|\\.)*"/g, '<span class="c-string">$&</span>')
      .replace(/'([^'\\]|\\.)*'/g, '<span class="c-string">$&</span>');
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-3 py-2 border-b border-border-subtle bg-bg-onyx/50">
        <span className="material-symbols-outlined text-[14px] text-accent-cyan">code</span>
        <div className="flex flex-col">
          <span className="text-[11px] font-mono text-text-primary font-semibold">
            {result.function_name}
          </span>
          {result.signature && (
            <span className="text-[10px] font-mono text-text-secondary truncate max-w-md" title={result.signature}>
              {result.signature}
            </span>
          )}
        </div>
        <span className="text-[10px] font-mono text-accent-cyan tabular ml-1">
          0x{result.address.replace(/^0x/i, "")}
        </span>
        <div className="flex-1" />
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[9px] font-mono px-2 py-0.5 bg-bg-onyx border border-border-subtle rounded text-text-secondary hover:text-accent-cyan hover:border-accent-cyan/30 transition-colors cursor-pointer"
        >
          <span className="material-symbols-outlined text-[11px]">
            {copied ? "check" : "content_copy"}
          </span>
          {copied ? "Copied" : "Copy"}
        </button>
        <button
          onClick={() => setShowCommentInput(!showCommentInput)}
          className="flex items-center gap-1 text-[9px] font-mono px-2 py-0.5 bg-bg-onyx border border-border-subtle rounded text-text-secondary hover:text-accent-gold hover:border-accent-gold/30 transition-colors cursor-pointer"
        >
          <span className="material-symbols-outlined text-[11px]">comment</span>
          Comment
        </button>
      </div>

      {/* Comment input */}
      {showCommentInput && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-accent-gold/20 bg-accent-gold/5">
          <input
            type="text"
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder="Add annotation..."
            onKeyDown={(e) => e.key === "Enter" && handleAddComment()}
            className="flex-1 h-6 px-2 text-[11px] font-mono bg-bg-onyx border border-border-subtle rounded text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:border-accent-gold transition-colors"
            autoFocus
          />
          <button
            onClick={handleAddComment}
            disabled={!commentText.trim()}
            className="text-[9px] font-mono px-2 py-0.5 bg-accent-gold/10 border border-accent-gold/20 rounded text-accent-gold hover:bg-accent-gold/20 transition-colors disabled:opacity-50 cursor-pointer"
          >
            Save
          </button>
        </div>
      )}

      {/* Code viewer */}
      <div className="flex-1 overflow-auto bg-bg-onyx">
        <pre className="p-3 text-[11px] font-mono leading-relaxed editor-select">
          <code
            dangerouslySetInnerHTML={{ __html: highlightC(result.pseudocode) }}
          />
        </pre>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ImportTable
// ---------------------------------------------------------------------------

function ImportTable({ imports }: { imports: GhidraAnalysisResult["imports"] }) {
  const [search, setSearch] = useState("");
  const [expandedLib, setExpandedLib] = useState<string | null>(null);

  // Group imports by library
  const grouped: Record<string, typeof imports> = {};
  for (const imp of imports) {
    const lib = imp.library || "UNKNOWN";
    if (!grouped[lib]) grouped[lib] = [];
    grouped[lib].push(imp);
  }

  const libNames = Object.keys(grouped).sort();

  const filteredGrouped: Record<string, typeof imports> = {};
  for (const lib of libNames) {
    const filtered = grouped[lib].filter(
      (imp) =>
        !search ||
        imp.name.toLowerCase().includes(search.toLowerCase()) ||
        imp.library.toLowerCase().includes(search.toLowerCase()) ||
        imp.address.includes(search)
    );
    if (filtered.length > 0) filteredGrouped[lib] = filtered;
  }

  if (imports.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 py-12">
        <span className="material-symbols-outlined text-[32px] text-text-secondary/20">import_export</span>
        <span className="text-[11px] font-mono text-text-secondary">No imports found</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border-subtle bg-bg-onyx/50">
        <span className="material-symbols-outlined text-[12px] text-text-secondary">search</span>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search imports..."
          className="flex-1 h-6 px-2 text-[11px] font-mono bg-bg-onyx border border-border-subtle rounded text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:border-accent-cyan transition-colors"
        />
        <span className="text-[9px] font-mono text-text-secondary tabular">
          {imports.length} imports · {libNames.length} libraries
        </span>
      </div>

      {/* Grouped list */}
      <div className="flex-1 overflow-auto">
        {Object.entries(filteredGrouped).map(([lib, libImports]) => {
          const isExpanded = expandedLib === lib || search.length > 0;
          return (
            <div key={lib} className="border-b border-border-subtle">
              <button
                onClick={() => setExpandedLib(isExpanded && !search ? null : lib)}
                className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-bg-onyx/50 transition-colors cursor-pointer text-left"
              >
                <span
                  className={`material-symbols-outlined text-[12px] text-text-secondary/40 transition-transform ${
                    isExpanded ? "rotate-90" : ""
                  }`}
                >
                  chevron_right
                </span>
                <span className="material-symbols-outlined text-[12px] text-purple-400">library_books</span>
                <span className="text-[11px] font-mono text-text-primary font-semibold">{lib}</span>
                <span className="text-[9px] font-mono text-text-secondary ml-1">
                  ({libImports.length})
                </span>
              </button>
              {isExpanded && (
                <div className="pl-7 pr-3 pb-1">
                  <table className="w-full text-[10px] font-mono">
                    <thead>
                      <tr className="text-text-secondary/50 border-b border-border-subtle/50">
                        <th className="text-left py-0.5 px-2 w-[50%]">Symbol</th>
                        <th className="text-left py-0.5 px-2 w-[30%]">Address</th>
                        <th className="text-left py-0.5 px-2 w-[20%]">Library</th>
                      </tr>
                    </thead>
                    <tbody>
                      {libImports.map((imp, i) => (
                        <tr
                          key={i}
                          className="border-b border-border-subtle/20 hover:bg-bg-onyx/30 transition-colors"
                        >
                          <td className="py-0.5 px-2 text-text-primary">{imp.name}</td>
                          <td className="py-0.5 px-2 text-accent-cyan tabular">
                            0x{imp.address.replace(/^0x/i, "")}
                          </td>
                          <td className="py-0.5 px-2 text-text-secondary">{imp.library}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// GhidraPanel (main)
// ---------------------------------------------------------------------------

export default function GhidraPanel() {
  const [subTab, setSubTab] = useState<GhidraSubTab>("dropzone");
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [result, setResult] = useState<GhidraAnalysisResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progressPhase, setProgressPhase] = useState("import");
  const [progressPercent, setProgressPercent] = useState(0);
  const [progressMessage, setProgressMessage] = useState("");
  const [decompileResult, setDecompileResult] = useState<DecompileResult | null>(null);
  const [decompiling, setDecompiling] = useState(false);
  const [ghidraAvailable, setGhidraAvailable] = useState<boolean | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // ---- Check Ghidra backend availability ----
  useEffect(() => {
    const check = async () => {
      try {
        const resp = await fetch(`${BACKEND_URL}/api/tools/ghidra/status`, {
          signal: AbortSignal.timeout(3000),
        });
        if (resp.ok) {
          const data = await resp.json();
          setGhidraAvailable(data.available);
        } else {
          setGhidraAvailable(false);
        }
      } catch {
        setGhidraAvailable(false);
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  // ---- WebSocket for progress updates ----
  useEffect(() => {
    if (!analysisId || !analyzing) return;

    const ws = new WebSocket(`ws://127.0.0.1:8000/ws/ghidra/${analysisId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg: WsEvent = JSON.parse(event.data);
        switch (msg.type) {
          case "progress":
            setProgressPhase(msg.phase);
            setProgressPercent(msg.percent);
            setProgressMessage(msg.message);
            break;
          case "complete":
            setResult(msg.result);
            setAnalyzing(false);
            setSubTab("risk");
            ws.close();
            break;
          case "error":
            setError(msg.message);
            setAnalyzing(false);
            ws.close();
            break;
        }
      } catch {
        // ignore malformed ws messages
      }
    };

    ws.onerror = () => {
      // Fallback: poll status if WebSocket fails
    };

    ws.onclose = () => {
      wsRef.current = null;
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [analysisId, analyzing]);

  // ---- Fallback polling when WS is not available ----
  useEffect(() => {
    if (!analysisId || !analyzing) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const poll = async () => {
      try {
        const resp = await fetch(`${BACKEND_URL}/api/tools/ghidra/status/${analysisId}`, {
          signal: AbortSignal.timeout(5000),
        });
        if (resp.ok) {
          const data = await resp.json();
          setProgressPhase(data.current_phase ?? "analysis");
          setProgressPercent(data.progress_percent ?? 0);
          if (data.status === "completed") {
            const resResp = await fetch(
              `${BACKEND_URL}/api/tools/ghidra/results/${analysisId}`,
              { signal: AbortSignal.timeout(10000) }
            );
            if (resResp.ok) {
              const resData = await resResp.json();
              setResult(resData);
              setAnalyzing(false);
              setSubTab("risk");
            }
          } else if (data.status === "failed" || data.status === "error") {
            setError(data.error ?? "Analysis failed");
            setAnalyzing(false);
          }
        }
      } catch {
        // poll will retry
      }
    };

    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [analysisId, analyzing]);

  // ---- Start analysis ----
  const handleAnalyze = useCallback(async (binaryPath: string) => {
    setAnalyzing(true);
    setError(null);
    setResult(null);
    setDecompileResult(null);
    setProgressPhase("import");
    setProgressPercent(0);
    setProgressMessage("Starting analysis...");
    setSubTab("progress");

    try {
      const resp = await fetch(`${BACKEND_URL}/api/tools/ghidra/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ binary_path: binaryPath }),
        signal: AbortSignal.timeout(30000),
      });

      const data = await resp.json();
      if (!resp.ok) {
        setError(data.detail ?? `Analysis failed: ${resp.status}`);
        setAnalyzing(false);
        setSubTab("dropzone");
        return;
      }

      setAnalysisId(data.analysis_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start analysis");
      setAnalyzing(false);
      setSubTab("dropzone");
    }
  }, []);

  // ---- Decompile a function ----
  const handleDecompile = useCallback(
    async (address: string) => {
      if (!analysisId) return;
      setDecompiling(true);
      setError(null);

      try {
        const resp = await fetch(`${BACKEND_URL}/api/tools/ghidra/decompile`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ analysis_id: analysisId, function_address: address }),
          signal: AbortSignal.timeout(15000),
        });

        const data = await resp.json();
        if (!resp.ok) {
          setError(data.detail ?? `Decompile failed: ${resp.status}`);
          setDecompiling(false);
          return;
        }

        setDecompileResult({
          pseudocode: data.pseudocode,
          language: data.language,
          function_name: data.function_name,
          address: data.address,
          signature: data.signature ?? "",
        });
        setSubTab("decompiled");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Decompilation failed");
      } finally {
        setDecompiling(false);
      }
    },
    [analysisId]
  );

  // ---- Add comment (placeholder — would integrate with backend) ----
  const handleAddComment = useCallback((_address: string, _comment: string) => {
    // TODO: POST to /api/tools/ghidra/comment when backend supports it
  }, []);

  // ---- Cancel analysis ----
  const handleCancel = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    setAnalyzing(false);
    setSubTab("dropzone");
  }, []);

  // ---- Tab definitions ----
  const SUB_TABS: { id: GhidraSubTab; label: string; icon: string; badge?: number }[] = [
    { id: "dropzone", label: "Binary", icon: "upload_file" },
    { id: "progress", label: "Progress", icon: "progress_activity" },
    { id: "risk", label: "Risks", icon: "warning", badge: result?.risk_indicators.length },
    { id: "functions", label: "Functions", icon: "functions", badge: result?.functions.length },
    { id: "strings", label: "Strings", icon: "text_fields", badge: result?.strings.length },
    { id: "decompiled", label: "Decompile", icon: "code" },
    { id: "imports", label: "Imports", icon: "import_export", badge: result?.imports.length },
  ];

  return (
    <div className="flex flex-col h-full bg-panel-bg font-mono">
      {/* Sub-tab bar */}
      <div className="flex items-center h-8 shrink-0 bg-bg-onyx border-b border-border-subtle">
        {SUB_TABS.map((tab) => {
          const isActive = subTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setSubTab(tab.id)}
              className={`
                flex items-center h-full px-2.5 gap-1 border-0 cursor-pointer shrink-0
                whitespace-nowrap text-[9px] uppercase tracking-wider font-semibold
                transition-colors duration-[50ms]
                ${isActive
                  ? "text-accent-cyan border-b-2 border-b-accent-cyan bg-c-s2"
                  : "text-text-secondary border-b-2 border-b-transparent bg-transparent hover:text-text-primary"
                }
              `}
            >
              <span className="material-symbols-outlined text-[12px]">{tab.icon}</span>
              <span>{tab.label}</span>
              {tab.badge !== undefined && tab.badge > 0 && (
                <span className="ml-0.5 text-[8px] font-mono text-accent-cyan tabular">
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
        <div className="flex-1" />
        {/* Ghidra availability indicator */}
        <div className="flex items-center gap-1.5 pr-2">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              ghidraAvailable === null
                ? "bg-text-secondary/30"
                : ghidraAvailable
                ? "bg-emerald-400"
                : "bg-red-400"
            }`}
          />
          <span className="text-[9px] text-text-secondary">
            {ghidraAvailable === null
              ? "checking..."
              : ghidraAvailable
              ? "ghidra ready"
              : "ghidra offline"}
          </span>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 px-3 py-2 border-b border-red-500/20 bg-red-500/5">
          <span className="material-symbols-outlined text-[14px] text-red-400">error</span>
          <span className="text-[10px] font-mono text-red-400 flex-1">{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-[10px] font-mono text-red-400/50 hover:text-red-400 cursor-pointer"
          >
            dismiss
          </button>
        </div>
      )}

      {/* Analyzing overlay / Cancel */}
      {analyzing && subTab !== "progress" && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-amber-500/10 bg-amber-500/5">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span className="text-[10px] font-mono text-amber-400">
            Analyzing... {Math.round(progressPercent)}% ({progressPhase})
          </span>
          <button
            onClick={handleCancel}
            className="ml-auto text-[9px] font-mono px-2 py-0.5 bg-red-500/10 border border-red-500/20 rounded text-red-400 hover:bg-red-500/20 transition-colors cursor-pointer"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Decompiling indicator */}
      {decompiling && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-accent-cyan/10 bg-accent-cyan/5">
          <span className="w-2 h-2 rounded-full bg-accent-cyan animate-pulse" />
          <span className="text-[10px] font-mono text-accent-cyan">Decompiling function...</span>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {subTab === "dropzone" && (
          <BinaryDropZone onFileSelected={handleAnalyze} analyzing={analyzing} />
        )}
        {subTab === "progress" && (
          <>
            {analyzing && analysisId ? (
              <AnalysisProgress
                phase={progressPhase}
                percent={progressPercent}
                message={progressMessage}
                analysisId={analysisId}
              />
            ) : result ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 py-12">
                <span className="material-symbols-outlined text-[32px] text-emerald-400">check_circle</span>
                <span className="text-[11px] font-mono text-emerald-400">Analysis Complete</span>
                <span className="text-[10px] font-mono text-text-secondary">
                  {result.functions.length} functions · {result.strings.length} strings · {result.risk_indicators.length} risks
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-3 py-12">
                <span className="material-symbols-outlined text-[32px] text-text-secondary/20">progress_activity</span>
                <span className="text-[11px] font-mono text-text-secondary">No analysis in progress</span>
              </div>
            )}
            {analyzing && (
              <div className="flex justify-center p-3">
                <button
                  onClick={handleCancel}
                  className="text-[10px] font-mono px-4 py-1.5 bg-red-500/10 border border-red-500/20 rounded text-red-400 hover:bg-red-500/20 transition-colors cursor-pointer"
                >
                  Cancel Analysis
                </button>
              </div>
            )}
          </>
        )}
        {subTab === "risk" && (
          <RiskAssessment
            indicators={result?.risk_indicators ?? []}
            onDecompile={handleDecompile}
          />
        )}
        {subTab === "functions" && (
          <FunctionList
            functions={result?.functions ?? []}
            onDecompile={handleDecompile}
          />
        )}
        {subTab === "strings" && (
          <StringAnalysis strings={result?.strings ?? []} />
        )}
        {subTab === "decompiled" && (
          <DecompiledView result={decompileResult} onAddComment={handleAddComment} />
        )}
        {subTab === "imports" && (
          <ImportTable imports={result?.imports ?? []} />
        )}
      </div>
    </div>
  );
}
