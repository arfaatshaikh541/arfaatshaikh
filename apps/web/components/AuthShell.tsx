import { Card, CardHeader } from "@gridkeep/ui";
import type { ReactNode } from "react";

export function AuthShell({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 px-4">
      <div className="flex items-center gap-2 text-lg font-semibold text-ink-900">
        <span className="h-2.5 w-2.5 rounded-full bg-accent" aria-hidden="true" />
        GRIDKEEP <span className="text-ink-500">Cyber OS</span>
      </div>
      <Card className="w-full max-w-sm">
        <CardHeader title={title} description={description} />
        {children}
      </Card>
    </main>
  );
}
