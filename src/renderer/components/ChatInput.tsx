import { useState, useRef, useCallback, useEffect } from "react";
import { Send, X, AtSign } from "lucide-react";

export interface FileAttachment {
  id: string;
  fileName: string;
  filePath: string;
}

interface ChatInputProps {
  onSend: (message: string, attachments: FileAttachment[]) => void;
  fileSuggestions?: string[];
}

const DEFAULT_FILE_SUGGESTIONS: string[] = [
  "src/App.tsx",
  "src/components/Sidebar.tsx",
  "src/components/Editor.tsx",
  "src/components/Panel.tsx",
  "src/components/StatusBar.tsx",
  "src/components/AgentPanel.tsx",
  "src/components/ChatInput.tsx",
  "src/hooks/useKeyboardShortcuts.ts",
  "src/stores/useAppStore.ts",
  "src/types/index.ts",
  "src/main.tsx",
  "package.json",
  "vite.config.ts",
  "tsconfig.json",
];

function ChatInput({
  onSend,
  fileSuggestions = DEFAULT_FILE_SUGGESTIONS,
}: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<FileAttachment[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestionQuery, setSuggestionQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const filteredSuggestions = suggestionQuery
    ? fileSuggestions.filter((f) => f.toLowerCase().includes(suggestionQuery.toLowerCase()))
    : fileSuggestions;

  const atTriggerRef = useRef<number>(-1);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      const cursorPos = e.target.selectionStart ?? 0;
      setMessage(value);
      const lastAtIndex = value.lastIndexOf("@", cursorPos - 1);
      const textAfterAt = value.slice(lastAtIndex + 1, cursorPos);
      const hasSpaceBetween = textAfterAt.includes(" ");
      if (lastAtIndex !== -1 && !hasSpaceBetween && cursorPos > lastAtIndex) {
        atTriggerRef.current = lastAtIndex;
        setSuggestionQuery(textAfterAt);
        setShowSuggestions(true);
        setSelectedIndex(0);
      } else {
        setShowSuggestions(false);
        setSuggestionQuery("");
        atTriggerRef.current = -1;
      }
    },
    []
  );

  const acceptSuggestion = useCallback(
    (filePath: string) => {
      if (atTriggerRef.current === -1) return;
      const beforeAt = message.slice(0, atTriggerRef.current);
      const afterCursor = message.slice(inputRef.current?.selectionStart ?? message.length);
      const newMessage = `${beforeAt}${afterCursor}`;
      setMessage(newMessage);
      const fileName = filePath.split("/").pop() ?? filePath;
      const alreadyAttached = attachments.some((a) => a.filePath === filePath);
      if (!alreadyAttached) {
        setAttachments((prev) => [...prev, { id: `att-${crypto.randomUUID()}`, fileName, filePath }]);
      }
      setShowSuggestions(false);
      setSuggestionQuery("");
      atTriggerRef.current = -1;
      requestAnimationFrame(() => inputRef.current?.focus());
    },
    [message, attachments]
  );

  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = message.trim();
    if (!trimmed && attachments.length === 0) return;
    onSend(trimmed, attachments);
    setMessage("");
    setAttachments([]);
    setShowSuggestions(false);
    atTriggerRef.current = -1;
  }, [message, attachments, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (showSuggestions) {
        if (e.key === "ArrowDown") { e.preventDefault(); setSelectedIndex((prev) => Math.min(prev + 1, filteredSuggestions.length - 1)); return; }
        if (e.key === "ArrowUp") { e.preventDefault(); setSelectedIndex((prev) => Math.max(prev - 1, 0)); return; }
        if (e.key === "Tab" || e.key === "Enter") { e.preventDefault(); if (filteredSuggestions[selectedIndex]) { acceptSuggestion(filteredSuggestions[selectedIndex]); } return; }
        if (e.key === "Escape") { setShowSuggestions(false); return; }
      }
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); return; }
    },
    [showSuggestions, filteredSuggestions, selectedIndex, acceptSuggestion, handleSend]
  );

  useEffect(() => {
    if (!showSuggestions) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) { setShowSuggestions(false); }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showSuggestions]);

  return (
    <div
      ref={containerRef}
      className="flex flex-col gap-1.5 px-2 py-1.5 relative font-mono"
      style={{ borderTop: "1px solid var(--c-border)", backgroundColor: "var(--c-base)" }}
    >
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {attachments.map((att) => (
            <span
              key={att.id}
              className="inline-flex items-center gap-1 text-[10px] font-mono rounded px-1.5 py-[2px] cursor-default"
              style={{ color: "var(--c-text2)", backgroundColor: "var(--c-s2)", border: "1px solid var(--c-border)" }}
            >
              <AtSign size={9} style={{ color: "var(--c-accent)" }} />
              <span>{att.fileName}</span>
              <span
                onClick={() => removeAttachment(att.id)}
                className="cursor-pointer flex items-center"
                style={{ color: "var(--c-text4)", fontSize: 10, lineHeight: 1 }}
                onMouseEnter={(e) => { (e.target as HTMLElement).style.color = "var(--c-err)"; }}
                onMouseLeave={(e) => { (e.target as HTMLElement).style.color = "var(--c-text4)"; }}
              >
                <X size={10} />
              </span>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-1.5">
        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            value={message}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="> Type message or @ to reference files..."
            className="w-full h-[26px] px-2 bg-panel-bg border outline-none font-mono text-[11px] rounded-md"
            style={{ borderColor: "var(--c-border)", color: "var(--c-text)", caretColor: "var(--c-accent)" }}
            spellCheck={false}
            autoComplete="off"
          />
          {showSuggestions && filteredSuggestions.length > 0 && (
            <div
              className="glass-panel absolute left-0 right-0 z-50 max-h-[160px] overflow-auto rounded-lg"
              style={{ bottom: "calc(100% + 2px)" }}
            >
              {filteredSuggestions.map((file, i) => {
                const isSelected = i === selectedIndex;
                const fileName = file.split("/").pop() ?? file;
                const dirPath = file.slice(0, file.lastIndexOf("/"));
                return (
                  <button
                    key={file}
                    onClick={() => acceptSuggestion(file)}
                    className="flex items-center gap-1.5 w-full h-6 px-2 border-none font-mono text-[11px] text-left outline-none whitespace-nowrap overflow-hidden text-ellipsis"
                    style={{
                      borderBottom: "1px solid var(--c-border)",
                      backgroundColor: isSelected ? "var(--c-s2)" : "transparent",
                      color: isSelected ? "var(--c-text)" : "var(--c-text2)",
                      cursor: "pointer",
                    }}
                    onMouseEnter={() => setSelectedIndex(i)}
                  >
                    <AtSign size={10} className="shrink-0" style={{ color: isSelected ? "var(--c-accent)" : "var(--c-text4)" }} />
                    <span style={{ fontWeight: isSelected ? 600 : 400 }}>{fileName}</span>
                    {dirPath && <span className="ml-auto shrink-0 text-[10px]" style={{ color: "var(--c-text4)" }}>{dirPath}</span>}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <button
          onClick={handleSend}
          className="flex items-center justify-center w-[26px] h-[26px] border-none rounded-md cursor-pointer shrink-0"
          style={{
            backgroundColor: "var(--c-accent)",
            color: "var(--c-base)",
            opacity: message.trim() || attachments.length > 0 ? 1 : 0.5,
            transition: "opacity 0.1s",
          }}
          title="Send message"
        >
          <Send size={12} />
        </button>
      </div>
    </div>
  );
}

export default ChatInput;
