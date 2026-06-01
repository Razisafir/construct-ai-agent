import React, { Component, ErrorInfo } from "react";

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
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="fixed inset-0 flex items-center justify-center font-mono z-[9999]" style={{ background: "var(--c-base)" }}>
        <div className="p-6 max-w-[560px] w-[90%]" style={{ background: "var(--c-s1)", border: "1px solid var(--c-border)" }}>
          <div className="text-[13px] font-semibold mb-3" style={{ color: "var(--c-err)" }}>
            APPLICATION ERROR
          </div>
          <div className="text-[11px] mb-4 leading-relaxed" style={{ color: "var(--c-text2)" }}>
            Something went wrong. The error has been logged.
          </div>

          <div className="p-3 text-[10px] font-mono leading-relaxed mb-4 max-h-[200px] overflow-auto" style={{ background: "var(--c-s2)", color: "var(--c-text3)" }}>
            <div>{this.state.error?.toString()}</div>
            <div className="mt-2" style={{ color: "var(--c-text4)" }}>
              {this.state.errorInfo?.componentStack}
            </div>
          </div>

          <div className="flex gap-2">
            <button onClick={this.handleReload}
              className="px-4 py-1.5 border-none font-mono text-[10px] uppercase tracking-wider cursor-pointer" style={{ background: "var(--c-accent)", color: "var(--c-base)" }}>
              Reload App
            </button>
            <button onClick={() => alert("Report feature coming soon")}
              className="px-4 py-1.5 font-mono text-[10px] uppercase cursor-pointer" style={{ background: "var(--c-s2)", border: "1px solid var(--c-border)", color: "var(--c-text3)" }}>
              Report Issue
            </button>
            <button onClick={() => console.log(this.state)}
              className="px-4 py-1.5 font-mono text-[10px] uppercase cursor-pointer" style={{ background: "transparent", border: "1px solid var(--c-border)", color: "var(--c-text4)" }}>
              View Logs
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
