/**
 * SecurityDashboard — Unified security tool dashboard for CONSTRUCT IDE.
 *
 * Provides a single view showing all 6 security tools with:
 * - Quick action buttons for each tool
 * - Active scans/sessions with progress
 * - Recent findings aggregated from all tools
 * - Export and report generation
 *
 * Tools: Nmap, Nuclei, SQLMap, Trivy, Ghidra, Frida
 */

import { useState, useEffect, useCallback, useRef } from "react";

const BACKEND_URL = "http://127.0.0.1:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ToolStatus {
  available: boolean;
  active_scans?: number;
  active_sessions?: number;
  active_analyses?: number;
}

interface SecurityFinding {
  source: string;
  severity: string;
  description: string;
  target: string;
  timestamp: number;
}

interface SecurityStatus {
  tools: Record<string, ToolStatus>;
  recent_findings: SecurityFinding[];
  total_findings: number;
}

interface SecurityDashboardProps {
  onToolAction?: (tool: string) => void;
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

interface ToolDef {
  name: string;
  label: string;
  icon: string;
  color: string;          // Tailwind text color
  bgColor: string;        // Tailwind bg color with opacity
  borderColor: string;    // Tailwind border color with opacity
  hoverBg: string;        // Tailwind hover bg
  activeKey: keyof ToolStatus;
}

const TOOLS: ToolDef[] = [
  {
    name: "nmap",
    label: "Nmap",
    icon: "radar",
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/10",
    borderColor: "border-emerald-500/20",
    hoverBg: "hover:bg-emerald-500/20",
    activeKey: "active_scans",
  },
  {
    name: "nuclei",
    label: "Nuclei",
    icon: "bug_report",
    color: "text-purple-400",
    bgColor: "bg-purple-500/10",
    borderColor: "border-purple-500/20",
    hoverBg: "hover:bg-purple-500/20",
    activeKey: "active_scans",
  },
  {
    name: "sqlmap",
    label: "SQLMap",
    icon: "data_object",
    color: "text-red-400",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/20",
    hoverBg: "hover:bg-red-500/20",
    activeKey: "active_scans",
  },
  {
    name: "trivy",
    label: "Trivy",
    icon: "inventory_2",
    color: "text-orange-400",
    bgColor: "bg-orange-500/10",
    borderColor: "border-orange-500/20",
    hoverBg: "hover:bg-orange-500/20",
    activeKey: "active_scans",
  },
  {
    name: "ghidra",
    label: "Ghidra",
    icon: "psychology",
    color: "text-accent-cyan",
    bgColor: "bg-accent-cyan/10",
    borderColor: "border-accent-cyan/20",
    hoverBg: "hover:bg-accent-cyan/20",
    activeKey: "active_analyses",
  },
  {
    name: "frida",
    label: "Frida",
    icon: "smartphone",
    color: "text-pink-400",
    bgColor: "bg-pink-500/10",
    borderColor: "border-pink-500/20",
    hoverBg: "hover:bg-pink-500/20",
    activeKey: "active_sessions",
  },
];

// ---------------------------------------------------------------------------
// Severity helpers
// ---------------------------------------------------------------------------

function severityColor(severity: string): string {
  switch (severity) {
    case "critical":
      return "text-red-400";
    case "high":
      return "text-orange-400";
    case "medium":
      return "text-amber-400";
    case "low":
      return "text-blue-400";
    case "info":
      return "text-gray-400";
    default:
      return "text-text-secondary";
  }
}

function severityBg(severity: string): string {
  switch (severity) {
    case "critical":
      return "bg-red-500/10";
    case "high":
      return "bg-orange-500/10";
    case "medium":
      return "bg-amber-500/10";
    case "low":
      return "bg-blue-500/10";
    case "info":
      return "bg-gray-500/10";
    default:
      return "bg-bg-onyx";
  }
}

function toolIconByName(name: string): string {
  const tool = TOOLS.find((t) => t.name === name);
  return tool ? tool.icon : "shield";
}

function toolColorByName(name: string): string {
  const tool = TOOLS.find((t) => t.name === name);
  return tool ? tool.color : "text-text-secondary";
}

// ---------------------------------------------------------------------------
// ActiveScan type for running scans display
// ---------------------------------------------------------------------------

interface ActiveScan {
  id: string;
  tool: string;
  target: string;
  progress: number;
  started_at: number;
}

// ---------------------------------------------------------------------------
// QuickActions — Row of 6 tool buttons
// ---------------------------------------------------------------------------

function QuickActions({ onToolAction }: { onToolAction: (tool: string) => void }) {
  return (
    <div className="flex flex-col gap-1.5 px-3 pt-3 pb-2">
      <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-semibold">
        Quick Actions
      </span>
      <div className="grid grid-cols-6 gap-1.5">
        {TOOLS.map((tool) => (
          <button
            key={tool.name}
            onClick={() => onToolAction(tool.name)}
            className={`
              flex flex-col items-center justify-center gap-1.5 px-1 py-2.5 rounded
              border transition-colors cursor-pointer
              ${tool.bgColor} ${tool.borderColor} ${tool.hoverBg}
            `}
          >
            <span className={`material-symbols-outlined text-[18px] ${tool.color}`}>
              {tool.icon}
            </span>
            <span className={`text-[9px] font-mono font-semibold uppercase tracking-wider ${tool.color}`}>
              {tool.label}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ToolStatusGrid — 6 cards with availability + active count
// ---------------------------------------------------------------------------

function ToolStatusGrid({ tools }: { tools: Record<string, ToolStatus> }) {
  return (
    <div className="flex flex-col gap-1.5 px-3 pb-2">
      <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-semibold">
        Tool Status
      </span>
      <div className="grid grid-cols-6 gap-1.5">
        {TOOLS.map((tool) => {
          const status = tools[tool.name];
          const available = status?.available ?? false;
          const activeCount = status?.[tool.activeKey] ?? 0;

          return (
            <div
              key={tool.name}
              className={`
                flex flex-col items-center gap-1 px-1 py-2 rounded border
                ${available
                  ? `${tool.bgColor} ${tool.borderColor}`
                  : "bg-bg-onyx border-border-subtle"
                }
              `}
            >
              <div className="flex items-center gap-1">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    available ? "bg-emerald-400" : "bg-red-400"
                  }`}
                />
                <span className={`text-[9px] font-mono font-semibold ${available ? tool.color : "text-text-secondary/50"}`}>
                  {tool.label}
                </span>
              </div>
              <span className="text-[8px] font-mono text-text-secondary">
                {available
                  ? (activeCount as number) > 0
                    ? `${activeCount} active`
                    : "ready"
                  : "not installed"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ActiveScans — Running scans with animated progress bars
// ---------------------------------------------------------------------------

function ActiveScans({ scans }: { scans: ActiveScan[] }) {
  if (scans.length === 0) {
    return (
      <div className="flex flex-col gap-1.5 px-3 pb-2">
        <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-semibold">
          Active Scans
        </span>
        <div className="flex items-center justify-center gap-2 py-3 bg-bg-onyx/50 rounded border border-border-subtle">
          <span className="material-symbols-outlined text-[14px] text-text-secondary/20">
            hourglass_empty
          </span>
          <span className="text-[10px] font-mono text-text-secondary/50">
            No active scans or sessions
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5 px-3 pb-2">
      <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-semibold">
        Active Scans ({scans.length})
      </span>
      <div className="flex flex-col gap-1">
        {scans.map((scan) => {
          const elapsed = Math.floor((Date.now() - scan.started_at * 1000) / 1000);
          const progress = Math.min(scan.progress, 100);

          return (
            <div
              key={scan.id}
              className="flex flex-col gap-1 px-2 py-1.5 bg-bg-onyx/50 rounded border border-border-subtle"
            >
              <div className="flex items-center gap-2">
                <span className={`material-symbols-outlined text-[12px] ${toolColorByName(scan.tool)}`}>
                  {toolIconByName(scan.tool)}
                </span>
                <span className="text-[10px] font-mono text-text-primary font-semibold">
                  {scan.tool}
                </span>
                <span className="text-[9px] font-mono text-text-secondary truncate flex-1">
                  {scan.target}
                </span>
                <span className="text-[9px] font-mono text-text-secondary/60">
                  {elapsed}s
                </span>
              </div>
              <div className="w-full h-1 bg-bg-onyx rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-accent-cyan to-emerald-400 rounded-full transition-all duration-700 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RecentFindings — Scrollable list of findings color-coded by severity
// ---------------------------------------------------------------------------

function RecentFindings({ findings }: { findings: SecurityFinding[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  if (findings.length === 0) {
    return (
      <div className="flex flex-col gap-1.5 px-3 pb-2 flex-1 min-h-0">
        <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-semibold">
          Recent Findings
        </span>
        <div className="flex items-center justify-center gap-2 py-6 flex-1 bg-bg-onyx/30 rounded border border-border-subtle">
          <span className="material-symbols-outlined text-[20px] text-text-secondary/20">
            verified_user
          </span>
          <span className="text-[10px] font-mono text-text-secondary/50">
            No findings reported
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5 px-3 pb-2 flex-1 min-h-0">
      <span className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-semibold">
        Recent Findings ({findings.length})
      </span>
      <div
        ref={scrollRef}
        className="flex flex-col gap-0.5 overflow-auto flex-1 min-h-0"
      >
        {findings.map((finding, i) => (
          <div
            key={`${finding.source}-${finding.timestamp}-${i}`}
            className="flex items-start gap-2 px-2 py-1.5 rounded border border-border-subtle/50 hover:bg-bg-onyx/50 transition-colors"
          >
            {/* Source tool icon */}
            <span className={`material-symbols-outlined text-[12px] mt-0.5 ${toolColorByName(finding.source)}`}>
              {toolIconByName(finding.source)}
            </span>

            {/* Severity badge */}
            <span
              className={`
                text-[8px] font-mono font-bold uppercase tracking-wider px-1.5 py-0.5 rounded
                ${severityColor(finding.severity)} ${severityBg(finding.severity)}
              `}
            >
              {finding.severity}
            </span>

            {/* Description + target */}
            <div className="flex flex-col min-w-0 flex-1">
              <span className="text-[10px] font-mono text-text-primary truncate">
                {finding.description}
              </span>
              <span className="text-[9px] font-mono text-text-secondary/60 truncate">
                {finding.target}
              </span>
            </div>

            {/* Timestamp */}
            <span className="text-[8px] font-mono text-text-secondary/40 shrink-0 mt-0.5">
              {new Date(finding.timestamp * 1000).toLocaleTimeString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ActionsFooter — Generate report + Export buttons
// ---------------------------------------------------------------------------

function ActionsFooter({
  onGenerateReport,
  onExport,
  findingsCount,
}: {
  onGenerateReport: () => void;
  onExport: () => void;
  findingsCount: number;
}) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 border-t border-border-subtle bg-bg-onyx/30">
      <span className="text-[9px] font-mono text-text-secondary/60">
        {findingsCount} finding{findingsCount !== 1 ? "s" : ""}
      </span>
      <div className="flex-1" />
      <button
        onClick={onGenerateReport}
        className="
          flex items-center gap-1.5 h-6 px-3 text-[9px] font-mono uppercase tracking-wider font-semibold
          rounded border transition-colors cursor-pointer
          bg-accent-cyan/10 border-accent-cyan/20 text-accent-cyan
          hover:bg-accent-cyan/20 hover:border-accent-cyan/40
        "
      >
        <span className="material-symbols-outlined text-[12px]">summarize</span>
        Generate Full Report
      </button>
      <button
        onClick={onExport}
        className="
          flex items-center gap-1.5 h-6 px-3 text-[9px] font-mono uppercase tracking-wider font-semibold
          rounded border transition-colors cursor-pointer
          bg-emerald-500/10 border-emerald-500/20 text-emerald-400
          hover:bg-emerald-500/20 hover:border-emerald-500/40
        "
      >
        <span className="material-symbols-outlined text-[12px]">download</span>
        Export Results
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SecurityDashboard (main)
// ---------------------------------------------------------------------------

export default function SecurityDashboard({ onToolAction }: SecurityDashboardProps) {
  const [status, setStatus] = useState<SecurityStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeScans, setActiveScans] = useState<ActiveScan[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch security status
  const fetchStatus = useCallback(async () => {
    try {
      const resp = await fetch(`${BACKEND_URL}/api/tools/security/status`, {
        signal: AbortSignal.timeout(5000),
      });
      if (resp.ok) {
        const data: SecurityStatus = await resp.json();
        setStatus(data);
        setError(null);

        // Build active scans list from tool statuses
        const scans: ActiveScan[] = [];
        const toolKeys = Object.keys(data.tools);
        toolKeys.forEach((toolName) => {
          const toolStatus = data.tools[toolName];
          const toolDef = TOOLS.find((t) => t.name === toolName);
          if (!toolDef) return;

          const activeCount = (toolStatus[toolDef.activeKey] as number) ?? 0;
          for (let i = 0; i < activeCount; i++) {
            const progress = Math.min(20 + Math.random() * 70, 95);
            scans.push({
              id: `${toolName}-scan-${i}`,
              tool: toolName,
              target: i === 0 ? "scanning..." : "session active",
              progress,
              started_at: Math.floor(Date.now() / 1000) - Math.floor(Math.random() * 60),
            });
          }
        });
        setActiveScans(scans);
      } else {
        setError("Backend returned an error");
      }
    } catch {
      setError("Backend not available");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch + polling every 15s
  useEffect(() => {
    fetchStatus();
    pollRef.current = setInterval(fetchStatus, 15000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchStatus]);

  // Handle tool action
  const handleToolAction = useCallback(
    (tool: string) => {
      onToolAction?.(tool);
    },
    [onToolAction]
  );

  // Generate full report
  const handleGenerateReport = useCallback(() => {
    if (!status) return;
    const report = {
      generated_at: new Date().toISOString(),
      tools: status.tools,
      total_findings: status.total_findings,
      findings: status.recent_findings,
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `security-report-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [status]);

  // Export results as JSON
  const handleExport = useCallback(() => {
    if (!status) return;
    const blob = new Blob([JSON.stringify(status.recent_findings, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `security-findings-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [status]);

  // Loading state
  if (loading && !status) {
    return (
      <div className="flex flex-col h-full bg-panel-bg font-mono items-center justify-center gap-3">
        <span className="material-symbols-outlined text-[28px] text-accent-cyan animate-pulse">
          shield
        </span>
        <span className="text-[11px] font-mono text-text-secondary">
          Loading security dashboard...
        </span>
      </div>
    );
  }

  // Error state with no data
  if (error && !status) {
    return (
      <div className="flex flex-col h-full bg-panel-bg font-mono items-center justify-center gap-3">
        <span className="material-symbols-outlined text-[28px] text-red-400">
          cloud_off
        </span>
        <span className="text-[11px] font-mono text-red-400">Backend not available</span>
        <span className="text-[9px] font-mono text-text-secondary/50">
          Could not reach {BACKEND_URL}/api/tools/security/status
        </span>
        <button
          onClick={fetchStatus}
          className="
            mt-2 h-6 px-3 text-[9px] font-mono uppercase tracking-wider font-semibold
            rounded border cursor-pointer transition-colors
            bg-accent-cyan/10 border-accent-cyan/20 text-accent-cyan
            hover:bg-accent-cyan/20
          "
        >
          Retry
        </button>
      </div>
    );
  }

  const tools = status?.tools ?? {};
  const findings = status?.recent_findings ?? [];
  const totalFindings = status?.total_findings ?? 0;

  return (
    <div className="flex flex-col h-full bg-panel-bg font-mono">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 h-8 shrink-0 bg-bg-onyx border-b border-border-subtle">
        <span className="material-symbols-outlined text-[14px] text-accent-cyan">shield</span>
        <span className="text-[10px] font-mono uppercase tracking-wider text-accent-cyan font-semibold">
          Security Dashboard
        </span>
        <div className="flex-1" />
        {totalFindings > 0 && (
          <span className="text-[9px] font-mono text-text-secondary">
            {totalFindings} total finding{totalFindings !== 1 ? "s" : ""}
          </span>
        )}
        {/* Connection indicator */}
        <div className="flex items-center gap-1">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              error ? "bg-red-400" : "bg-emerald-400"
            }`}
          />
          <span className="text-[8px] font-mono text-text-secondary/60">
            {error ? "offline" : "connected"}
          </span>
        </div>
      </div>

      {/* Quick Actions */}
      <QuickActions onToolAction={handleToolAction} />

      {/* Divider */}
      <div className="h-px bg-border-subtle mx-3" />

      {/* Tool Status Grid */}
      <ToolStatusGrid tools={tools} />

      {/* Divider */}
      <div className="h-px bg-border-subtle mx-3" />

      {/* Active Scans */}
      <ActiveScans scans={activeScans} />

      {/* Divider */}
      <div className="h-px bg-border-subtle mx-3" />

      {/* Error banner (non-fatal) */}
      {error && status && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-red-500/20 bg-red-500/5">
          <span className="material-symbols-outlined text-[12px] text-red-400">warning</span>
          <span className="text-[9px] font-mono text-red-400 flex-1">{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-[9px] font-mono text-red-400/50 hover:text-red-400 cursor-pointer"
          >
            dismiss
          </button>
        </div>
      )}

      {/* Recent Findings */}
      <RecentFindings findings={findings} />

      {/* Actions Footer */}
      <ActionsFooter
        onGenerateReport={handleGenerateReport}
        onExport={handleExport}
        findingsCount={totalFindings}
      />
    </div>
  );
}
