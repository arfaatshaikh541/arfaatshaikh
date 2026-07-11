"use client";

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback: ReactNode;
}

interface State {
  hasError: boolean;
}

export class SceneErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    if (process.env.NODE_ENV !== "production") {
      console.error("[GRIDKEEP] 3D scene failed to render:", error);
    }
  }

  render() {
    if (this.state.hasError) return <>{this.props.fallback}</>;
    return this.props.children;
  }
}
