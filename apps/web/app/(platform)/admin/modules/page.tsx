"use client";

import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api-client";

interface ModuleItem {
  id: string;
  code: string;
  name: string;
}

export default function ModulesPage() {
  const { data } = useQuery({ queryKey: ["platform", "modules"], queryFn: () => api.get<ModuleItem[]>("/platform/modules") });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Modules</h1>
        <p className="mt-1 text-sm text-ink-muted">The full module catalog available across all plans.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {data?.map((module) => (
          <Card key={module.id}>
            <p className="text-sm font-medium text-ink">{module.name}</p>
            <p className="mt-1 text-xs text-ink-faint">{module.code}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
