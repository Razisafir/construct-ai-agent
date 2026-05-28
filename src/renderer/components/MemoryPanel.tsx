import { useState, useRef, useEffect, useCallback } from "react";
import {
  MessagesSquare,
  FileCode,
  Settings,
  Search,
  Brain,
  Send,
  ChevronDown,
  ChevronRight,
  User,
  Bot,
  Cpu,
  GitCommit,
  Clock,
  Sparkles,
} from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import useAppStore from "../stores/useAppStore";
import type {
  ConversationMessage,
  ContextItem,
  Preference,
  CodeEvent,
  MemoryTab,
} from "../types/memory";

// ─── Tauri Command Wrappers ───────────────────────────────────────

const recordConversation = async (msg: ConversationMessage) => {
  await invoke("record_conversation", { message: msg });
};

const recallContext = async (
  query: string,
  limit?: number
): Promise<ContextItem[]> => {
  return await invoke("recall_context", { query, limit });
};

const getPreferences = async (): Promise<Preference[]> => {
  return await invoke("get_preferences");
};

// ─── Helpers ──────────────────────────────────────────────────────

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDate(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function generateId(): string {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

// ─── Demo Data ────────────────────────────────────────────────────

const DEMO_CONVERSATIONS: ConversationMessage[] = [
  {
    id: "1",
    timestamp: Date.now() - 1000 * 60 * 30,
    role: "user",
    content:
      "Can you help me refactor the authentication middleware to use JWT tokens instead of session cookies?",
  },
  {
    id: "2",
    timestamp: Date.now() - 1000 * 60 * 29,
    role: "assistant",
    content:
      "I'll help you refactor the auth middleware to use JWT. First, let's look at the current session-based implementation and then create a JWT strategy.",
  },
  {
    id: "3",
    timestamp: Date.now() - 1000 * 60 * 25,
    role: "system",
    content:
      "Code event recorded: Modified src/middleware/auth.ts — switched from express-session to jsonwebtoken",
  },
  {
    id: "4",
    timestamp: Date.now() - 1000 * 60 * 20,
    role: "user",
    content:
      "Great! Now let's add refresh token rotation and secure token storage.",
  },
  {
    id: "5",
    timestamp: Date.now() - 1000 * 60 * 15,
    role: "assistant",
    content:
      "Good idea. I'll implement refresh token rotation with a sliding expiration window. The refresh tokens will be stored in an httpOnly cookie.",
  },
  {
    id: "6",
    timestamp: Date.now() - 1000 * 60 * 5,
    role: "user",
    content: "Please also add rate limiting for the token refresh endpoint.",
  },
  {
    id: "7",
    timestamp: Date.now() - 1000 * 60 * 2,
    role: "assistant",
    content:
      "Rate limiting added using express-rate-limit. The refresh endpoint is now capped at 5 requests per minute per IP with a 15-minute block window after exceeded attempts.",
  },
];

const DEMO_CODE_EVENTS: CodeEvent[] = [
  {
    id: "ce1",
    timestamp: Date.now() - 1000 * 60 * 60 * 2,
    file_path: "src/middleware/auth.ts",
    change_type: "refactor",
    summary: "Migrated from session-based auth to JWT tokens",
  },
  {
    id: "ce2",
    timestamp: Date.now() - 1000 * 60 * 45,
    file_path: "src/routes/login.ts",
    change_type: "modify",
    summary: "Updated login route to issue JWT access & refresh tokens",
  },
  {
    id: "ce3",
    timestamp: Date.now() - 1000 * 60 * 30,
    file_path: "src/utils/token.ts",
    change_type: "create",
    summary: "Created token utilities for sign, verify, and refresh operations",
  },
  {
    id: "ce4",
    timestamp: Date.now() - 1000 * 60 * 20,
    file_path: "src/middleware/rateLimit.ts",
    change_type: "create",
    summary: "Added rate limiting middleware for auth endpoints",
  },
  {
    id: "ce5",
    timestamp: Date.now() - 1000 * 60 * 10,
    file_path: "src/types/auth.d.ts",
    change_type: "modify",
    summary: "Extended auth types with JwtPayload and TokenPair interfaces",
  },
  {
    id: "ce6",
    timestamp: Date.now() - 1000 * 60 * 5,
    file_path: "src/config/auth.ts",
    change_type: "refactor",
    summary: "Consolidated auth configuration into single config object",
  },
];

const DEMO_PREFERENCES: Preference[] = [
  {
    key: "auth.strategy",
    value: "jwt",
    confidence: 0.95,
    last_updated: Date.now() - 1000 * 60 * 60 * 2,
  },
  {
    key: "code.style.semicolons",
    value: "true",
    confidence: 0.88,
    last_updated: Date.now() - 1000 * 60 * 60 * 24,
  },
  {
    key: "framework.backend",
    value: "express",
    confidence: 0.92,
    last_updated: Date.now() - 1000 * 60 * 60 * 5,
  },
  {
    key: "language.primary",
    value: "typescript",
    confidence: 0.97,
    last_updated: Date.now() - 1000 * 60 * 60 * 48,
  },
  {
    key: "db.orm",
    value: "prisma",
    confidence: 0.76,
    last_updated: Date.now() - 1000 * 60 * 60 * 12,
  },
  {
    key: "testing.framework",
    value: "vitest",
    confidence: 0.83,
    last_updated: Date.now() - 1000 * 60 * 60 * 36,
  },
];

const DEMO_SEARCH_RESULTS: ContextItem[] = [
  {
    id: "sr1",
    source: "code_event",
    content:
      "Rate limiting middleware uses express-rate-limit with a 5 req/min window...",
    relevance: 0.94,
    timestamp: Date.now() - 1000 * 60 * 20,
  },
  {
    id: "sr2",
    source: "conversation",
    content:
      "User requested refresh token rotation with sliding expiration window...",
    relevance: 0.87,
    timestamp: Date.now() - 1000 * 60 * 15,
  },
  {
    id: "sr3",
    source: "preference",
    content: "Preference: auth.strategy = jwt (confidence: 95%)",
    relevance: 0.72,
    timestamp: Date.now() - 1000 * 60 * 60 * 2,
  },
  {
    id: "sr4",
    source: "code_event",
    content:
      "Token utilities support sign, verify, and refresh operations with RS256...",
    relevance: 0.68,
    timestamp: Date.now() - 1000 * 60 * 30,
  },
];

// ─── Sub-Components ───────────────────────────────────────────────

function RoleBadge({ role }: { role: ConversationMessage["role"] }) {
  const config = {
    user: {
      icon: <User size={10} />,
      label: "You",
      classes: "bg-construct-accent-primary/15 text-construct-accent-primary border-construct-accent-primary/25",
    },
    assistant: {
      icon: <Bot size={10} />,
      label: "AI",
      classes: "bg-construct-semantic-success/15 text-construct-semantic-success border-construct-semantic-success/25",
    },
    system: {
      icon: <Cpu size={10} />,
      label: "System",
      classes: "bg-construct-text-muted/10 text-construct-text-muted border-construct-text-muted/20",
    },
  };
  const c = config[role];
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium border rounded ${c.classes}`}
    >
      {c.icon}
      {c.label}
    </span>
  );
}

function ChangeTypeBadge({ type }: { type: CodeEvent["change_type"] }) {
  const config = {
    create: { label: "CREATE", classes: "bg-construct-semantic-success/15 text-construct-semantic-success border-construct-semantic-success/25" },
    modify: { label: "MODIFY", classes: "bg-construct-accent-primary/15 text-construct-accent-primary border-construct-accent-primary/25" },
    delete: { label: "DELETE", classes: "bg-construct-semantic-error/15 text-construct-semantic-error border-construct-semantic-error/25" },
    refactor: { label: "REFACTOR", classes: "bg-construct-semantic-warning/15 text-construct-semantic-warning border-construct-semantic-warning/25" },
  };
  const c = config[type];
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 text-[9px] font-bold tracking-wider border rounded ${c.classes}`}
    >
      {c.label}
    </span>
  );
}

function SourceBadge({ source }: { source: ContextItem["source"] }) {
  const config = {
    conversation: { label: "Conversation", classes: "bg-blue-500/15 text-blue-400 border-blue-500/25" },
    code_event: { label: "Code", classes: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25" },
    preference: { label: "Preference", classes: "bg-purple-500/15 text-purple-400 border-purple-500/25" },
  };
  const c = config[source];
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 text-[9px] font-medium border rounded ${c.classes}`}
    >
      {c.label}
    </span>
  );
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  let colorClass = "bg-construct-semantic-success";
  if (pct < 60) colorClass = "bg-construct-semantic-error";
  else if (pct < 80) colorClass = "bg-construct-semantic-warning";

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-construct-border/50 rounded-full overflow-hidden">
        <div
          className={`h-full ${colorClass} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] text-construct-text-muted w-8 text-right">
        {pct}%
      </span>
    </div>
  );
}

// ─── Tab Content Components ───────────────────────────────────────

function ConversationsTab() {
  const conversations = useAppStore((s) => s.conversations);
  const addConversation = useAppStore((s) => s.addConversation);
  const [inputValue, setInputValue] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when conversations change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversations.length]);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSend = useCallback(async () => {
    if (!inputValue.trim()) return;
    const msg: ConversationMessage = {
      id: generateId(),
      timestamp: Date.now(),
      role: "user",
      content: inputValue.trim(),
    };
    addConversation(msg);
    setInputValue("");
    try {
      await recordConversation(msg);
    } catch {
      // Silently fail if Tauri command not registered
    }

    // Simulate assistant reply after a short delay
    setTimeout(() => {
      const reply: ConversationMessage = {
        id: generateId(),
        timestamp: Date.now(),
        role: "assistant",
        content: `I've noted your message about "${msg.content.slice(0, 40)}${msg.content.length > 40 ? "..." : ""}". This is a demo reply from the memory panel.`,
      };
      addConversation(reply);
      try {
        recordConversation(reply);
      } catch {
        // Silently fail
      }
    }, 800);
  }, [inputValue, addConversation]);

  return (
    <div className="flex flex-col h-full">
      {/* Messages list */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto pr-1 space-y-2">
        {conversations.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-construct-text-muted">
            <MessagesSquare size={24} className="mb-2 opacity-50" />
            <p className="text-xs">No conversation history yet</p>
          </div>
        )}
        {conversations.map((msg) => {
          const isExpanded = expandedIds.has(msg.id);
          const isLong = msg.content.length > 120;
          return (
            <div
              key={msg.id}
              className="group flex flex-col gap-1 p-2 rounded bg-construct-bg-primary-tertiary/50 border border-construct-border/40 hover:border-construct-border transition-colors"
            >
              <div className="flex items-center justify-between">
                <RoleBadge role={msg.role} />
                <span className="text-[10px] text-construct-text-muted">
                  {formatTime(msg.timestamp)}
                </span>
              </div>
              <p
                className={`text-xs text-construct-text-primary leading-relaxed ${
                  !isExpanded && isLong ? "line-clamp-2" : ""
                }`}
              >
                {msg.content}
              </p>
              {isLong && (
                <button
                  onClick={() => toggleExpand(msg.id)}
                  className="self-start flex items-center gap-0.5 text-[10px] text-construct-accent-primary hover:text-construct-accent-primary-primaryHover transition-colors"
                >
                  {isExpanded ? (
                    <>
                      <ChevronDown size={10} /> Show less
                    </>
                  ) : (
                    <>
                      <ChevronRight size={10} /> Show more
                    </>
                  )}
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Input */}
      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-construct-border">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Type a message..."
          className="flex-1 h-7 px-2.5 bg-construct-bg-primary border border-construct-border rounded text-xs text-construct-text-primary placeholder-construct-text-muted outline-none focus:border-construct-accent-primary transition-colors"
        />
        <button
          onClick={handleSend}
          disabled={!inputValue.trim()}
          className="flex items-center justify-center w-7 h-7 bg-construct-accent-primary hover:bg-construct-accent-primary-primaryHover disabled:opacity-40 disabled:hover:bg-construct-accent-primary text-construct-bg-primary-tertiary rounded transition-colors"
        >
          <Send size={12} />
        </button>
      </div>
    </div>
  );
}

function CodeEventsTab() {
  const [codeEvents] = useState<CodeEvent[]>(DEMO_CODE_EVENTS);

  return (
    <div className="flex flex-col h-full overflow-y-auto pr-1 space-y-1.5">
      {codeEvents.map((event) => (
        <div
          key={event.id}
          className="flex flex-col gap-1.5 p-2.5 rounded bg-construct-bg-primary-tertiary/50 border border-construct-border/40 hover:border-construct-border transition-colors"
        >
          <div className="flex items-center justify-between">
            <ChangeTypeBadge type={event.change_type} />
            <span className="text-[10px] text-construct-text-muted flex items-center gap-1">
              <Clock size={10} />
              {formatTime(event.timestamp)}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-construct-text-primary">
            <FileCode size={13} className="text-construct-text-muted shrink-0" />
            <span className="font-mono text-construct-accent-primary truncate">
              {event.file_path}
            </span>
          </div>
          <p className="text-[11px] text-construct-text-muted leading-relaxed">
            {event.summary}
          </p>
        </div>
      ))}
    </div>
  );
}

function PreferencesTab() {
  const [preferences, setPreferences] = useState<Preference[]>(DEMO_PREFERENCES);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Attempt to load real preferences from backend
    setLoading(true);
    getPreferences()
      .then((prefs) => {
        if (prefs && prefs.length > 0) setPreferences(prefs);
      })
      .catch(() => {
        // Fallback to demo data
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-construct-text-muted">
        <div className="animate-pulse text-xs">Loading preferences...</div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-2 overflow-y-auto pr-1">
      {preferences.map((pref) => (
        <div
          key={pref.key}
          className="flex flex-col gap-2 p-2.5 rounded bg-construct-bg-primary-tertiary/50 border border-construct-border/40 hover:border-construct-border transition-colors"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-construct-accent-primary truncate">
              {pref.key}
            </span>
            <span className="text-[10px] text-construct-text-muted flex items-center gap-1">
              <Clock size={10} />
              {formatDate(pref.last_updated)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-construct-text-primary font-medium">
              {pref.value}
            </span>
          </div>
          <ConfidenceBar confidence={pref.confidence} />
        </div>
      ))}
    </div>
  );
}

function SearchTab() {
  const memorySearchQuery = useAppStore((s) => s.memorySearchQuery);
  const setMemorySearchQuery = useAppStore((s) => s.setMemorySearchQuery);
  const memorySearchResults = useAppStore((s) => s.memorySearchResults);
  const setMemorySearchResults = useAppStore((s) => s.setMemorySearchResults);
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = useCallback(async () => {
    if (!memorySearchQuery.trim()) return;
    setIsSearching(true);
    try {
      const results = await recallContext(memorySearchQuery.trim(), 10);
      if (results && results.length > 0) {
        setMemorySearchResults(results);
      } else {
        // Fallback to demo results filtered by query
        const filtered = DEMO_SEARCH_RESULTS.filter((r) =>
          r.content.toLowerCase().includes(memorySearchQuery.toLowerCase())
        );
        setMemorySearchResults(
          filtered.length > 0 ? filtered : DEMO_SEARCH_RESULTS
        );
      }
    } catch {
      setMemorySearchResults(DEMO_SEARCH_RESULTS);
    } finally {
      setIsSearching(false);
    }
  }, [memorySearchQuery, setMemorySearchResults]);

  // Auto-search on query change with debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      if (memorySearchQuery.trim()) {
        handleSearch();
      } else {
        setMemorySearchResults(DEMO_SEARCH_RESULTS);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [memorySearchQuery]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col h-full">
      {/* Search input */}
      <div className="flex items-center gap-2 mb-3">
        <div className="flex-1 flex items-center gap-2 h-8 px-2.5 bg-construct-bg-primary border border-construct-border rounded focus-within:border-construct-accent-primary transition-colors">
          <Search size={13} className="text-construct-text-muted shrink-0" />
          <input
            type="text"
            value={memorySearchQuery}
            onChange={(e) => setMemorySearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch();
            }}
            placeholder="Search memory semantically..."
            className="flex-1 bg-transparent text-xs text-construct-text-primary placeholder-construct-text-muted outline-none"
          />
          {isSearching && (
            <div className="w-3.5 h-3.5 border-2 border-construct-accent-primary border-t-transparent rounded-full animate-spin" />
          )}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-2">
        {memorySearchResults.map((result) => {
          const pct = Math.round(result.relevance * 100);
          return (
            <div
              key={result.id}
              className="flex flex-col gap-1.5 p-2.5 rounded bg-construct-bg-primary-tertiary/50 border border-construct-border/40 hover:border-construct-border transition-colors"
            >
              <div className="flex items-center justify-between">
                <SourceBadge source={result.source} />
                <div className="flex items-center gap-1.5">
                  <Sparkles
                    size={10}
                    className={
                      pct >= 80
                        ? "text-construct-semantic-success"
                        : pct >= 50
                          ? "text-construct-semantic-warning"
                          : "text-construct-text-muted"
                    }
                  />
                  <span
                    className={`text-[10px] font-medium ${
                      pct >= 80
                        ? "text-construct-semantic-success"
                        : pct >= 50
                          ? "text-construct-semantic-warning"
                          : "text-construct-text-muted"
                    }`}
                  >
                    {pct}% match
                  </span>
                </div>
              </div>
              <p className="text-xs text-construct-text-primary leading-relaxed">
                {result.content}
              </p>
              <span className="text-[10px] text-construct-text-muted">
                {formatTime(result.timestamp)} · {formatDate(result.timestamp)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main MemoryPanel ─────────────────────────────────────────────

const subTabs: { id: MemoryTab; icon: React.ReactNode; label: string }[] = [
  {
    id: "conversations",
    icon: <MessagesSquare size={12} />,
    label: "Conversations",
  },
  { id: "code", icon: <FileCode size={12} />, label: "Code Events" },
  { id: "preferences", icon: <Settings size={12} />, label: "Preferences" },
  { id: "search", icon: <Search size={12} />, label: "Search" },
];

function MemoryPanel() {
  const memoryPanelTab = useAppStore((s) => s.memoryPanelTab);
  const setMemoryPanelTab = useAppStore((s) => s.setMemoryPanelTab);
  const conversations = useAppStore((s) => s.conversations);

  // Load demo conversations on first mount if empty
  useEffect(() => {
    const current = useAppStore.getState().conversations;
    if (current.length === 0) {
      useAppStore.getState().setConversations(DEMO_CONVERSATIONS);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const conversationCount = conversations.length;
  const codeEventCount = DEMO_CODE_EVENTS.length;
  const preferenceCount = DEMO_PREFERENCES.length;

  return (
    <div className="flex flex-col h-full">
      {/* ── Stats Bar ── */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-construct-bg-primary-tertiary border-b border-construct-border">
        <Brain size={12} className="text-construct-accent-primary shrink-0" />
        <div className="flex items-center gap-1.5">
          {/* Conversation chip */}
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/15 text-blue-400 border border-blue-500/20">
            <MessagesSquare size={9} />
            {conversationCount} Conversations
          </span>
          {/* Code chip */}
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
            <GitCommit size={9} />
            {codeEventCount} Code Changes
          </span>
          {/* Preference chip */}
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-purple-500/15 text-purple-400 border border-purple-500/20">
            <Settings size={9} />
            {preferenceCount} Preferences
          </span>
        </div>
      </div>

      {/* ── Sub-Tab Navigation ── */}
      <div className="flex items-center h-7 bg-construct-bg-primary-tertiary border-b border-construct-border">
        {subTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setMemoryPanelTab(tab.id)}
            className={`
              flex items-center h-7 px-3 gap-1.5 text-[11px] border-r border-construct-border
              transition-colors duration-100
              ${
                memoryPanelTab === tab.id
                  ? "bg-construct-bg-primary text-construct-text-primary border-t-2 border-t-construct-accent-primary"
                  : "text-construct-text-muted hover:text-construct-text-primary hover:bg-construct-bg-primary-elevated"
              }
            `}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ── Content Area ── */}
      <div className="flex-1 overflow-hidden p-3 min-h-0">
        {memoryPanelTab === "conversations" && <ConversationsTab />}
        {memoryPanelTab === "code" && <CodeEventsTab />}
        {memoryPanelTab === "preferences" && <PreferencesTab />}
        {memoryPanelTab === "search" && <SearchTab />}
      </div>
    </div>
  );
}

export default MemoryPanel;
