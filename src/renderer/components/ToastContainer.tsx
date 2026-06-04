import React, { useEffect, useCallback } from "react";
import {
  CheckCircle2,
  XCircle,
  Info,
  AlertTriangle,
  X,
} from "lucide-react";
import useAppStore from "../stores/useAppStore";
import type { ToastType } from "../types";

const toastConfig: Record<
  ToastType,
  { icon: React.ElementType; iconColor: string; borderColor: string }
> = {
  success: {
    icon: CheckCircle2,
    iconColor: "var(--c-ok)",
    borderColor: "rgba(74,222,128,0.3)",
  },
  error: {
    icon: XCircle,
    iconColor: "var(--c-err)",
    borderColor: "rgba(248,113,113,0.3)",
  },
  info: {
    icon: Info,
    iconColor: "var(--c-info)",
    borderColor: "rgba(96,165,250,0.3)",
  },
  warning: {
    icon: AlertTriangle,
    iconColor: "var(--c-gold)",
    borderColor: "rgba(234,179,8,0.3)",
  },
};

const ToastItem: React.FC<{ toastId: string }> = ({ toastId }) => {
  const toast = useAppStore((s) => s.toasts.find((t) => t.id === toastId));
  const removeToast = useAppStore((s) => s.removeToast);

  const handleDismiss = useCallback(() => {
    removeToast(toastId);
  }, [toastId, removeToast]);

  useEffect(() => {
    if (!toast) return;
    const duration = toast.duration ?? 4000;
    const timer = setTimeout(() => { handleDismiss(); }, duration);
    return () => clearTimeout(timer);
  }, [toast, handleDismiss]);

  if (!toast) return null;

  const config = toastConfig[toast.type];
  const Icon = config.icon;

  return (
    <div
      className="font-mono"
      style={{
        background: "var(--c-s2)",
        border: `1px solid ${config.borderColor}`,
        borderRadius: "0px",
        padding: "12px",
        minWidth: "280px",
        maxWidth: "360px",
        pointerEvents: "auto",
        transition: "opacity 100ms ease",
      }}
    >
      <div className="flex items-start gap-3">
        <Icon
          style={{ width: "20px", height: "20px", color: config.iconColor, flexShrink: 0, marginTop: "2px" }}
        />
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-semibold leading-snug m-0" style={{ color: "var(--c-text)" }}>
            {toast.title}
          </p>
          {toast.message && (
            <p className="text-[10px] mt-1 leading-relaxed" style={{ color: "var(--c-text2)" }}>
              {toast.message}
            </p>
          )}
        </div>
        <button
          onClick={handleDismiss}
          className="shrink-0 p-[2px] rounded-sm bg-transparent border-none cursor-pointer flex items-center justify-center"
          style={{ color: "var(--c-text3)" }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--c-text)"; (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.05)"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = "var(--c-text3)"; (e.currentTarget as HTMLButtonElement).style.background = "none"; }}
        >
          <X style={{ width: "14px", height: "14px" }} />
        </button>
      </div>
    </div>
  );
};

const ToastContainer: React.FC = () => {
  const toasts = useAppStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toastId={toast.id} />
      ))}
    </div>
  );
};

export default ToastContainer;
