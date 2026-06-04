import { ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
}

export function GlassCard({ children, className = "" }: GlassCardProps) {
  return (
    <div
      className={`bg-[rgba(20,22,25,0.6)] backdrop-blur-[12px] -webkit-backdrop-blur-[12px] border border-border-subtle rounded p-3 ${className}`}
    >
      {children}
    </div>
  );
}
