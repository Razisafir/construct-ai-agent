import { useEffect } from "react";
import { CheckCircle, AlertCircle, Info, AlertTriangle } from "lucide-react";

export type ToastType = "success" | "error" | "info" | "warning";

interface ToastNotificationProps {
  type: ToastType;
  title: string;
  message?: string;
  onDismiss?: () => void;
  duration?: number;
}

export function ToastNotification({
  type,
  title,
  message,
  onDismiss,
  duration = 4000,
}: ToastNotificationProps) {
  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        onDismiss?.();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, onDismiss]);

  const typeConfig = {
    success: {
      icon: <CheckCircle size={12} />,
      border: "#282a2d",
      iconColor: "#4ade80",
    },
    error: {
      icon: <AlertCircle size={12} />,
      border: "#282a2d",
      iconColor: "#f87171",
    },
    info: {
      icon: <Info size={12} />,
      border: "#282a2d",
      iconColor: "#00f5ff",
    },
    warning: {
      icon: <AlertTriangle size={12} />,
      border: "#282a2d",
      iconColor: "#e9c349",
    },
  };

  const config = typeConfig[type];

  return (
    <div
      className="fixed top-4 right-4 z-50 flex items-start gap-2 px-3 py-2 font-mono glass-panel"
      style={{
        minWidth: 240,
        maxWidth: 340,
        borderRadius: 8,
      }}
    >
      <div className="mt-0.5 shrink-0" style={{ color: config.iconColor }}>
        {config.icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[11px] font-semibold" style={{ color: "#e2e2e6" }}>
          {title}
        </div>
        {message && (
          <div className="text-[10px] mt-0.5" style={{ color: "#849495" }}>
            {message}
          </div>
        )}
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="shrink-0 hover:text-[#e2e2e6] transition-colors duration-100 cursor-pointer"
          style={{ fontSize: 12, lineHeight: 1, color: "#3a494a" }}
        >
          ×
        </button>
      )}
    </div>
  );
}
