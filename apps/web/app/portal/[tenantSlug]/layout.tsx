"use client";

import { PortalAuthProvider } from "@/lib/portal-auth-context";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-surface">
      <PortalAuthProvider>{children}</PortalAuthProvider>
    </div>
  );
}
