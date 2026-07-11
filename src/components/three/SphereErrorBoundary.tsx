"use client";

import { Component, type ReactNode } from "react";
import { SphereFallback } from "./SphereFallback";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class SphereErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error("Sphere scene failed to render, falling back to static hero:", error);
  }

  render() {
    if (this.state.hasError) {
      return <SphereFallback />;
    }
    return this.props.children;
  }
}
