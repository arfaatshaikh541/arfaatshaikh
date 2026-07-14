"use client";

import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api-client";

interface Plan {
  id: string;
  code: string;
  name: string;
  is_custom: boolean;
}

export default function PlansPage() {
  const { data } = useQuery({ queryKey: ["platform", "plans"], queryFn: () => api.get<Plan[]>("/platform/plans") });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Plans</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Subscription plans available to assign to tenants. Plan editing UI ships in Milestone 9 — plans are
          currently data-driven via the seed catalog.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {data?.map((plan) => (
          <Card key={plan.id}>
            <h2 className="text-sm font-semibold text-ink">{plan.name}</h2>
            <p className="mt-1 text-xs text-ink-faint">code: {plan.code}</p>
            {plan.is_custom && <p className="mt-2 text-xs text-accent">Custom plan</p>}
          </Card>
        ))}
      </div>
    </div>
  );
}
