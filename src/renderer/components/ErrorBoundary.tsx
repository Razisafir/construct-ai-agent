import React, { Component, ErrorInfo } from "react";

const C = {
  base: "#0a0a10", s1: "#12121a", s2: "#1a1a24",
  accent: "#6366f1", t1: "#e8e8ec", t2: "#94949c", t3: "#6b6b73", err: "#ef4444",
};
const ff = '"Geist Mono", "JetBrains Mono", monospace';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null, errorInfo: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ error, errorInfo });
    console.error("ErrorBoundary caught:", error, errorInfo);
    // TODO: Send to backend analytics
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div style={{
        position: "fixed", inset: 0, background: C.base,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: ff, zIndex: 9999,
      }}>
        <div style={{
          background: C.s1, border: "1px solid rgba(255,255,255,0.04)",
          padding: "24px", maxWidth: "560px", width: "90%",
        }}>
          <div style={{ fontSize: "13px", fontWeight: 600, color: C.err, marginBottom: "12px" }}>
            APPLICATION ERROR
          </div>
          <div style={{ fontSize: "11px", color: C.t2, marginBottom: "16px", lineHeight: 1.5 }}>
            Something went wrong. The error has been logged.
          </div>

          {/* Error details */}
          <div style={{
            background: C.s2, padding: "8px 12px",
            fontSize: "10px", color: C.t3,
            fontFamily: ff, lineHeight: 1.6,
            marginBottom: "16px", maxHeight: "200px", overflow: "auto",
          }}>
            <div>{this.state.error?.toString()}</div>
            <div style={{ color: C.t4, marginTop: "8px" }}>
              {this.state.errorInfo?.componentStack}
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: "flex", gap: "8px" }}>
            <button onClick={this.handleReload}
              style={{ padding: "6px 16px", background: C.accent, border: "none", color: "#fff", fontFamily: ff, fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.04em", cursor: "pointer" }}>
              Reload App
            </button>
            <button onClick={() => alert("Report feature coming soon")}
              style={{ padding: "6px 16px", background: C.s2, border: "1px solid rgba(255,255,255,0.04)", color: C.t3, fontFamily: ff, fontSize: "10px", textTransform: "uppercase", cursor: "pointer" }}>
              Report Issue
            </button>
            <button onClick={() => console.log(this.state)}
              style={{ padding: "6px 16px", background: "transparent", border: "1px solid rgba(255,255,255,0.04)", color: C.t4, fontFamily: ff, fontSize: "10px", textTransform: "uppercase", cursor: "pointer" }}>
              View Logs
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
