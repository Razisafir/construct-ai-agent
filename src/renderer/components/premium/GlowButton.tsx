import { ReactNode } from "react";
import { motion } from "framer-motion";
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
  const base =
    "relative inline-flex items-center justify-center gap-2 font-medium rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-0 focus:ring-construct-accent-primary/50 overflow-hidden";

  const sizeClasses = {
    sm: "h-7 px-3 text-xs rounded-lg",
    md: "h-9 px-4 text-sm rounded-xl",
    lg: "h-11 px-6 text-base rounded-xl",
  };

  const variantClasses = {
    primary:
      "bg-gradient-to-r from-construct-accent-primary to-construct-accent-secondary text-white shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:shadow-[0_0_30px_rgba(99,102,241,0.5)] hover:brightness-110 active:scale-[0.98]",
    secondary:
      "bg-[rgba(255,255,255,0.06)] text-construct-text-primary border border-[rgba(255,255,255,0.1)] hover:bg-[rgba(255,255,255,0.1)] hover:border-[rgba(255,255,255,0.18)] active:scale-[0.98]",
    danger:
      "bg-gradient-to-r from-construct-semantic-error to-[#f87171] text-white shadow-[0_0_20px_rgba(239,68,68,0.3)] hover:shadow-[0_0_30px_rgba(239,68,68,0.5)] hover:brightness-110 active:scale-[0.98]",
    ghost:
      "bg-transparent text-construct-text-muted hover:text-construct-text-primary hover:bg-[rgba(255,255,255,0.04)] active:scale-[0.98]",
  };

  const isDisabled = disabled || loading;

  return (
    <motion.button
      type={type}
      onClick={onClick}
      disabled={isDisabled}
      whileTap={!isDisabled ? { scale: 0.97 } : undefined}
      className={`${base} ${sizeClasses[size]} ${variantClasses[variant]} ${
        isDisabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
      } ${className}`}
    >
      {loading && (
        <Loader2 size={size === "sm" ? 12 : size === "md" ? 14 : 16} className="animate-spin" />
      )}
      <span className={loading ? "opacity-80" : ""}>{children}</span>
    </motion.button>
  );
}
