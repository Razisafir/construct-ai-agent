import { useEffect } from "react";
import {
  Terminal,
  MessageSquare,
  Bot,
  Brain,
  Wrench,
  Plug,
  Monitor,
  Users,
  Zap,
  GitPullRequest,
  X,
  ChevronUp,
} from "lucide-react";
import useAppStore from "../stores/useAppStore";
import { useDiffStore } from "../stores/useDiffStore";
import DiffPanel from "./DiffPanel";

const COLORS = {
  base: "#0c0c10",
  surface1: "#12121a",
  surface2: "#1a1a24",
  surface3: "#22222e",
  accent: "#6366f1",
  textPrimary: "#e8e8ec",
  textSecondary: "#94949c",
  muted: "#6b6b73",
  dim: "#4a4a52",
  border: "rgba(255,255,255,0.04)",
  success: "#22c55e",
  error: "#ef4444",
  warning: "#f59e0b",
};

interface Tab {
  id: string;
  icon: React.ReactNode;
  label: string;
  badge?: number;
}

function Panel() {
  const panelTab = useAppStore((s) => s.panelTab);
  const setPanelTab = useAppStore((s) => s.setPanelTab);
  const togglePanel = useAppStore((s) => s.togglePanel);
  const pendingDiffCount = useDiffStore((s) => s.getPendingCount());

  // Listen for construct:panel-tab events from command palette / keyboard shortcuts
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.tab) {
        setPanelTab(detail.tab);
      }
    };
    window.addEventListener("construct:panel-tab", handler);
    return () => window.removeEventListener("construct:panel-tab", handler);
  }, [setPanelTab]);

  const tabs: Tab[] = [
    { id: "terminal", icon: <Terminal size={13} />, label: "Terminal" },
    { id: "chat", icon: <MessageSquare size={13} />, label: "Chat" },
    { id: "agent", icon: <Bot size={13} />, label: "Agent" },
    { id: "memory", icon: <Brain size={13} />, label: "Memory" },
    { id: "changes", icon: <GitPullRequest size={13} />, label: "Changes", badge: pendingDiffCount || undefined },
    { id: "skills", icon: <Wrench size={13} />, label: "Skills" },
    { id: "mcp", icon: <Plug size={13} />, label: "MCP" },
    { id: "screen", icon: <Monitor size={13} />, label: "Screen" },
    { id: "agents", icon: <Users size={13} />, label: "Agents" },
    { id: "auto", icon: <Zap size={13} />, label: "Auto" },
  ];

  const renderTerminal = () => (
    <div
      className="font-['Geist_Mono','JetBrains_Mono',monospace] text-[11px] leading-[18px] p-2"
    >
      <div style={{ color: COLORS.muted }}>$ construct --version</div>
      <div style={{ color: COLORS.textPrimary }}>0.1.0-alpha</div>
      <div className="mt-1" style={{ color: COLORS.muted }}>$ npm run dev</div>
      <div style={{ color: COLORS.success }}>vite v6.0 ready in 342ms</div>
      <div style={{ color: COLORS.accent }}>
        local: http://localhost:5173/
      </div>
      <div className="mt-1" style={{ color: COLORS.muted }}>
        $ cargo tauri dev
      </div>
      <div style={{ color: COLORS.textPrimary }}>Running ConstructApp...</div>
      <div className="mt-1" style={{ color: COLORS.accent }}>_</div>
    </div>
  );

  const renderChat = () => (
    <div className="p-2">
      <div
        className="text-[11px] mb-2"
        style={{ color: COLORS.muted }}
      >
        AI assistant panel. Type to send messages.
      </div>
      <div
        className="flex items-center gap-1.5"
      >
        <input
          type="text"
          placeholder="Ask anything..."
          className="flex-1 h-[26px] px-2 rounded-[2px] text-[11px] font-['Geist_Mono','JetBrains_Mono',monospace] outline-none"
          style={{
            backgroundColor: COLORS.base,
            border: `1px solid ${COLORS.border}`,
            color: COLORS.textPrimary,
          }}
        />
        <button
          className="h-[26px] px-3 rounded-[2px] text-[10px] font-semibold font-['Geist_Mono','JetBrains_Mono',monospace] text-white uppercase tracking-[0.06em] cursor-pointer border-0"
          style={{ backgroundColor: COLORS.accent }}
        >
          Send
        </button>
      </div>
    </div>
  );

  const renderAgent = () => (
    <div className="p-2">
      <div
        className="text-[10px] uppercase tracking-[0.08em] mb-2 font-semibold"
        style={{ color: COLORS.muted }}
      >
        Agent Status
      </div>
      <div
        className="flex items-center gap-2 mb-1.5"
      >
        <span className="text-[10px] w-[60px]" style={{ color: COLORS.dim }}>State</span>
        <span className="text-[11px]" style={{ color: COLORS.textSecondary }}>
          idle
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[10px] w-[60px]" style={{ color: COLORS.dim }}>Model</span>
        <span className="text-[11px]" style={{ color: COLORS.textSecondary }}>
          claude-sonnet-4-20250514
        </span>
      </div>
    </div>
  );

  const renderMemory = () => (
    <div className="p-2">
      <div
        className="text-[10px] uppercase tracking-[0.08em] mb-2 font-semibold"
        style={{ color: COLORS.muted }}
      >
        Memory Usage
      </div>
      <div
        className="font-['Geist_Mono','JetBrains_Mono',monospace] text-[11px] leading-[18px]"
        style={{ color: COLORS.textSecondary }}
      >
        <div>Contexts: 1,247</div>
        <div>Vectors: 8,932</div>
        <div>Tokens: 12,456 / 200,000</div>
        <div>Usage: 6.2%</div>
      </div>
    </div>
  );

  const renderPlaceholder = (label: string) => (
    <div className="p-2">
      <div
        className="text-[11px] font-['Geist_Mono','JetBrains_Mono',monospace]"
        style={{ color: COLORS.muted }}
      >
        {label} panel content.
      </div>
    </div>
  );

  const renderContent = () => {
    switch (panelTab) {
      case "terminal":
        return renderTerminal();
      case "chat":
        return renderChat();
      case "agent":
        return renderAgent();
      case "memory":
        return renderMemory();
      case "changes":
        return <DiffPanel />;
      case "skills":
        return renderPlaceholder("Skills");
      case "mcp":
        return renderPlaceholder("MCP");
      case "screen":
        return renderPlaceholder("Screen");
      case "agents":
        return renderPlaceholder("Multi-agent");
      case "auto":
        return renderPlaceholder("Autonomous");
      default:
        return renderTerminal();
    }
  };

  return (
    <div
      className="flex flex-col w-full h-full"
      style={{ backgroundColor: COLORS.surface1 }}
    >
      {/* Tab Bar */}
      <div
        className="flex items-center justify-between h-7 shrink-0"
        style={{
          backgroundColor: COLORS.base,
          borderBottom: `1px solid ${COLORS.border}`,
        }}
      >
        <div className="flex overflow-hidden flex-1">
          {tabs.map((tab) => {
            const isActive = panelTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setPanelTab(tab.id)}
                className="flex items-center h-full px-[10px] gap-[5px] border-0 cursor-pointer shrink-0 whitespace-nowrap font-['Geist_Mono','JetBrains_Mono',monospace] text-[10px] uppercase tracking-[0.08em] font-semibold transition-colors duration-[50ms]"
                style={{
                  borderRight: `1px solid ${COLORS.border}`,
                  borderBottom: isActive
                    ? `2px solid ${COLORS.accent}`
                    : `2px solid transparent`,
                  backgroundColor: isActive ? COLORS.surface2 : "transparent",
                  color: isActive ? COLORS.textPrimary : COLORS.muted,
                  position: "relative",
                }}
              >
                {tab.icon}
                <span>{tab.label}</span>
                {tab.badge && tab.badge > 0 && (
                  <span
                    style={{
                      position: "absolute",
                      top: 2,
                      right: 4,
                      fontSize: 7,
                      fontWeight: 700,
                      lineHeight: 1,
                      padding: "1px 3px",
                      borderRadius: 9999,
                      backgroundColor: COLORS.warning,
                      color: COLORS.base,
                    }}
                  >
                    {tab.badge > 9 ? "9+" : tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        <div className="flex items-center pr-1 shrink-0">
          <button
            onClick={togglePanel}
            className="flex items-center justify-center w-[22px] h-[22px] rounded-[2px] border-0 cursor-pointer bg-transparent"
            style={{ color: COLORS.muted }}
            title="Close panel"
          >
            <ChevronUp size={12} />
          </button>
          <button
            onClick={togglePanel}
            className="flex items-center justify-center w-[22px] h-[22px] rounded-[2px] border-0 cursor-pointer bg-transparent"
            style={{ color: COLORS.muted }}
            title="Close"
          >
            <X size={12} />
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div
        className="flex-1 overflow-auto"
        style={{ backgroundColor: COLORS.surface1 }}
      >
        {renderContent()}
      </div>
    </div>
  );
}

export default Panel;
