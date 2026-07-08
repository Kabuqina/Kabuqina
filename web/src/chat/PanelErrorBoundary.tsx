// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// Guards the workspace panel body so a single panel's render error degrades to
// an inline message instead of white-screening the whole app. Also surfaces the
// error text on screen (and to the console) for diagnosis.

import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode; label?: string };
type State = { error: Error | null };

export class PanelErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[panel crash]${this.props.label ? ` ${this.props.label}` : ""}`, error, info);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (error) {
      return (
        <div className="m-2 rounded-md border border-red-300 bg-red-50 p-2.5 text-[12px] leading-snug text-red-600">
          <div className="font-medium">此面板渲染出错，已隔离以避免整页白屏。</div>
          <pre className="mt-1 whitespace-pre-wrap break-words text-[11px]">
            {error.message || String(error)}
          </pre>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="mt-1.5 rounded-md border border-red-300 px-2 py-0.5 text-[11px]"
          >
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
