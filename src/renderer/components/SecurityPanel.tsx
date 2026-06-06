/**
 * SecurityPanel — Network security scanning interface for CONSTRUCT IDE.
 *
 * Provides Nmap scanning UI with form inputs, results table, scan history,
 * and real-time progress indication. Integrates with the Python backend
 * via the /api/tools/nmap endpoint.
 *
 * Sub-components:
 * - NmapScanForm: Target/ports/options input with validation
 * - NmapResultsTable: Host/port results with expandable rows
 * - NmapScanHistory: Previous scans with timestamps
 * - NmapProgressIndicator: Real-time scan progress bar
 * - NmapAuditLog: Security audit trail
 */

import { useState, useEffect, useCallback } from "react";
import useAppStore from "../stores/useAppStore";

const BACKEND_URL = "http://127.0.0.1:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NmapPort {
  port: number;
  protocol: string;
  state: string;
  service: string;
  version: string;
  product: string;
  extra_info: string;
}

interface NmapOSMatch {
  name: string;
  accuracy: number;
  family: string;
  version: string;
}

interface NmapHost {
  ip: string;
  hostname: string | null;
  status: string;
  ports: NmapPort[];
  os_matches: NmapOSMatch[];
  latency: number;
}

interface NmapScanResult {
  scan_id: string;
  target: string;
  command: string;
  start_time: string;
  end_time: string | null;
  status: "running" | "completed" | "failed";
  hosts: NmapHost[];
  raw_xml: string | null;
  error: string | null;
  elapsed: number;
  hosts_up: number;
  hosts_down: number;
}

interface AuditEntry {
  id: number;
  timestamp: number;
  tool: string;
  action: string;
  target: string | null;
  status: string;
  result_summary: string | null;
  error: string | null;
  scan_id: string | null;
}

// ---------------------------------------------------------------------------
// Scan preset options
// ---------------------------------------------------------------------------

const SCAN_PRESETS = [
  { label: "Quick Scan", value: "-T4", description: "Fast scan of top 100 ports" },
  { label: "Intense Scan", value: "-T4 -A -v", description: "All ports, OS + version detection" },
  { label: "Stealth SYN", value: "-sS", description: "Stealthy SYN scan (requires root)" },
  { label: "Service Version", value: "-sV", description: "Detect service versions" },
  { label: "OS Detection", value: "-O", description: "OS fingerprinting (requires root)" },
  { label: "Comprehensive", value: "-sS -sV -O -A", description: "Full scan with all detections" },
];

// ---------------------------------------------------------------------------
// Port state color helper
// ---------------------------------------------------------------------------

function portStateColor(state: string): string {
  switch (state) {
    case "open":
      return "text-emerald-400";
    case "filtered":
      return "text-amber-400";
    case "closed":
      return "text-gray-500";
    default:
      return "text-text-secondary";
  }
}

function portStateBg(state: string): string {
  switch (state) {
    case "open":
      return "bg-emerald-500/10 border-emerald-500/20";
    case "filtered":
      return "bg-amber-500/10 border-amber-500/20";
    case "closed":
      return "bg-gray-500/10 border-gray-500/20";
    default:
      return "bg-bg-onyx border-border-subtle";
  }
}

// ---------------------------------------------------------------------------
// NmapScanForm
// ---------------------------------------------------------------------------

function NmapScanForm({
  onScan,
  scanning,
}: {
  onScan: (target: string, ports: string | null, options: string | null) => void;
  scanning: boolean;
}) {
  const [target, setTarget] = useState("");
  const [ports, setPorts] = useState("");
  const [options, setOptions] = useState("-T4");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!target.trim() || scanning) return;
    onScan(
      target.trim(),
      ports.trim() || null,
      options.trim() || null
    );
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 p-3">
      {/* Target input */}
      <div className="flex flex-col gap-1">
        <label className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-semibold">
          Target
        </label>
        <input
          type="text"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="IP (192.168.1.1), CIDR (192.168.1.0/24), or hostname"
          disabled={scanning}
          className="w-full h-8 px-2 text-[12px] font-mono bg-bg-onyx border border-border-subtle rounded text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:border-accent-cyan transition-colors"
        />
      </div>

      {/* Ports + Options row */}
      <div className="flex gap-2">
        <div className="flex flex-col gap-1 flex-1">
          <label className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-semibold">
            Ports
          </label>
          <input
            type="text"
            value={ports}
            onChange={(e) => setPorts(e.target.value)}
            placeholder="80,443,8080-8090 (optional)"
            disabled={scanning}
            className="w-full h-8 px-2 text-[12px] font-mono bg-bg-onyx border border-border-subtle rounded text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:border-accent-cyan transition-colors"
          />
        </div>
        <div className="flex flex-col gap-1 flex-1">
          <label className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-semibold">
            Scan Type
          </label>
          <select
            value={options}
            onChange={(e) => setOptions(e.target.value)}
            disabled={scanning}
            className="w-full h-8 px-2 text-[12px] font-mono bg-bg-onyx border border-border-subtle rounded text-text-primary focus:outline-none focus:border-accent-cyan transition-colors appearance-none cursor-pointer"
          >
            {SCAN_PRESETS.map((preset) => (
              <option key={preset.value} value={preset.value}>
                {preset.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Advanced options toggle */}
      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="text-[10px] font-mono text-text-secondary hover:text-accent-cyan transition-colors text-left"
      >
        {showAdvanced ? "Hide" : "Show"} advanced options
      </button>

      {showAdvanced && (
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-mono uppercase tracking-wider text-text-secondary font-semibold">
            Custom Nmap Flags
          </label>
          <input
            type="text"
            value={options}
            onChange={(e) => setOptions(e.target.value)}
            placeholder="-sV -O --version-intensity 5"
            disabled={scanning}
            className="w-full h-8 px-2 text-[12px] font-mono bg-bg-onyx border border-border-subtle rounded text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:border-accent-cyan transition-colors"
          />
          <span className="text-[9px] font-mono text-text-secondary/50">
            Only whitelisted flags allowed. Blocked: -D, -S, -f, --spoof-mac, etc.
          </span>
        </div>
      )}

      {/* Scan button */}
      <button
        type="submit"
        disabled={!target.trim() || scanning}
        className={`
          h-8 px-4 text-[11px] font-mono uppercase tracking-wider font-semibold rounded
          transition-all duration-150 border
          ${scanning
            ? "bg-amber-500/10 border-amber-500/30 text-amber-400 cursor-wait"
            : "bg-accent-cyan/10 border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/20 hover:border-accent-cyan/50 cursor-pointer"
          }
          disabled:opacity-50 disabled:cursor-not-allowed
        `}
      >
        {scanning ? (
          <span className="flex items-center gap-2 justify-center">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            Scanning...
          </span>
        ) : (
          <span className="flex items-center gap-2 justify-center">
            <span className="material-symbols-outlined text-[14px]">radar</span>
            Scan Network
          </span>
        )}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// NmapProgressIndicator
// ---------------------------------------------------------------------------

function NmapProgressIndicator({
  result,
}: {
  result: NmapScanResult | null;
}) {
  if (!result || result.status !== "running") return null;

  const phases = [
    { label: "Host discovery...", progress: 20 },
    { label: "Port scanning...", progress: 50 },
    { label: "Service detection...", progress: 75 },
    { label: "Finalizing...", progress: 90 },
  ];

  // Simple phase estimation based on elapsed time
  const elapsed = result.elapsed || 0;
  const phaseIndex = Math.min(Math.floor(elapsed / 15), phases.length - 1);
  const currentPhase = phases[phaseIndex];

  return (
    <div className="flex flex-col gap-2 px-3 py-2 bg-amber-500/5 border-b border-amber-500/10">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono text-amber-400 uppercase tracking-wider font-semibold">
          {currentPhase.label}
        </span>
        <span className="text-[10px] font-mono text-text-secondary">
          Target: {result.target}
        </span>
      </div>
      <div className="w-full h-1.5 bg-bg-onyx rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-amber-500 to-accent-cyan rounded-full transition-all duration-500 ease-out"
          style={{ width: `${currentPhase.progress}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NmapResultsTable
// ---------------------------------------------------------------------------

function NmapResultsTable({ result }: { result: NmapScanResult | null }) {
  const [expandedHost, setExpandedHost] = useState<string | null>(null);

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 py-12">
        <span className="material-symbols-outlined text-[32px] opacity-20 text-text-secondary">
          shield
        </span>
        <span className="text-[11px] font-mono text-text-secondary">
          No scan results yet
        </span>
        <span className="text-[10px] font-mono text-text-secondary/50">
          Enter a target above and click Scan Network
        </span>
      </div>
    );
  }

  if (result.status === "failed") {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 py-8 px-4">
        <span className="material-symbols-outlined text-[28px] text-red-400">
          error
        </span>
        <span className="text-[11px] font-mono text-red-400 text-center">
          Scan Failed
        </span>
        <span className="text-[10px] font-mono text-text-secondary text-center max-w-md">
          {result.error}
        </span>
      </div>
    );
  }

  if (result.status === "running") {
    return <NmapProgressIndicator result={result} />;
  }

  const hosts = result.hosts;
  if (hosts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 py-8">
        <span className="material-symbols-outlined text-[28px] text-text-secondary/30">
          search_off
        </span>
        <span className="text-[11px] font-mono text-text-secondary">
          No hosts discovered
        </span>
        <span className="text-[10px] font-mono text-text-secondary/50">
          Target: {result.target} — {result.hosts_up} up, {result.hosts_down} down
        </span>
      </div>
    );
  }

  const openPorts = hosts.reduce(
    (sum, h) => sum + h.ports.filter((p) => p.state === "open").length,
    0
  );

  return (
    <div className="flex flex-col h-full overflow-auto">
      {/* Summary bar */}
      <div className="flex items-center gap-4 px-3 py-2 border-b border-border-subtle bg-bg-onyx/50">
        <span className="text-[10px] font-mono text-emerald-400 font-semibold uppercase tracking-wider">
          {hosts.length} host{hosts.length !== 1 ? "s" : ""} discovered
        </span>
        <span className="text-[10px] font-mono text-accent-cyan">
          {openPorts} open port{openPorts !== 1 ? "s" : ""}
        </span>
        <span className="text-[10px] font-mono text-text-secondary">
          {result.elapsed.toFixed(1)}s
        </span>
        <div className="flex-1" />
        <button
          onClick={() => {
            const json = JSON.stringify(result, null, 2);
            const blob = new Blob([json], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `nmap-scan-${result.scan_id}.json`;
            a.click();
            URL.revokeObjectURL(url);
          }}
          className="text-[9px] font-mono text-text-secondary hover:text-accent-cyan transition-colors cursor-pointer"
        >
          Export JSON
        </button>
      </div>

      {/* Host rows */}
      <div className="flex-1 overflow-auto">
        {hosts.map((host) => {
          const isExpanded = expandedHost === host.ip;
          const openHostPorts = host.ports.filter((p) => p.state === "open");

          return (
            <div key={host.ip} className="border-b border-border-subtle">
              {/* Host header */}
              <button
                onClick={() => setExpandedHost(isExpanded ? null : host.ip)}
                className="w-full flex items-center gap-3 px-3 py-2 hover:bg-bg-onyx/50 transition-colors cursor-pointer text-left"
              >
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    host.status === "up"
                      ? "bg-emerald-400"
                      : "bg-gray-500"
                  }`}
                />
                <span className="text-[12px] font-mono text-text-primary font-semibold">
                  {host.ip}
                </span>
                {host.hostname && (
                  <span className="text-[10px] font-mono text-text-secondary">
                    ({host.hostname})
                  </span>
                )}
                <span
                  className={`text-[10px] font-mono ${portStateColor("open")} ml-auto`}
                >
                  {openHostPorts.length} open
                </span>
                <span
                  className={`material-symbols-outlined text-[14px] text-text-secondary transition-transform ${
                    isExpanded ? "rotate-180" : ""
                  }`}
                >
                  expand_more
                </span>
              </button>

              {/* Expanded port list */}
              {isExpanded && (
                <div className="px-3 pb-2">
                  {/* OS detection */}
                  {host.os_matches.length > 0 && (
                    <div className="mb-2 px-2 py-1 bg-purple-500/5 border border-purple-500/10 rounded">
                      <span className="text-[9px] font-mono text-purple-400 uppercase tracking-wider font-semibold">
                        OS Detection
                      </span>
                      {host.os_matches.slice(0, 3).map((os, i) => (
                        <div key={i} className="text-[10px] font-mono text-text-secondary ml-2">
                          {os.name} ({os.accuracy}% accuracy)
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Port table */}
                  {host.ports.length > 0 ? (
                    <table className="w-full text-[10px] font-mono">
                      <thead>
                        <tr className="text-text-secondary/50 border-b border-border-subtle">
                          <th className="text-left py-1 px-2 w-16">Port</th>
                          <th className="text-left py-1 px-2 w-16">State</th>
                          <th className="text-left py-1 px-2 w-24">Service</th>
                          <th className="text-left py-1 px-2">Version</th>
                        </tr>
                      </thead>
                      <tbody>
                        {host.ports.map((port, i) => (
                          <tr
                            key={i}
                            className={`border-b border-border-subtle/30 ${portStateBg(port.state)}`}
                          >
                            <td className="py-1 px-2 text-text-primary">
                              {port.port}/{port.protocol}
                            </td>
                            <td className={`py-1 px-2 ${portStateColor(port.state)}`}>
                              {port.state}
                            </td>
                            <td className="py-1 px-2 text-text-secondary">
                              {port.service || "—"}
                            </td>
                            <td className="py-1 px-2 text-text-secondary">
                              {[port.product, port.version, port.extra_info]
                                .filter(Boolean)
                                .join(" ") || "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <span className="text-[10px] font-mono text-text-secondary/50">
                      No ports found
                    </span>
                  )}
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
// NmapScanHistory
// ---------------------------------------------------------------------------

function NmapScanHistory({
  history,
  onSelect,
  selectedScanId,
}: {
  history: NmapScanResult[];
  onSelect: (result: NmapScanResult) => void;
  selectedScanId: string | null;
}) {
  if (history.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 py-8">
        <span className="material-symbols-outlined text-[24px] text-text-secondary/20">
          history
        </span>
        <span className="text-[10px] font-mono text-text-secondary/50">
          No previous scans
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col overflow-auto">
      {history.map((scan) => (
        <button
          key={scan.scan_id}
          onClick={() => onSelect(scan)}
          className={`
            flex items-center gap-3 px-3 py-2 border-b border-border-subtle
            transition-colors cursor-pointer text-left w-full
            ${selectedScanId === scan.scan_id
              ? "bg-accent-cyan/5 border-l-2 border-l-accent-cyan"
              : "hover:bg-bg-onyx/50 border-l-2 border-l-transparent"
            }
          `}
        >
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${
              scan.status === "completed"
                ? "bg-emerald-400"
                : scan.status === "failed"
                ? "bg-red-400"
                : "bg-amber-400 animate-pulse"
            }`}
          />
          <div className="flex flex-col flex-1 min-w-0">
            <span className="text-[11px] font-mono text-text-primary truncate">
              {scan.target}
            </span>
            <span className="text-[9px] font-mono text-text-secondary">
              {scan.start_time} · {scan.hosts_up} host{scan.hosts_up !== 1 ? "s" : ""} · {scan.elapsed.toFixed(1)}s
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// NmapAuditLog
// ---------------------------------------------------------------------------

function NmapAuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchAuditLog = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${BACKEND_URL}/api/tools/nmap/audit?limit=50`, {
        signal: AbortSignal.timeout(5000),
      });
      if (resp.ok) {
        const data = await resp.json();
        setEntries(data.entries || []);
      }
    } catch {
      // Backend not available
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAuditLog();
  }, [fetchAuditLog]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-[11px] text-text-secondary font-mono">
        Loading audit log...
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 py-8">
        <span className="material-symbols-outlined text-[24px] text-text-secondary/20">
          fact_check
        </span>
        <span className="text-[10px] font-mono text-text-secondary/50">
          No audit entries yet
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col overflow-auto">
      <div className="flex items-center justify-between px-3 py-1 border-b border-border-subtle">
        <span className="text-[10px] font-mono text-text-secondary uppercase tracking-wider font-semibold">
          Audit Log
        </span>
        <button
          onClick={fetchAuditLog}
          className="text-[9px] font-mono text-text-secondary hover:text-accent-cyan transition-colors cursor-pointer"
        >
          Refresh
        </button>
      </div>
      {entries.map((entry) => (
        <div
          key={entry.id}
          className="flex items-start gap-2 px-3 py-1.5 border-b border-border-subtle/50"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
              entry.status === "completed"
                ? "bg-emerald-400"
                : entry.status === "failed" || entry.status === "blocked"
                ? "bg-red-400"
                : entry.status === "rate_limited"
                ? "bg-amber-400"
                : "bg-accent-cyan"
            }`}
          />
          <div className="flex flex-col min-w-0">
            <span className="text-[10px] font-mono text-text-primary">
              {entry.action}: {entry.target || "N/A"} — {entry.status}
            </span>
            <span className="text-[9px] font-mono text-text-secondary/60">
              {new Date(entry.timestamp * 1000).toLocaleString()}
              {entry.error && ` · ${entry.error}`}
              {entry.result_summary && ` · ${entry.result_summary}`}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SecurityPanel (main)
// ---------------------------------------------------------------------------

type SecuritySubTab = "scanner" | "results" | "history" | "audit";

export default function SecurityPanel() {
  const agentMode = useAppStore((s) => s.agentMode);
  const [subTab, setSubTab] = useState<SecuritySubTab>("scanner");
  const [scanning, setScanning] = useState(false);
  const [currentResult, setCurrentResult] = useState<NmapScanResult | null>(null);
  const [scanHistory, setScanHistory] = useState<NmapScanResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [nmapAvailable, setNmapAvailable] = useState<boolean | null>(null);

  // Check nmap availability
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const resp = await fetch(`${BACKEND_URL}/api/tools/nmap/status`, {
          signal: AbortSignal.timeout(3000),
        });
        if (resp.ok) {
          const data = await resp.json();
          setNmapAvailable(data.available);
        } else {
          setNmapAvailable(false);
        }
      } catch {
        setNmapAvailable(false);
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Run scan
  const handleScan = useCallback(
    async (target: string, ports: string | null, options: string | null) => {
      setScanning(true);
      setError(null);
      setCurrentResult(null);

      try {
        const body: Record<string, unknown> = {
          target,
          allow_private: true,
          allow_localhost: false,
          timeout: 120,
        };
        if (ports) body.ports = ports;
        if (options) body.options = options;

        const resp = await fetch(`${BACKEND_URL}/api/tools/nmap`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: AbortSignal.timeout(310000), // 5min + buffer
        });

        const data = await resp.json();

        if (!resp.ok) {
          setError(data.detail || `Scan failed: ${resp.status}`);
          setScanning(false);
          return;
        }

        const result: NmapScanResult = data;
        setCurrentResult(result);
        setScanHistory((prev) => [result, ...prev]);
        setSubTab("results");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Scan failed");
      } finally {
        setScanning(false);
      }
    },
    []
  );

  // Quick action handlers
  const handleQuickScan = useCallback(() => {
    handleScan("192.168.1.0/24", "80,443,8080", "-T4");
  }, [handleScan]);

  const handleScanLocalhost = useCallback(() => {
    handleScan("127.0.0.1", "1-1000", "-sV");
  }, [handleScan]);

  const SUB_TABS: { id: SecuritySubTab; label: string; icon: string }[] = [
    { id: "scanner", label: "Scanner", icon: "radar" },
    { id: "results", label: "Results", icon: "table_chart" },
    { id: "history", label: "History", icon: "history" },
    { id: "audit", label: "Audit", icon: "fact_check" },
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
              {tab.id === "results" && currentResult && currentResult.status === "completed" && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              )}
              {tab.id === "results" && scanning && (
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              )}
            </button>
          );
        })}
        <div className="flex-1" />
        {/* Nmap availability indicator */}
        <div className="flex items-center gap-1.5 pr-2">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              nmapAvailable === null
                ? "bg-text-secondary/30"
                : nmapAvailable
                ? "bg-emerald-400"
                : "bg-red-400"
            }`}
          />
          <span className="text-[9px] text-text-secondary">
            {nmapAvailable === null
              ? "checking..."
              : nmapAvailable
              ? "nmap ready"
              : "nmap not found"}
          </span>
        </div>
      </div>

      {/* Security mode quick actions */}
      {agentMode === "security" && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border-subtle bg-emerald-500/5">
          <span className="material-symbols-outlined text-[12px] text-emerald-400">shield</span>
          <span className="text-[9px] font-mono text-emerald-400 uppercase tracking-wider font-semibold">
            Security Mode
          </span>
          <div className="flex gap-1.5 ml-3">
            <button
              onClick={handleQuickScan}
              disabled={scanning || !nmapAvailable}
              className="text-[9px] font-mono px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 rounded text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-50 cursor-pointer"
            >
              Scan Network
            </button>
            <button
              onClick={handleScanLocalhost}
              disabled={scanning || !nmapAvailable}
              className="text-[9px] font-mono px-2 py-0.5 bg-accent-cyan/10 border border-accent-cyan/20 rounded text-accent-cyan hover:bg-accent-cyan/20 transition-colors disabled:opacity-50 cursor-pointer"
            >
              Scan Localhost
            </button>
          </div>
        </div>
      )}

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

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {subTab === "scanner" && (
          <NmapScanForm onScan={handleScan} scanning={scanning} />
        )}
        {subTab === "results" && (
          <NmapResultsTable result={currentResult} />
        )}
        {subTab === "history" && (
          <NmapScanHistory
            history={scanHistory}
            onSelect={(r) => {
              setCurrentResult(r);
              setSubTab("results");
            }}
            selectedScanId={currentResult?.scan_id ?? null}
          />
        )}
        {subTab === "audit" && <NmapAuditLog />}
      </div>
    </div>
  );
}
