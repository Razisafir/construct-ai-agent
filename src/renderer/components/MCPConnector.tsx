import { useState, useCallback, useEffect } from "react";

/* ─── Types ─── */
interface MCPTool {
  name: string;
  description: string;
}

interface MCPServer {
  id: string;
  name: string;
  connected: boolean;
  url: string;
  tools: MCPTool[];
  tool_count: number;
  last_health_check?: string | null;
}

const BACKEND_URL = "http://127.0.0.1:8000";

export default function MCPConnector() {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newCommand, setNewCommand] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selected = servers.find((s) => s.id === selectedId) || null;

  // Fetch servers from backend
  const fetchServers = useCallback(async () => {
    try {
      const resp = await fetch(`${BACKEND_URL}/mcp/servers`, {
        signal: AbortSignal.timeout(3000),
      });
      if (resp.ok) {
        const data = await resp.json();
        setServers(data.servers || []);
        setError(null);
      }
    } catch {
      // Backend not available — show empty state
      setError("Backend not reachable");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchServers();
    const interval = setInterval(fetchServers, 15000); // Refresh every 15s
    return () => clearInterval(interval);
  }, [fetchServers]);

  // Connect to MCP server via command string
  const connectServer = useCallback(async () => {
    if (!newCommand.trim()) return;
    setIsConnecting(true);
    setError(null);

    try {
      const parts = newCommand.trim().split(" ");
      const command = parts[0];
      const args = parts.slice(1);

      const resp = await fetch(`${BACKEND_URL}/mcp/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, args }),
      });

      if (resp.ok) {
        const data = await resp.json();
        if (data.connected) {
          setNewCommand("");
          setShowAdd(false);
          fetchServers();
        } else {
          setError(data.error || "Connection failed");
        }
      } else {
        setError("Failed to connect — backend returned error");
      }
    } catch (err) {
      setError("Failed to connect — is the backend running?");
    } finally {
      setIsConnecting(false);
    }
  }, [newCommand, fetchServers]);

  // Disconnect from MCP server
  const disconnectServer = useCallback(async (serverName: string) => {
    try {
      await fetch(`${BACKEND_URL}/mcp/disconnect/${serverName}`, {
        method: "POST",
      });
      fetchServers();
      if (selectedId === serverName) setSelectedId(null);
    } catch {
      // Best effort
    }
  }, [fetchServers, selectedId]);

  const getStatusColor = (connected: boolean) => {
    return connected ? "var(--c-running, #4ade80)" : "var(--c-err, #f87171)";
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-[11px] font-mono text-c-text4">
        Loading MCP servers...
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden font-mono bg-c-base text-c-text">
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 shrink-0"
        style={{ borderBottom: "1px solid var(--c-border)", background: "var(--c-s1)" }}
      >
        <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--c-text2)" }}>
          MCP Servers
        </span>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider font-medium border-none rounded-sm cursor-pointer"
          style={{ background: "var(--c-s2)", color: "var(--c-text)" }}
        >
          {showAdd ? "CANCEL" : "+ ADD"}
        </button>
      </div>

      {/* Add Server Form */}
      {showAdd && (
        <div
          className="px-3 py-3 shrink-0"
          style={{ borderBottom: "1px solid var(--c-border)", background: "var(--c-s1)" }}
        >
          <label className="text-[9px] uppercase tracking-wider font-semibold block mb-1.5" style={{ color: "var(--c-text4)" }}>
            Server Command
          </label>
          <input
            type="text"
            value={newCommand}
            onChange={(e) => setNewCommand(e.target.value)}
            placeholder="npx @mcp/server-filesystem /path"
            className="w-full px-2 py-1.5 text-[11px] font-mono outline-none mb-2"
            style={{ background: "var(--c-base)", color: "var(--c-text)", border: "1px solid var(--c-border)" }}
            onKeyDown={(e) => {
              if (e.key === "Enter") connectServer();
            }}
          />
          <button
            onClick={connectServer}
            disabled={isConnecting || !newCommand.trim()}
            className="w-full py-1.5 text-[11px] font-mono uppercase tracking-wider font-medium border-none rounded-sm"
            style={{
              background: "var(--c-accent, #00f5ff)",
              color: "var(--c-base, #0c0e11)",
              cursor: isConnecting || !newCommand.trim() ? "default" : "pointer",
              opacity: isConnecting || !newCommand.trim() ? 0.5 : 1,
            }}
          >
            {isConnecting ? "Connecting..." : "Connect"}
          </button>
          <p className="text-[9px] mt-1.5" style={{ color: "var(--c-text4)" }}>
            Paste an MCP server command (stdio or HTTP). Examples: npx @mcp/server-filesystem /path, or a preset name like "github".
          </p>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div
          className="px-3 py-2 text-[10px] font-mono shrink-0"
          style={{ background: "rgba(248,113,113,0.1)", color: "var(--c-err, #f87171)", borderBottom: "1px solid rgba(248,113,113,0.2)" }}
        >
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 underline cursor-pointer bg-transparent border-none"
            style={{ color: "inherit" }}
          >
            dismiss
          </button>
        </div>
      )}

      {/* Server List */}
      {servers.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 px-4">
          <span className="material-symbols-outlined text-[32px] opacity-20">hub</span>
          <span className="text-[11px] text-center" style={{ color: "var(--c-text4)" }}>
            No MCP servers connected.
            <br />
            Click "+ ADD" to connect one.
          </span>
        </div>
      ) : (
        <div className="flex-1 overflow-auto">
          {servers.map((server) => {
            const isSelected = selectedId === server.id;
            return (
              <div
                key={server.id}
                onClick={() => setSelectedId(isSelected ? null : server.id)}
                className="flex items-center cursor-pointer px-3 py-2 transition-colors"
                style={{
                  background: isSelected ? "var(--c-s2)" : "transparent",
                  borderLeft: isSelected ? "2px solid var(--c-accent, #00f5ff)" : "2px solid transparent",
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = "var(--c-s2)";
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = "transparent";
                }}
              >
                {/* Status dot */}
                <span
                  className={`w-2 h-2 rounded-full flex-shrink-0 mr-2.5 ${server.connected ? "bg-green-500" : "bg-red-500"}`}
                />
                {/* Server name */}
                <span className="text-[11px] font-mono truncate flex-1" style={{ color: "var(--c-text)" }}>
                  {server.name}
                </span>
                {/* Tool count */}
                <span className="text-[9px] font-mono mr-2" style={{ color: "var(--c-text4)" }}>
                  {server.tool_count} tools
                </span>
                {/* Status */}
                <span
                  className="text-[9px] font-mono lowercase"
                  style={{ color: getStatusColor(server.connected) }}
                >
                  {server.connected ? "online" : "offline"}
                </span>
                {/* Disconnect button */}
                {server.connected && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      disconnectServer(server.id);
                    }}
                    className="ml-2 text-[9px] font-mono bg-transparent border-none cursor-pointer"
                    style={{ color: "var(--c-text4)" }}
                    title="Disconnect"
                  >
                    ✕
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Selected Server Detail Panel */}
      {selected && (
        <div
          className="shrink-0 max-h-[220px] overflow-auto"
          style={{ background: "var(--c-s2)", borderTop: "1px solid var(--c-border)" }}
        >
          <div className="flex items-center justify-between px-3 py-1.5" style={{ borderBottom: "1px solid var(--c-border)" }}>
            <span className="text-[11px] font-semibold" style={{ color: "var(--c-text)" }}>{selected.name}</span>
            <div className="flex items-center gap-3">
              <span className="text-[9px] font-mono lowercase" style={{ color: getStatusColor(selected.connected) }}>
                {selected.connected ? "online" : "offline"}
              </span>
              <button
                onClick={() => setSelectedId(null)}
                className="text-[10px] bg-none border-none cursor-pointer font-mono"
                style={{ color: "var(--c-text4)" }}
              >
                ✕
              </button>
            </div>
          </div>

          <div className="flex gap-5 px-3 py-1.5" style={{ borderBottom: "1px solid var(--c-border)" }}>
            <div>
              <span className="text-[9px] uppercase tracking-wider" style={{ color: "var(--c-text4)" }}>URL</span>
              <div className="text-[11px] font-mono" style={{ color: "var(--c-text2)" }}>{selected.url}</div>
            </div>
            <div>
              <span className="text-[9px] uppercase tracking-wider" style={{ color: "var(--c-text4)" }}>TOOLS</span>
              <div className="text-[11px] font-mono" style={{ color: "var(--c-text2)" }}>{selected.tool_count}</div>
            </div>
          </div>

          {/* Tools list */}
          <div className="px-3 py-1.5">
            <div className="text-[10px] font-medium uppercase tracking-wider mb-1.5" style={{ color: "var(--c-text3)" }}>
              Tools ({selected.tools.length})
            </div>
            {selected.tools.length === 0 ? (
              <div className="text-[11px]" style={{ color: "var(--c-text3)" }}>No tools available</div>
            ) : (
              <div className="grid gap-px" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))" }}>
                {selected.tools.map((tool) => (
                  <div key={tool.name} className="px-2 py-1 flex flex-col gap-[2px]" style={{ background: "var(--c-s3)" }}>
                    <span className="text-[10px] font-mono overflow-hidden text-ellipsis whitespace-nowrap" style={{ color: "var(--c-text)" }}>{tool.name}</span>
                    <span className="text-[9px] overflow-hidden text-ellipsis whitespace-nowrap" style={{ color: "var(--c-text3)" }}>{tool.description}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
