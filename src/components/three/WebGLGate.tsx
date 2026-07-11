"use client";

import { useEffect, useState, type ReactNode } from "react";
import { isWebGLAvailable } from "@/lib/three";

export function WebGLGate({
  children,
  fallback,
}: {
  children: ReactNode;
  fallback: ReactNode;
}) {
  const [supported, setSupported] = useState<boolean | null>(null);

  useEffect(() => {
    setSupported(isWebGLAvailable());
  }, []);

  if (supported === null) return <>{fallback}</>;
  return supported ? <>{children}</> : <>{fallback}</>;
}
