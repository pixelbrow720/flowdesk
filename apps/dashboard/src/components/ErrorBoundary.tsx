"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * ErrorBoundary — catches JavaScript errors in child components and displays a
 * fallback UI instead of crashing the entire page. Logs errors to console for
 * debugging. Provides a reset button to retry rendering.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[ErrorBoundary] Caught error:", error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex min-h-[200px] flex-col items-center justify-center gap-4 rounded-md border border-crimson-deep/30 bg-ink-900 p-6 text-center">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-crimson-deep">
            Component Error
          </p>
          <p className="max-w-md font-mono text-[12px] text-bone-2">
            This component encountered an unexpected error and cannot render.
          </p>
          {this.state.error && (
            <pre className="max-h-32 max-w-full overflow-auto rounded bg-ink-950 p-3 font-mono text-[10px] text-bone-3">
              {this.state.error.message}
            </pre>
          )}
          <button
            onClick={this.handleReset}
            className="rounded bg-turquoise-deep px-4 py-2 font-mono text-[11px] uppercase tracking-[0.2em] text-ink-0 transition-colors hover:bg-turquoise-deep/80"
          >
            Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
