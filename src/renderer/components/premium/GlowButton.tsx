import { ReactNode } from "react";
import { Loader2 } from "lucide-react";

interface GlowButtonProps {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  type?: "button" | "submit";
}

export function GlowButton({
  variant = "primary",
  size = "md",
  children,
  onClick,
  disabled = false,
  loading = false,
  className = "",
  type = "button",
}: GlowButtonProps) {
  const sizeClasses = {
    sm: "px-2 py-[6px] text-[9px]",
    md: "px-3 py-[6px] text-[10px]",
    lg: "px-4 py-2 text-[11px]",
  };

  const variantClasses = {
    primary:
      "bg-accent-cyan text-bg-onyx border-accent-cyan hover:bg-accent-cyan/80",
    secondary:
      "bg-transparent text-text-primary border-transparent hover:bg-accent-cyan-dim luminous-border",
    danger:
      "bg-diff-remove/10 text-diff-remove border-diff-remove/30 hover:bg-diff-remove/20",
    ghost:
      "bg-transparent text-text-secondary border-transparent hover:text-text-primary hover:border-border-subtle",
  };

  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={isDisabled}
      className={`
        inline-flex items-center justify-center gap-1.5
        font-mono font-medium
        border
        transition-colors duration-100
        ${sizeClasses[size]}
        ${variantClasses[variant]}
        ${isDisabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}
        ${className}
      `}
      style={{ borderRadius: 6 }}
    >
      {loading && (
        <Loader2
          size={size === "sm" ? 10 : size === "md" ? 11 : 12}
          className="animate-spin"
        />
      )}
      {children}
    </button>
  );
}
