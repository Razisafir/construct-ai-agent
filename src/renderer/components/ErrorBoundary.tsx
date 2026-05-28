import React, { Component, type ReactNode } from "react";
import { AlertTriangle, RotateCcw, Trash2 } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  override componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  handleReload = () => {
    window.location.reload();
  };

  handleResetState = () => {
    // Clear all localStorage
    try {
      localStorage.clear();
    } catch {
      // Ignore localStorage errors
    }
    // Reload the app
    window.location.reload();
  };

  override render() {
    if (this.state.hasError) {
      const isDev = import.meta.env.DEV;

      return (
        <div className="flex items-center justify-center w-full h-full bg-construct-bg-primary p-8">
          <div className="glass-panel rounded-xl p-8 max-w-lg w-full space-y-6">
            {/* Icon */}
            <div className="flex justify-center">
              <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center glow-error">
                <AlertTriangle className="w-8 h-8 text-red-400" />
              </div>
            </div>

            {/* Message */}
            <div className="text-center space-y-2">
              <h2 className="text-lg font-semibold text-construct-text-primary">
                Something went wrong
              </h2>
              <p className="text-sm text-construct-text-muted">
                Construct encountered an unexpected error. You can try reloading the app or resetting the application state.
              </p>
            </div>

            {/* Error details in dev mode */}
            {isDev && this.state.error && (
              <div className="rounded-lg bg-construct-bg-primary/80 border border-construct-border/50 p-4 space-y-2 overflow-hidden">
                <p className="text-xs font-mono text-red-400 break-all">
                  {this.state.error.toString()}
                </p>
                {this.state.errorInfo && (
                  <pre className="text-[10px] font-mono text-construct-text-muted overflow-auto max-h-32 whitespace-pre-wrap break-all">
                    {this.state.errorInfo.componentStack}
                  </pre>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleReload}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-construct-accent-primary/10 text-construct-accent-primary text-sm font-medium btn-interactive hover:bg-construct-accent-primary/20 transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                Reload App
              </button>
              <button
                onClick={this.handleResetState}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 text-red-400 text-sm font-medium btn-interactive hover:bg-red-500/20 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                Reset State
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
