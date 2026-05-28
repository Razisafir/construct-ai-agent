import { useState, useRef, useCallback, useEffect } from "react";
import { Send, X, AtSign } from "lucide-react";

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
  ok: "#10b981",
  wrn: "#f59e0b",
  err: "#ef4444",
  border: "rgba(255,255,255,0.04)",
};

const ff = '"Geist Mono", "JetBrains Mono", monospace';

/* ─────────────────────── types ─────────────────────── */

export interface FileAttachment {
  id: string;
  fileName: string;
  filePath: string;
}

interface ChatInputProps {
  onSend: (message: string, attachments: FileAttachment[]) => void;
  fileSuggestions?: string[];
}

/* ─────────────────────── demo file list for @ autocomplete ─────────────────────── */

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

/* ─────────────────────── component ─────────────────────── */

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

  // Filter suggestions based on query
  const filteredSuggestions = suggestionQuery
    ? fileSuggestions.filter((f) =>
        f.toLowerCase().includes(suggestionQuery.toLowerCase())
      )
    : fileSuggestions;

  // Track @ trigger position
  const atTriggerRef = useRef<number>(-1);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      const cursorPos = e.target.selectionStart ?? 0;
      setMessage(value);

      // Check if we just typed @ or are typing after @
      const lastAtIndex = value.lastIndexOf("@", cursorPos - 1);
      const textAfterAt = value.slice(lastAtIndex + 1, cursorPos);
      const hasSpaceBetween = textAfterAt.includes(" ");

      if (
        lastAtIndex !== -1 &&
        !hasSpaceBetween &&
        cursorPos > lastAtIndex
      ) {
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
      const afterCursor = message.slice(
        (inputRef.current?.selectionStart ?? message.length)
      );
      const newMessage = `${beforeAt}${afterCursor}`;
      setMessage(newMessage);

      // Add as attachment chip
      const fileName = filePath.split("/").pop() ?? filePath;
      const alreadyAttached = attachments.some((a) => a.filePath === filePath);
      if (!alreadyAttached) {
        setAttachments((prev) => [
          ...prev,
          {
            id: `att-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            fileName,
            filePath,
          },
        ]);
      }

      setShowSuggestions(false);
      setSuggestionQuery("");
      atTriggerRef.current = -1;

      // Restore focus
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
      // Handle suggestion navigation
      if (showSuggestions) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setSelectedIndex((prev) =>
            Math.min(prev + 1, filteredSuggestions.length - 1)
          );
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          setSelectedIndex((prev) => Math.max(prev - 1, 0));
          return;
        }
        if (e.key === "Tab" || e.key === "Enter") {
          e.preventDefault();
          if (filteredSuggestions[selectedIndex]) {
            acceptSuggestion(filteredSuggestions[selectedIndex]);
          }
          return;
        }
        if (e.key === "Escape") {
          setShowSuggestions(false);
          return;
        }
      }

      // Send on Enter (no shift)
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
        return;
      }
    },
    [showSuggestions, filteredSuggestions, selectedIndex, acceptSuggestion, handleSend]
  );

  // Close suggestions on outside click
  useEffect(() => {
    if (!showSuggestions) return;
    const handler = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showSuggestions]);

  return (
    <div
      ref={containerRef}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
        padding: "6px 8px",
        borderTop: `1px solid ${C.border}`,
        backgroundColor: C.base,
        position: "relative",
        fontFamily: ff,
      }}
    >
      {/* Attachment chips */}
      {attachments.length > 0 && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 4,
          }}
        >
          {attachments.map((att) => (
            <span
              key={att.id}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: 10,
                fontFamily: ff,
                color: C.t2,
                backgroundColor: C.s2,
                border: `1px solid ${C.border}`,
                padding: "2px 6px",
                cursor: "default",
              }}
            >
              <AtSign size={9} style={{ color: C.accent }} />
              <span>{att.fileName}</span>
              <span
                onClick={() => removeAttachment(att.id)}
                style={{
                  cursor: "pointer",
                  color: C.t4,
                  fontSize: 10,
                  lineHeight: 1,
                  display: "flex",
                  alignItems: "center",
                }}
                onMouseEnter={(e) => {
                  (e.target as HTMLElement).style.color = C.err;
                }}
                onMouseLeave={(e) => {
                  (e.target as HTMLElement).style.color = C.t4;
                }}
              >
                <X size={10} />
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Input row */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{ position: "relative", flex: 1 }}>
          <input
            ref={inputRef}
            type="text"
            value={message}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="> Type message or @ to reference files..."
            style={{
              width: "100%",
              height: 26,
              padding: "0 8px",
              backgroundColor: C.s1,
              border: `1px solid ${C.border}`,
              outline: "none",
              fontSize: 11,
              fontFamily: ff,
              color: C.t1,
              caretColor: C.accent,
            }}
            spellCheck={false}
            autoComplete="off"
          />

          {/* @ suggestions dropdown */}
          {showSuggestions && filteredSuggestions.length > 0 && (
            <div
              style={{
                position: "absolute",
                bottom: "calc(100% + 2px)",
                left: 0,
                right: 0,
                zIndex: 50,
                maxHeight: 160,
                overflow: "auto",
                backgroundColor: C.s1,
                border: `1px solid ${C.border}`,
                boxShadow: "0 -4px 12px rgba(0,0,0,0.4)",
              }}
            >
              {filteredSuggestions.map((file, i) => {
                const isSelected = i === selectedIndex;
                const fileName = file.split("/").pop() ?? file;
                const dirPath = file.slice(0, file.lastIndexOf("/"));

                return (
                  <button
                    key={file}
                    onClick={() => acceptSuggestion(file)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      width: "100%",
                      height: 24,
                      padding: "0 8px",
                      border: "none",
                      borderBottom: `1px solid ${C.border}`,
                      backgroundColor: isSelected ? C.s2 : "transparent",
                      color: isSelected ? C.t1 : C.t2,
                      cursor: "pointer",
                      fontFamily: ff,
                      fontSize: 11,
                      textAlign: "left",
                      outline: "none",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                    onMouseEnter={() => setSelectedIndex(i)}
                  >
                    <AtSign
                      size={10}
                      style={{
                        color: isSelected ? C.accent : C.t4,
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ fontWeight: isSelected ? 600 : 400 }}>
                      {fileName}
                    </span>
                    {dirPath && (
                      <span
                        style={{
                          color: C.t4,
                          fontSize: 10,
                          marginLeft: "auto",
                          flexShrink: 0,
                        }}
                      >
                        {dirPath}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Send button */}
        <button
          onClick={handleSend}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 26,
            height: 26,
            backgroundColor: C.accent,
            border: "none",
            borderRadius: 2,
            cursor: "pointer",
            color: "#fff",
            flexShrink: 0,
            transition: "opacity 0.1s",
            opacity: message.trim() || attachments.length > 0 ? 1 : 0.5,
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
