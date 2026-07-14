"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardHeader } from "@/components/ui/card";
import { api } from "@/lib/api-client";

interface SubscriptionResponse {
  plan_code: string | null;
  status: string | null;
  current_period_end: string | null;
  trial_ends_at: string | null;
  modules: Record<string, boolean>;
  features: Record<string, { enabled?: boolean; limit?: number | null }>;
}

export default function SubscriptionPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["tenant", "subscription"],
    queryFn: () => api.get<SubscriptionResponse>("/tenant/subscription"),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Subscription</h1>
        <p className="mt-1 text-sm text-ink-muted">Your workspace&apos;s current plan and module access.</p>
      </div>

      {isLoading && <p className="text-sm text-ink-muted">Loading…</p>}

      {data && (
        <>
          <Card>
            <CardHeader title="Plan" />
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-ink-faint">Plan</dt>
                <dd className="mt-0.5 capitalize text-ink">{data.plan_code ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Status</dt>
                <dd className="mt-0.5 capitalize text-ink">{data.status ?? "—"}</dd>
              </div>
              {data.trial_ends_at && (
                <div>
                  <dt className="text-ink-faint">Trial ends</dt>
                  <dd className="mt-0.5 text-ink">{new Date(data.trial_ends_at).toLocaleDateString()}</dd>
                </div>
              )}
            </dl>
          </Card>

          <Card>
            <CardHeader title="Modules" description="Modules included in this plan, plus any granted add-ons." />
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {Object.entries(data.modules).map(([code, enabled]) => (
                <div
                  key={code}
                  className={`rounded-md border px-3 py-2 text-sm capitalize ${
                    enabled
                      ? "border-accent/40 bg-accent/10 text-ink"
                      : "border-surface-border bg-surface text-ink-faint line-through"
                  }`}
                >
                  {code.replaceAll("_", " ")}
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
