import { lazy, Suspense, useState, useCallback } from "react";

import ChatInput, { type FileAttachment } from "./ChatInput";

const AgentPanel = lazy(() => import("./AgentPanel"));
const MemoryPanel = lazy(() => import("./MemoryPanel"));

interface RightTab {
  id: string;
  icon: string;
  label: string;
}

const RIGHT_TABS: RightTab[] = [
  { id: "chat", icon: "chat", label: "Chat" },
  { id: "agent", icon: "smart_toy", label: "Agent" },
  { id: "memory", icon: "memory", label: "Memory" },
];

function RightSidebar() {
  const [activeTab, setActiveTab] = useState<string>("agent");
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);

  const handleChatSend = useCallback((message: string, _attachments: FileAttachment[]) => {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    // Placeholder: in production this would invoke the LLM
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Thinking..." },
      ]);
    }, 500);
  }, []);

  const renderContent = () => {
    switch (activeTab) {
      case "chat":
        return (
          <div className="flex flex-col h-full">
            {/* Messages area */}
            <div className="flex-1 overflow-auto p-3 flex flex-col gap-3">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-text-secondary">
                  <span className="material-symbols-outlined text-[32px] opacity-40">chat</span>
                  <span className="text-[11px] font-mono tracking-wider">No messages yet</span>
                  <span className="text-[10px] font-mono opacity-60">Type below to start a conversation</span>
                </div>
              )}
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`text-[12px] font-mono leading-5 p-2 rounded-md ${
                    msg.role === "user"
                      ? "bg-accent-cyan-dim text-text-primary ml-4"
                      : "bg-bg-onyx text-text-secondary mr-4 border border-border-subtle"
                  }`}
                >
                  {msg.content}
                </div>
              ))}
            </div>
            {/* Chat input */}
            <ChatInput onSend={handleChatSend} />
          </div>
        );

      case "agent":
        return (
          <Suspense
            fallback={
              <div className="flex items-center justify-center h-full text-[11px] text-text-secondary font-mono">
                loading agent...
              </div>
            }
          >
            <AgentPanel />
          </Suspense>
        );

      case "memory":
        return (
          <Suspense
            fallback={
              <div className="flex items-center justify-center h-full text-[11px] text-text-secondary font-mono">
                loading memory...
              </div>
            }
          >
            <MemoryPanel />
          </Suspense>
        );

      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col h-full bg-panel-bg font-mono">
      {/* Tab Bar */}
      <div className="flex items-center h-10 shrink-0 bg-bg-onyx border-b border-border-subtle">
        {RIGHT_TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                relative flex items-center h-full px-3 gap-1.5 border-0 cursor-pointer shrink-0
                whitespace-nowrap font-mono text-[10px] uppercase tracking-wider font-semibold
                transition-colors duration-[50ms]
                ${isActive
                  ? "text-accent-cyan border-b-2 border-b-accent-cyan bg-c-s2"
                  : "text-text-secondary border-b-2 border-b-transparent bg-transparent hover:text-text-primary"
                }
              `}
            >
              <span className="material-symbols-outlined text-[14px]">{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {renderContent()}
      </div>
    </div>
  );
}

export default RightSidebar;
