interface StatusBadgeProps {
  status: "idle" | "working" | "success" | "warning" | "error";
  text?: string;
  className?: string;
}

export function StatusBadge({
  status,
  text,
  className = "",
}: StatusBadgeProps) {
  const config: Record<string, { textClass: string; dotClass: string; label: string }> = {
    idle:    { textClass: "text-text-secondary", dotClass: "bg-text-secondary", label: text || "idle" },
    working: { textClass: "text-accent-cyan", dotClass: "bg-accent-cyan animate-pulse", label: text || "working" },
    success: { textClass: "text-status-running", dotClass: "bg-status-running", label: text || "success" },
    warning: { textClass: "text-accent-gold", dotClass: "bg-accent-gold", label: text || "warning" },
    error:   { textClass: "text-tertiary", dotClass: "bg-tertiary animate-pulse", label: text || "error" },
  };

  const c = config[status];

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono text-[9px] ${c.textClass} ${className}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full inline-block ${c.dotClass}`}
      />
      {c.label}
    </span>
  );
}
