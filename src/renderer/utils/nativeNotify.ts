/**
 * Native OS notifications via Tauri plugin-notification.
 *
 * Falls back to web Notification API when not running inside Tauri,
 * and gracefully degrades if no notification system is available.
 */

let notifyModule: any = null;

async function getNotify() {
  if (notifyModule !== null) return notifyModule;
  try {
    notifyModule = await import("@tauri-apps/plugin-notification");
  } catch {
    notifyModule = null;
  }
  return notifyModule;
}

function isTauri(): boolean {
  return typeof window !== "undefined" && !!(window as any).__TAURI__;
}

/**
 * Send a native OS notification.
 *
 * On Tauri: uses tauri-plugin-notification (requests permission automatically).
 * On Web: falls back to the Web Notification API.
 * If neither is available, logs to console.
 */
export async function notify(title: string, body: string): Promise<void> {
  // Try Tauri notification first
  if (isTauri()) {
    const mod = await getNotify();
    if (mod) {
      try {
        const hasPermission = await mod.isPermissionGranted();
        if (!hasPermission) {
          const permission = await mod.requestPermission();
          if (permission !== "granted") {
            console.warn("[nativeNotify] Notification permission denied");
            return;
          }
        }
        mod.sendNotification({ title, body });
        return;
      } catch (err) {
        console.warn("[nativeNotify] Tauri notification failed:", err);
      }
    }
  }

  // Fallback: Web Notification API
  if (typeof Notification !== "undefined") {
    try {
      if (Notification.permission === "granted") {
        new Notification(title, { body });
      } else if (Notification.permission !== "denied") {
        const permission = await Notification.requestPermission();
        if (permission === "granted") {
          new Notification(title, { body });
        }
      }
      return;
    } catch {
      // Web notification failed too
    }
  }

  // Final fallback: console
  console.log(`[notify] ${title}: ${body}`);
}

/**
 * Convenience wrapper for common notification types.
 */
export const nativeNotify = {
  info: (title: string, body: string) => notify(title, body),
  success: (body: string) => notify("Construct", body),
  error: (body: string) => notify("Construct Error", body),
  agent: (body: string) => notify("Construct Agent", body),
};
