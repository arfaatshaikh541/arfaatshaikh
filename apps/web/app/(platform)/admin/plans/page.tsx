"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { PlanFeatureGrant, PlatformFeature, PlatformPlan } from "@/lib/types";

function PlanFeatureEditor({ plan }: { plan: PlatformPlan }) {
  const queryClient = useQueryClient();
  const featuresQuery = useQuery({ queryKey: ["platform", "features"], queryFn: () => api.get<PlatformFeature[]>("/platform/features") });
  const grantsQuery = useQuery({
    queryKey: ["platform", "plans", plan.id, "features"],
    queryFn: () => api.get<PlanFeatureGrant[]>(`/platform/plans/${plan.id}/features`),
  });

  const grantsByCode = new Map((grantsQuery.data ?? []).map((g) => [g.feature_code, g]));

  const setFeatureMutation = useMutation({
    mutationFn: (input: { feature_code: string; enabled: boolean; limit: number | null }) =>
      api.put(`/platform/plans/${plan.id}/features`, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["platform", "plans", plan.id, "features"] }),
  });

  const removeFeatureMutation = useMutation({
    mutationFn: (featureCode: string) =>
      api.delete(`/platform/plans/${plan.id}/features?feature_code=${encodeURIComponent(featureCode)}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["platform", "plans", plan.id, "features"] }),
  });

  return (
    <div className="mt-4 space-y-2 border-t border-surface-border pt-4">
      {(setFeatureMutation.isError || removeFeatureMutation.isError) && (
        <Alert tone="error">
          {(setFeatureMutation.error instanceof ApiError && setFeatureMutation.error.message) ||
            (removeFeatureMutation.error instanceof ApiError && removeFeatureMutation.error.message) ||
            "Could not update grant."}
        </Alert>
      )}
      {featuresQuery.data?.map((feature) => {
        const grant = grantsByCode.get(feature.code);
        const granted = !!grant;
        return (
          <div key={feature.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-surface-border px-3 py-2 text-sm">
            <div>
              <span className="text-ink">{feature.name}</span>
              <span className="ml-2 text-xs text-ink-faint">
                {feature.module_code} · {feature.code} · {feature.feature_type}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {feature.feature_type === "limit" && (
                <Input
                  type="number"
                  min={0}
                  placeholder="unlimited"
                  className="w-28"
                  defaultValue={grant?.config.limit ?? ""}
                  onBlur={(e) =>
                    setFeatureMutation.mutate({
                      feature_code: feature.code,
                      enabled: true,
                      limit: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                />
              )}
              <label className="flex items-center gap-1.5 text-xs text-ink-muted">
                <input
                  type="checkbox"
                  checked={granted}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setFeatureMutation.mutate({ feature_code: feature.code, enabled: true, limit: grant?.config.limit ?? null });
                    } else {
                      removeFeatureMutation.mutate(feature.code);
                    }
                  }}
                />
                Granted
              </label>
            </div>
          </div>
        );
      })}
      {featuresQuery.data?.length === 0 && <p className="text-xs text-ink-faint">No features exist yet — add some under Modules.</p>}
    </div>
  );
}

function PlanCard({ plan }: { plan: PlatformPlan }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(plan.name);
  const [description, setDescription] = useState(plan.description);
  const [showFeatures, setShowFeatures] = useState(false);

  const updateMutation = useMutation({
    mutationFn: () => api.put(`/platform/plans/${plan.id}`, { name, description }),
    onSuccess: () => {
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["platform", "plans"] });
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: () => api.post(`/platform/plans/${plan.id}/active`, { is_active: !plan.is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["platform", "plans"] }),
  });

  return (
    <Card>
      {editing ? (
        <div className="space-y-3">
          {updateMutation.isError && (
            <Alert tone="error">{updateMutation.error instanceof ApiError ? updateMutation.error.message : "Update failed."}</Alert>
          )}
          <div>
            <Label htmlFor={`plan-name-${plan.id}`}>Name</Label>
            <Input id={`plan-name-${plan.id}`} value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <Label htmlFor={`plan-desc-${plan.id}`}>Description</Label>
            <Input id={`plan-desc-${plan.id}`} value={description} onChange={(e) => setDescription(e.target.value)} />
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
      ) : (
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-sm font-semibold text-ink">{plan.name}</h2>
            <p className="mt-1 text-xs text-ink-faint">code: {plan.code}</p>
            {plan.description && <p className="mt-1 text-xs text-ink-muted">{plan.description}</p>}
            <div className="mt-2 flex gap-2">
              {plan.is_custom && <span className="text-xs text-accent">Custom plan</span>}
              {!plan.is_active && <span className="text-xs text-amber-400">Inactive</span>}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <Button variant="ghost" onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button variant="secondary" onClick={() => toggleActiveMutation.mutate()} disabled={toggleActiveMutation.isPending}>
              {plan.is_active ? "Deactivate" : "Activate"}
            </Button>
          </div>
        </div>
      )}

      <Button variant="ghost" className="mt-3" onClick={() => setShowFeatures((v) => !v)}>
        {showFeatures ? "Hide feature grants" : "Manage feature grants"}
      </Button>
      {showFeatures && <PlanFeatureEditor plan={plan} />}
    </Card>
  );
}

export default function PlansPage() {
  const queryClient = useQueryClient();
  const [showInactive, setShowInactive] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isCustom, setIsCustom] = useState(false);

  const plansQuery = useQuery({
    queryKey: ["platform", "plans", showInactive],
    queryFn: () => api.get<PlatformPlan[]>(`/platform/plans${showInactive ? "?all_plans=true" : ""}`),
  });

  const createMutation = useMutation({
    mutationFn: () => api.post("/platform/plans", { code, name, description, is_custom: isCustom }),
    onSuccess: () => {
      setCode("");
      setName("");
      setDescription("");
      setIsCustom(false);
      queryClient.invalidateQueries({ queryKey: ["platform", "plans"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Plans</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Subscription plans available to assign to tenants, and which features each one grants.
        </p>
      </div>

      <Card>
        <CardHeader title="Add a plan" />
        {createMutation.isError && (
          <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Could not create plan."}</Alert>
        )}
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="min-w-[140px] flex-1">
            <Label htmlFor="new-plan-code">Code</Label>
            <Input id="new-plan-code" placeholder="e.g. boutique" value={code} onChange={(e) => setCode(e.target.value)} required />
          </div>
          <div className="min-w-[180px] flex-1">
            <Label htmlFor="new-plan-name">Name</Label>
            <Input id="new-plan-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="min-w-[220px] flex-1">
            <Label htmlFor="new-plan-desc">Description</Label>
            <Input id="new-plan-desc" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <label className="flex items-center gap-1.5 pb-2 text-xs text-ink-muted">
            <input type="checkbox" checked={isCustom} onChange={(e) => setIsCustom(e.target.checked)} />
            Custom plan
          </label>
          <Button type="submit" disabled={createMutation.isPending}>
            Create
          </Button>
        </form>
      </Card>

      <label className="flex items-center gap-1.5 text-xs text-ink-muted">
        <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
        Show inactive plans
      </label>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {plansQuery.data?.map((plan) => (
          <PlanCard key={plan.id} plan={plan} />
        ))}
      </div>
    </div>
  );
}
