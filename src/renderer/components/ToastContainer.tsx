import React, { useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
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
  { icon: React.ElementType; iconColor: string; borderColor: string; bgColor: string }
> = {
  success: {
    icon: CheckCircle2,
    iconColor: "text-green-400",
    borderColor: "border-green-500/30",
    bgColor: "bg-green-500/5",
  },
  error: {
    icon: XCircle,
    iconColor: "text-red-400",
    borderColor: "border-red-500/30",
    bgColor: "bg-red-500/5",
  },
  info: {
    icon: Info,
    iconColor: "text-blue-400",
    borderColor: "border-blue-500/30",
    bgColor: "bg-blue-500/5",
  },
  warning: {
    icon: AlertTriangle,
    iconColor: "text-yellow-400",
    borderColor: "border-yellow-500/30",
    bgColor: "bg-yellow-500/5",
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
    const timer = setTimeout(() => {
      handleDismiss();
    }, duration);
    return () => clearTimeout(timer);
  }, [toast, handleDismiss]);

  if (!toast) return null;

  const config = toastConfig[toast.type];
  const Icon = config.icon;

  return (
    <motion.div
      layout
      initial={{ x: 120, opacity: 0, scale: 0.9 }}
      animate={{ x: 0, opacity: 1, scale: 1 }}
      exit={{ x: 120, opacity: 0, scale: 0.9 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      className={`glass-panel rounded-lg border ${config.borderColor} ${config.bgColor} p-3 min-w-[280px] max-w-[360px] shadow-lg pointer-events-auto`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`w-5 h-5 ${config.iconColor} shrink-0 mt-0.5`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-construct-text-primary leading-tight">
            {toast.title}
          </p>
          {toast.message && (
            <p className="text-xs text-construct-text-muted mt-1 leading-relaxed">
              {toast.message}
            </p>
          )}
        </div>
        <button
          onClick={handleDismiss}
          className="shrink-0 p-0.5 rounded-md text-construct-text-muted hover:text-construct-text-primary hover:bg-white/5 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </motion.div>
  );
};

const ToastContainer: React.FC = () => {
  const toasts = useAppStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toastId={toast.id} />
        ))}
      </AnimatePresence>
    </div>
  );
};

export default ToastContainer;
