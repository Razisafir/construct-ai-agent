import {
  useState,
  useRef,
  useEffect,
  useCallback,
} from "react";
import { FileCode, X } from "lucide-react";

export interface FileChip {
  path: string;
  name: string;
}

interface FileReferenceInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onFileAttach: (files: FileChip[]) => void;
  projectFiles: string[];
  attachedFiles: FileChip[];
}

export function FileReferenceInput({
  value,
  onChange,
  onSubmit,
  onFileAttach,
  projectFiles,
  attachedFiles,
}: FileReferenceInputProps) {
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [filter, setFilter] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [cursorPos, setCursorPos] = useState(0);

  // Detect @ trigger
  const checkTrigger = useCallback(() => {
    const beforeCursor = value.slice(0, cursorPos);
    const match = beforeCursor.match(/@([\w./-]*)$/);
    if (match) { setFilter(match[1].toLowerCase()); setShowAutocomplete(true); }
    else { setShowAutocomplete(false); }
  }, [value, cursorPos]);

  useEffect(() => { checkTrigger(); }, [checkTrigger]);

  const filtered = projectFiles.filter((f) => f.toLowerCase().includes(filter)).slice(0, 8);

  const attachFile = (path: string) => {
    const name = path.split("/").pop() || path;
    const newFiles = [...attachedFiles, { path, name }];
    onFileAttach(newFiles);
    const before = value.slice(0, cursorPos).replace(/@[\w./-]*$/, "");
    const after = value.slice(cursorPos);
    onChange(before + after);
    setShowAutocomplete(false);
    inputRef.current?.focus();
  };

  const removeFile = (path: string) => {
    onFileAttach(attachedFiles.filter((f) => f.path !== path));
  };

  return (
    <div className="relative font-mono">
      {/* Attached file chips */}
      {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-[5px] mb-2">
          {attachedFiles.map((file) => (
            <span
              key={file.path}
              className="flex items-center gap-[5px] px-2 py-[2px] rounded-sm text-[10px] tracking-wider font-mono"
              style={{ background: "var(--c-s2)", color: "var(--c-text2)", border: "1px solid var(--c-s3)" }}
            >
              <FileCode size={10} style={{ color: "var(--c-accent)" }} />
              {file.name}
              <button
                onClick={() => removeFile(file.path)}
                title="Remove file"
                className="bg-transparent border-none cursor-pointer p-0 flex items-center"
                style={{ color: "var(--c-text3)" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--c-err)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--c-text3)"; }}
              >
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Input with @ autocomplete */}
      <div className="relative">
        <textarea
          ref={inputRef}
          value={value}
          onChange={(e) => { onChange(e.target.value); setCursorPos(e.target.selectionStart); }}
          onSelect={(e) => setCursorPos(e.currentTarget.selectionStart)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSubmit(); } }}
          placeholder="Type @ to reference a file..."
          className="w-full p-2 text-[11px] font-mono outline-none resize-none box-border rounded-sm"
          style={{ height: 80, background: "var(--c-s1)", border: "1px solid var(--c-s3)", color: "var(--c-text)" }}
          onFocus={(e) => { e.currentTarget.style.borderColor = "var(--c-accent)"; }}
          onBlur={(e) => { e.currentTarget.style.borderColor = "var(--c-s3)"; }}
        />

        {/* Autocomplete dropdown */}
        {showAutocomplete && filtered.length > 0 && (
          <div
            className="absolute left-0 w-[256px] max-h-[160px] overflow-y-auto z-50 font-mono rounded-sm"
            style={{ bottom: "100%", marginBottom: 4, background: "var(--c-s1)", border: "1px solid var(--c-s3)" }}
          >
            {filtered.map((file) => (
              <button
                key={file}
                onClick={() => attachFile(file)}
                className="flex items-center gap-2 w-full px-2.5 py-1.5 text-[11px] bg-transparent border-none cursor-pointer text-left font-mono whitespace-nowrap overflow-hidden text-ellipsis"
                style={{ color: "var(--c-text2)", borderBottom: "1px solid var(--c-s2)" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "var(--c-s2)"; e.currentTarget.style.color = "var(--c-text)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--c-text2)"; }}
              >
                <FileCode size={12} className="shrink-0" style={{ color: "var(--c-accent)" }} />
                <span className="overflow-hidden text-ellipsis whitespace-nowrap">{file}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default FileReferenceInput;
