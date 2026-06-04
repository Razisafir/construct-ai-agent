import { useCallback } from "react";
import useAppStore from "../stores/useAppStore";
import type { ToastType } from "../types";

export interface UseToastReturn {
  toast: (type: ToastType, title: string, message?: string, duration?: number) => void;
  success: (title: string, message?: string, duration?: number) => void;
  error: (title: string, message?: string, duration?: number) => void;
  info: (title: string, message?: string, duration?: number) => void;
  warning: (title: string, message?: string, duration?: number) => void;
}

export function useToast(): UseToastReturn {
  const addToast = useAppStore((s) => s.addToast);

  const toast = useCallback(
    (type: ToastType, title: string, message?: string, duration = 4000) => {
      addToast({ type, title, message, duration });
    },
    [addToast]
  );

  const success = useCallback(
    (title: string, message?: string, duration?: number) => {
      toast("success", title, message, duration);
    },
    [toast]
  );

  const error = useCallback(
    (title: string, message?: string, duration?: number) => {
      toast("error", title, message, duration);
    },
    [toast]
  );

  const info = useCallback(
    (title: string, message?: string, duration?: number) => {
      toast("info", title, message, duration);
    },
    [toast]
  );

  const warning = useCallback(
    (title: string, message?: string, duration?: number) => {
      toast("warning", title, message, duration);
    },
    [toast]
  );

  return { toast, success, error, info, warning };
}

export default useToast;
