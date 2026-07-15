"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { PlatformUsageMetric } from "@/lib/types";

function UsageMetricCard({ metric }: { metric: PlatformUsageMetric }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(metric.name);
  const [unit, setUnit] = useState(metric.unit);

  const updateMutation = useMutation({
    mutationFn: () => api.put(`/platform/usage-metrics/${metric.id}`, { name, unit }),
    onSuccess: () => {
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["platform", "usage-metrics"] });
    },
  });

  if (!editing) {
    return (
      <Card>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-ink">{metric.name}</p>
            <p className="mt-1 text-xs text-ink-faint">
              code: {metric.code} · unit: {metric.unit}
            </p>
          </div>
          <Button variant="ghost" onClick={() => setEditing(true)}>
            Edit
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="space-y-3">
        {updateMutation.isError && (
          <Alert tone="error">{updateMutation.error instanceof ApiError ? updateMutation.error.message : "Update failed."}</Alert>
        )}
        <div>
          <Label htmlFor={`metric-name-${metric.id}`}>Name</Label>
          <Input id={`metric-name-${metric.id}`} value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label htmlFor={`metric-unit-${metric.id}`}>Unit</Label>
          <Input id={`metric-unit-${metric.id}`} value={unit} onChange={(e) => setUnit(e.target.value)} />
        </div>
        <div className="flex gap-2">
          <Button onClick={() => updateMutation.mutate()} disabled={updateMutation.isPending || !name.trim()}>
            Save
          </Button>
          <Button variant="secondary" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      </div>
    </Card>
  );
}

export default function UsageMetricsPage() {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("count");

  const metricsQuery = useQuery({ queryKey: ["platform", "usage-metrics"], queryFn: () => api.get<PlatformUsageMetric[]>("/platform/usage-metrics") });

  const createMutation = useMutation({
    mutationFn: () => api.post("/platform/usage-metrics", { code, name, unit }),
    onSuccess: () => {
      setCode("");
      setName("");
      setUnit("count");
      queryClient.invalidateQueries({ queryKey: ["platform", "usage-metrics"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Usage metrics</h1>
        <p className="mt-1 text-sm text-ink-muted">The countable resources limit features are measured against (e.g. active leads, messages sent).</p>
      </div>

      <Card>
        <CardHeader title="Add a usage metric" />
        {createMutation.isError && (
          <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Could not create usage metric."}</Alert>
        )}
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="min-w-[160px] flex-1">
            <Label htmlFor="new-metric-code">Code</Label>
            <Input id="new-metric-code" placeholder="e.g. filings_submitted" value={code} onChange={(e) => setCode(e.target.value)} required />
          </div>
          <div className="min-w-[200px] flex-1">
            <Label htmlFor="new-metric-name">Name</Label>
            <Input id="new-metric-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="min-w-[120px]">
            <Label htmlFor="new-metric-unit">Unit</Label>
            <Input id="new-metric-unit" value={unit} onChange={(e) => setUnit(e.target.value)} />
          </div>
          <Button type="submit" disabled={createMutation.isPending}>
            Create
          </Button>
        </form>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {metricsQuery.data?.map((metric) => (
          <UsageMetricCard key={metric.id} metric={metric} />
        ))}
      </div>
    </div>
  );
}
