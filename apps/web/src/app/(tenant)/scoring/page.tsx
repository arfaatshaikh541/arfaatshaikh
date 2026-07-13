"use client";

import { Alert, Badge, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { ScoringRuleOut, ServiceOut, TenantScoringSettingsOut } from "@/lib/types";
import { SCORING_RULE_TYPES } from "@/lib/types";

const TYPES_WITH_SERVICE = new Set(["service_equals"]);
const TYPES_WITH_SOURCE = new Set(["source_equals"]);
const TYPES_WITH_MIN_VALUE = new Set(["estimated_value_at_least"]);

interface RuleFormValues {
  name: string;
  rule_type: string;
  points: number;
  service_id: string;
  source: string;
  min_value: number;
}

interface ThresholdFormValues {
  hot_threshold: number;
  warm_threshold: number;
  standard_threshold: number;
}

export default function ScoringPage() {
  const { tenantId, membership } = useCurrentTenant();
  const queryClient = useQueryClient();
  const canManage = membership?.role.permissions.some((p) => p.code === "scoring.manage") ?? false;
  const [serverError, setServerError] = useState<string | null>(null);

  const rulesQuery = useQuery({
    queryKey: ["scoring-rules", tenantId],
    queryFn: () => apiFetch<ScoringRuleOut[]>("/tenants/me/scoring/rules"),
    enabled: Boolean(tenantId),
  });
  const thresholdsQuery = useQuery({
    queryKey: ["scoring-thresholds", tenantId],
    queryFn: () => apiFetch<TenantScoringSettingsOut>("/tenants/me/scoring/thresholds"),
    enabled: Boolean(tenantId),
  });
  const servicesQuery = useQuery({
    queryKey: ["services", tenantId],
    queryFn: () => apiFetch<ServiceOut[]>("/tenants/me/services"),
    enabled: Boolean(tenantId),
  });

  const { register, handleSubmit, reset, watch, formState } = useForm<RuleFormValues>({
    defaultValues: {
      name: "",
      rule_type: "consent_given",
      points: 10,
      service_id: "",
      source: "",
      min_value: 0,
    },
  });
  const ruleType = watch("rule_type");

  const createRuleMutation = useMutation({
    mutationFn: (values: RuleFormValues) => {
      let config: Record<string, unknown> = {};
      if (TYPES_WITH_SERVICE.has(values.rule_type)) config = { service_id: values.service_id };
      if (TYPES_WITH_SOURCE.has(values.rule_type)) config = { source: values.source };
      if (TYPES_WITH_MIN_VALUE.has(values.rule_type)) config = { min_value: values.min_value };
      return apiFetch<ScoringRuleOut>("/tenants/me/scoring/rules", {
        method: "POST",
        body: { name: values.name, rule_type: values.rule_type, points: values.points, config },
      });
    },
    onSuccess: () => {
      reset();
      queryClient.invalidateQueries({ queryKey: ["scoring-rules", tenantId] });
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const toggleRuleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiFetch<ScoringRuleOut>(`/tenants/me/scoring/rules/${id}`, {
        method: "PATCH",
        body: { is_active },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scoring-rules", tenantId] }),
  });

  const {
    register: registerThresholds,
    handleSubmit: handleThresholdsSubmit,
    reset: resetThresholds,
    formState: thresholdsFormState,
  } = useForm<ThresholdFormValues>({
    values: thresholdsQuery.data
      ? {
          hot_threshold: thresholdsQuery.data.hot_threshold,
          warm_threshold: thresholdsQuery.data.warm_threshold,
          standard_threshold: thresholdsQuery.data.standard_threshold,
        }
      : undefined,
  });

  const updateThresholdsMutation = useMutation({
    mutationFn: (values: ThresholdFormValues) =>
      apiFetch<TenantScoringSettingsOut>("/tenants/me/scoring/thresholds", {
        method: "PATCH",
        body: values,
      }),
    onSuccess: (data) => {
      resetThresholds(data);
      queryClient.invalidateQueries({ queryKey: ["scoring-thresholds", tenantId] });
    },
  });

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Lead scoring</h1>
      <p className="mb-6 text-sm text-surface-400">
        Every point awarded traces back to a named rule - there is no black-box or ML scoring.
        Priority bands are derived from the thresholds below.
      </p>

      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}

      <Card className="mb-6">
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Priority thresholds</h2>
        <form
          onSubmit={handleThresholdsSubmit((values) => updateThresholdsMutation.mutate(values))}
          className="flex flex-wrap items-end gap-3"
          noValidate
        >
          <div>
            <Label htmlFor="hot-threshold">Hot (score ≥)</Label>
            <Input
              id="hot-threshold"
              type="number"
              className="w-28"
              disabled={!canManage}
              {...registerThresholds("hot_threshold", { valueAsNumber: true })}
            />
          </div>
          <div>
            <Label htmlFor="warm-threshold">Warm (score ≥)</Label>
            <Input
              id="warm-threshold"
              type="number"
              className="w-28"
              disabled={!canManage}
              {...registerThresholds("warm_threshold", { valueAsNumber: true })}
            />
          </div>
          <div>
            <Label htmlFor="standard-threshold">Standard (score ≥)</Label>
            <Input
              id="standard-threshold"
              type="number"
              className="w-28"
              disabled={!canManage}
              {...registerThresholds("standard_threshold", { valueAsNumber: true })}
            />
          </div>
          {canManage ? (
            <Button type="submit" loading={updateThresholdsMutation.isPending}>
              Save thresholds
            </Button>
          ) : null}
        </form>
        <p className="mt-2 text-xs text-surface-500">
          Below the standard threshold, a lead is scored &quot;low priority&quot;.
        </p>
      </Card>

      {canManage ? (
        <Card className="mb-6">
          <h2 className="mb-4 text-sm font-semibold text-surface-100">Add a scoring rule</h2>
          <form
            onSubmit={handleSubmit((values) => {
              setServerError(null);
              createRuleMutation.mutate(values);
            })}
            className="space-y-3"
            noValidate
          >
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label htmlFor="rule-name">Name</Label>
                <Input id="rule-name" {...register("name", { required: true })} />
                <FormError message={formState.errors.name ? "Name is required" : undefined} />
              </div>
              <div>
                <Label htmlFor="rule-type">Rule type</Label>
                <select
                  id="rule-type"
                  className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                  {...register("rule_type")}
                >
                  {SCORING_RULE_TYPES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="rule-points">Points</Label>
                <Input
                  id="rule-points"
                  type="number"
                  {...register("points", { required: true, valueAsNumber: true })}
                />
              </div>
            </div>
            {TYPES_WITH_SERVICE.has(ruleType) ? (
              <div>
                <Label htmlFor="rule-service">Service</Label>
                <select
                  id="rule-service"
                  className="w-64 rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                  {...register("service_id")}
                >
                  <option value="">Select a service…</option>
                  {servicesQuery.data?.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
            {TYPES_WITH_SOURCE.has(ruleType) ? (
              <div>
                <Label htmlFor="rule-source">Source</Label>
                <Input id="rule-source" placeholder="google, referral, direct…" {...register("source")} />
              </div>
            ) : null}
            {TYPES_WITH_MIN_VALUE.has(ruleType) ? (
              <div>
                <Label htmlFor="rule-min-value">Minimum estimated value</Label>
                <Input
                  id="rule-min-value"
                  type="number"
                  className="w-40"
                  {...register("min_value", { valueAsNumber: true })}
                />
              </div>
            ) : null}
            <Button type="submit" loading={createRuleMutation.isPending}>
              Add rule
            </Button>
          </form>
        </Card>
      ) : null}

      <Card>
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Rules</h2>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-800 text-surface-500">
              <th className="pb-2 font-medium">Name</th>
              <th className="pb-2 font-medium">Type</th>
              <th className="pb-2 font-medium">Points</th>
              <th className="pb-2 font-medium">Status</th>
              {canManage ? <th className="pb-2 font-medium">Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {rulesQuery.data?.map((rule) => (
              <tr key={rule.id} className="border-b border-surface-900">
                <td className="py-2 text-surface-200">{rule.name}</td>
                <td className="py-2 text-surface-400">{rule.rule_type}</td>
                <td className="py-2 text-surface-200">{rule.points}</td>
                <td className="py-2">
                  <Badge tone={rule.is_active ? "success" : "neutral"}>
                    {rule.is_active ? "active" : "inactive"}
                  </Badge>
                </td>
                {canManage ? (
                  <td className="py-2">
                    <Button
                      variant="ghost"
                      onClick={() =>
                        toggleRuleMutation.mutate({ id: rule.id, is_active: !rule.is_active })
                      }
                    >
                      {rule.is_active ? "Deactivate" : "Activate"}
                    </Button>
                  </td>
                ) : null}
              </tr>
            ))}
            {rulesQuery.data && rulesQuery.data.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-4 text-center text-surface-500">
                  No scoring rules yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
