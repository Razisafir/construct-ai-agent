import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  Command as CommandIcon,
  Search,
  Play,
  Square,
  Pause,
  Code2,
  Layout,
  Bug,
  Eye,
  Shield,
  Server,
  MessageSquare,
  Brain,
  FolderTree,
  Settings,
  Trash2,
  Download,
  RefreshCw,
  Moon,
  ArrowRight,
  Keyboard,
  Bot,
  Terminal,
  Files,
  Wrench,
  Plug,
  PanelLeft,
  PanelBottom,
  Maximize,
  GitPullRequest,
  Check,
  X,
} from "lucide-react";
import { registry, type Command } from "../commands/registry";

/* ─────────────────────── icon mapping ─────────────────────── */

const iconMap: Record<string, React.ReactNode> = {
  command: <CommandIcon size={13} />,
  play: <Play size={13} />,
  square: <Square size={13} />,
  pause: <Pause size={13} />,
  "code-2": <Code2 size={13} />,
  layout: <Layout size={13} />,
  bug: <Bug size={13} />,
  eye: <Eye size={13} />,
  shield: <Shield size={13} />,
  server: <Server size={13} />,
  "message-square": <MessageSquare size={13} />,
  brain: <Brain size={13} />,
  "folder-tree": <FolderTree size={13} />,
  settings: <Settings size={13} />,
  "trash-2": <Trash2 size={13} />,
  download: <Download size={13} />,
  "refresh-cw": <RefreshCw size={13} />,
  moon: <Moon size={13} />,
  bot: <Bot size={13} />,
  terminal: <Terminal size={13} />,
  files: <Files size={13} />,
  wrench: <Wrench size={13} />,
  plug: <Plug size={13} />,
  "panel-left": <PanelLeft size={13} />,
  "panel-bottom": <PanelBottom size={13} />,
  maximize: <Maximize size={13} />,
  "git-pull-request": <GitPullRequest size={13} />,
  check: <Check size={13} />,
  x: <X size={13} />,
};

/* ─────────────────────── category styling ─────────────────────── */

const categoryColors: Record<string, string> = {
  agent: "var(--c-accent)",      // Cyan
  navigation: "var(--c-ok)",     // Green
  tools: "var(--c-gold)",        // Gold
  system: "var(--c-text3)",      // Gray
};

const categoryLabels: Record<string, string> = {
  agent: "Agent",
  navigation: "Navigation",
  tools: "Tools",
  system: "System",
};

/* ─────────────────────── exported type for backward compat ─────────────────────── */

export interface PaletteCommand {
  id: string;
  label: string;
  shortcut?: string;
  icon: React.ReactNode;
  category: string;
  action: () => void;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  /** @deprecated Use the registry instead — commands are now centrally managed */
  commands?: PaletteCommand[];
  /** @deprecated Use registry.subscribe or handleSelect prop instead */
  onCommandSelect?: (cmd: PaletteCommand) => void;
}

/* ─────────────────────── component ─────────────────────── */

function CommandPalette({ isOpen, onClose, onCommandSelect }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [allCommands, setAllCommands] = useState<Command[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // Subscribe to registry changes
  useEffect(() => {
    if (isOpen) {
      setAllCommands(registry.getAll());
      const unsubscribe = registry.subscribe(() => {
        setAllCommands(registry.getAll());
      });
      return unsubscribe;
    }
  }, [isOpen]);

  // Filter commands by query
  const filteredCommands = useMemo(() => {
    if (!query.trim()) return allCommands;
    return registry.search(query);
  }, [query, allCommands]);

  // Group by category
  const grouped = useMemo(() => {
    const map = new Map<string, Command[]>();
    filteredCommands.forEach((cmd) => {
      const list = map.get(cmd.category) ?? [];
      list.push(cmd);
      map.set(cmd.category, list);
    });
    return map;
  }, [filteredCommands]);

  // Build flat list with category headers
  const flatList = useMemo(() => {
    const result: (Command | { type: "header"; category: string })[] = [];
    const catOrder = ["agent", "navigation", "tools", "system"];
    const sorted = Array.from(grouped.entries()).sort(
      (a, b) => catOrder.indexOf(a[0]) - catOrder.indexOf(b[0])
    );
    sorted.forEach(([category, cmds]) => {
      result.push({ type: "header", category });
      result.push(...cmds);
    });
    return result;
  }, [grouped]);

  // Reset selection when query changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Focus input on open
  useEffect(() => {
    if (isOpen) {
      requestAnimationFrame(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      });
    } else {
      setQuery("");
      setSelectedIndex(0);
    }
  }, [isOpen]);

  // Handle command execution
  const handleSelect = useCallback(
    (cmd: Command) => {
      onCommandSelect?.({
        id: cmd.id,
        label: cmd.title,
        shortcut: cmd.shortcut,
        icon: iconMap[cmd.icon || "command"] ?? <CommandIcon size={13} />,
        category: cmd.category,
        action: cmd.action,
      });
      cmd.action();
      onClose();
    },
    [onCommandSelect, onClose]
  );

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => {
          let next = prev + 1;
          while (next < flatList.length && "type" in flatList[next]) next++;
          return next >= flatList.length ? prev : next;
        });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => {
          let next = prev - 1;
          while (next >= 0 && "type" in flatList[next]) next--;
          return next < 0 ? prev : next;
        });
      } else if (e.key === "Enter") {
        e.preventDefault();
        const item = flatList[selectedIndex];
        if (item && "action" in item) {
          if (item.enabled?.() !== false) {
            handleSelect(item);
          }
        }
      }
    },
    [flatList, selectedIndex, onClose, handleSelect]
  );

  // Scroll selected into view
  useEffect(() => {
    const el = itemRefs.current[selectedIndex];
    if (el) {
      el.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  if (!isOpen) return null;

  // Count only command items (not headers)
  let cmdIndex = -1;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-start justify-center pt-[15vh] font-mono"
      style={{ backgroundColor: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="glass-panel flex flex-col max-h-[60vh] overflow-hidden rounded-lg"
        style={{ width: 640, maxWidth: "90vw" }}
      >
        {/* Search bar */}
        <div
          className="flex items-center gap-2 px-3.5 py-2.5 shrink-0"
          style={{ borderBottom: "1px solid var(--c-border)" }}
        >
          <Search size={14} className="shrink-0" style={{ color: "var(--c-accent)" }} />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            className="flex-1 bg-transparent border-none outline-none font-mono text-[13px]"
            style={{ color: "var(--c-text)", caretColor: "var(--c-accent)" }}
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
          />
          <button
            onClick={onClose}
            className="flex items-center justify-center border-none font-mono text-[9px] cursor-pointer rounded"
            style={{ width: 20, height: 20, background: "var(--c-s2)", color: "var(--c-text4)" }}
          >
            ESC
          </button>
        </div>

        {/* Results list */}
        <div
          ref={listRef}
          className="flex-1 overflow-auto"
          style={{ scrollbarWidth: "thin", scrollbarColor: "var(--c-s3) transparent" }}
        >
          {flatList.length === 0 && (
            <div className="px-4 py-6 text-center text-[11px]" style={{ color: "var(--c-text3)" }}>
              <CommandIcon size={24} className="mx-auto mb-2 block" style={{ color: "var(--c-text4)" }} />
              <div>No commands found</div>
              <div className="text-[10px] mt-1" style={{ color: "var(--c-text4)" }}>
                Try a different search term
              </div>
            </div>
          )}

          {flatList.map((item, i) => {
            if ("type" in item) {
              // Category header
              return (
                <div
                  key={`hdr-${item.category}`}
                  className="px-3.5 py-1 text-[9px] font-semibold uppercase tracking-wider sticky top-0 z-[1]"
                  style={{
                    color: categoryColors[item.category] ?? "var(--c-text4)",
                    backgroundColor: "var(--c-base)",
                    borderBottom: "1px solid var(--c-border)",
                  }}
                >
                  {categoryLabels[item.category] ?? item.category}
                </div>
              );
            }

            // Command item
            cmdIndex++;
            const isSelected = i === selectedIndex;
            const isDisabled = item.enabled?.() === false;
            const actualCmdIndex = i;
            const catColor = categoryColors[item.category] ?? "var(--c-text4)";

            return (
              <button
                key={item.id}
                ref={(el) => {
                  itemRefs.current[actualCmdIndex] = el;
                }}
                onClick={() => {
                  if (!isDisabled) handleSelect(item);
                }}
                onMouseEnter={() => setSelectedIndex(actualCmdIndex)}
                className="flex items-center gap-2.5 w-full h-9 px-3.5 border-none font-mono text-[11px] text-left outline-none"
                style={{
                  borderBottom: "1px solid var(--c-border)",
                  backgroundColor: isSelected ? "var(--c-s2)" : "transparent",
                  color: isDisabled ? "var(--c-text4)" : isSelected ? "var(--c-text)" : "var(--c-text2)",
                  cursor: isDisabled ? "not-allowed" : "pointer",
                  transition: "background-color 30ms",
                  opacity: isDisabled ? 0.4 : 1,
                }}
              >
                {/* Icon */}
                <div
                  className="w-[26px] h-[26px] rounded flex items-center justify-center shrink-0"
                  style={{
                    backgroundColor: isSelected ? "var(--c-accent-dim)" : "var(--c-s2)",
                    color: isSelected ? catColor : "var(--c-text4)",
                  }}
                >
                  {iconMap[item.icon || "command"] ?? <CommandIcon size={13} />}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span style={{ fontWeight: isSelected ? 600 : 400 }} className="overflow-hidden text-ellipsis whitespace-nowrap">
                      {item.title}
                    </span>
                    <span
                      className="text-[8px] font-semibold uppercase tracking-wider opacity-70"
                      style={{ color: catColor }}
                    >
                      {categoryLabels[item.category]}
                    </span>
                  </div>
                  {item.description && (
                    <div
                      className="text-[10px] whitespace-nowrap overflow-hidden text-ellipsis"
                      style={{ color: "var(--c-text3)" }}
                    >
                      {item.description}
                    </div>
                  )}
                </div>

                {/* Shortcut */}
                {item.shortcut && (
                  <kbd
                    className="text-[9px] px-[5px] py-[1px] font-mono rounded-sm shrink-0"
                    style={{
                      color: "var(--c-text4)",
                      backgroundColor: "var(--c-base)",
                      border: "1px solid var(--c-border)",
                    }}
                  >
                    {item.shortcut}
                  </kbd>
                )}

                {/* Selected indicator */}
                {isSelected && !isDisabled && (
                  <ArrowRight size={12} className="shrink-0" style={{ color: "var(--c-accent)" }} />
                )}
              </button>
            );
          })}
        </div>

        {/* Footer */}
        <div
          className="flex items-center gap-3.5 px-3.5 py-[5px] text-[9px] shrink-0"
          style={{
            borderTop: "1px solid var(--c-border)",
            color: "var(--c-text4)",
            backgroundColor: "var(--c-base)",
          }}
        >
          <span className="flex items-center gap-1">
            <Keyboard size={10} />
            {filteredCommands.length} commands
          </span>
          <span>↑↓ navigate</span>
          <span>↵ execute</span>
          <span>ESC close</span>
        </div>
      </div>
    </div>
  );
}

export default CommandPalette;
