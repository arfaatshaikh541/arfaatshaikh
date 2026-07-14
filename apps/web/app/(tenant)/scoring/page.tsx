"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { ScoringOperator, ScoringRule, ScoringSettings } from "@/lib/types";

const OPERATORS: { value: ScoringOperator; label: string }[] = [
  { value: "equals", label: "Equals" },
  { value: "not_equals", label: "Does not equal" },
  { value: "contains", label: "Contains" },
  { value: "greater_than", label: "Greater than" },
  { value: "less_than", label: "Less than" },
  { value: "is_set", label: "Is set (has a value)" },
  { value: "in", label: "Is one of (comma-separated)" },
];

const FIELD_HINT = 'Lead field name (e.g. "estimated_value", "consent_status", "company") or "answer:<question_id>" for a qualification answer.';

export default function ScoringPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [field, setField] = useState("");
  const [operator, setOperator] = useState<ScoringOperator>("equals");
  const [value, setValue] = useState("");
  const [points, setPoints] = useState("10");

  const rulesQuery = useQuery({ queryKey: ["tenant", "scoring", "rules"], queryFn: () => api.get<ScoringRule[]>("/tenant/scoring/rules") });
  const settingsQuery = useQuery({ queryKey: ["tenant", "scoring", "settings"], queryFn: () => api.get<ScoringSettings>("/tenant/scoring/settings") });

  const createRule = useMutation({
    mutationFn: () =>
      api.post("/tenant/scoring/rules", {
        name,
        field,
        operator,
        points: Number(points),
        value: operator === "in" ? value.split(",").map((v) => v.trim()).filter(Boolean) : operator === "is_set" ? null : value,
      }),
    onSuccess: () => {
      setName("");
      setField("");
      setValue("");
      setPoints("10");
      queryClient.invalidateQueries({ queryKey: ["tenant", "scoring", "rules"] });
    },
  });

  const toggleRule = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => api.patch(`/tenant/scoring/rules/${id}`, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "scoring", "rules"] }),
  });

  const updateSettings = useMutation({
    mutationFn: (updates: Partial<ScoringSettings>) => api.patch("/tenant/scoring/settings", updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "scoring", "settings"] }),
  });

  const settings = settingsQuery.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Lead scoring</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Deterministic rules that score every new or updated lead. A lead&apos;s score is the sum of matched rules&apos; points, clamped to 0–100.
        </p>
      </div>

      {settings && (
        <Card>
          <CardHeader title="Priority thresholds" description="When enabled, a lead's priority is set automatically from its score — unless staff have manually changed the priority." />
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <Label htmlFor="hot">Hot threshold (High priority)</Label>
              <Input
                id="hot" type="number" className="w-32" defaultValue={settings.hot_threshold}
                onBlur={(e) => updateSettings.mutate({ hot_threshold: Number(e.target.value) })}
              />
            </div>
            <div>
              <Label htmlFor="warm">Warm threshold (Medium priority)</Label>
              <Input
                id="warm" type="number" className="w-32" defaultValue={settings.warm_threshold}
                onBlur={(e) => updateSettings.mutate({ warm_threshold: Number(e.target.value) })}
              />
            </div>
            <label className="flex items-center gap-2 pb-2 text-sm text-ink">
              <input
                type="checkbox" checked={settings.auto_priority}
                onChange={(e) => updateSettings.mutate({ auto_priority: e.target.checked })}
              />
              Auto-set priority from score
            </label>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Add a scoring rule" description={FIELD_HINT} />
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            createRule.mutate();
          }}
        >
          <div className="min-w-[160px]">
            <Label htmlFor="rule-name">Name</Label>
            <Input id="rule-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="min-w-[200px]">
            <Label htmlFor="rule-field">Field</Label>
            <Input id="rule-field" value={field} onChange={(e) => setField(e.target.value)} required />
          </div>
          <div className="min-w-[180px]">
            <Label htmlFor="rule-operator">Operator</Label>
            <select
              id="rule-operator"
              className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
              value={operator}
              onChange={(e) => setOperator(e.target.value as ScoringOperator)}
            >
              {OPERATORS.map((op) => (
                <option key={op.value} value={op.value}>{op.label}</option>
              ))}
            </select>
          </div>
          {operator !== "is_set" && (
            <div className="min-w-[160px]">
              <Label htmlFor="rule-value">Value</Label>
              <Input id="rule-value" value={value} onChange={(e) => setValue(e.target.value)} />
            </div>
          )}
          <div className="w-28">
            <Label htmlFor="rule-points">Points</Label>
            <Input id="rule-points" type="number" value={points} onChange={(e) => setPoints(e.target.value)} required />
          </div>
          <Button type="submit" disabled={createRule.isPending || !name || !field}>
            {createRule.isPending ? "Adding…" : "Add rule"}
          </Button>
        </form>
        {createRule.isError && (
          <div className="mt-3">
            <Alert tone="error">{createRule.error instanceof ApiError ? createRule.error.message : "Unable to add rule."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Rules" />
        <div className="space-y-2">
          {rulesQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No scoring rules yet.</p>}
          {rulesQuery.data?.map((rule) => (
            <div key={rule.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
              <div>
                <p className="font-medium text-ink">{rule.name}</p>
                <p className="text-xs text-ink-faint">
                  {rule.field} {rule.operator} {rule.operator !== "is_set" ? JSON.stringify(rule.value) : ""} → {rule.points} pts
                </p>
              </div>
              <Button
                variant="secondary"
                onClick={() => toggleRule.mutate({ id: rule.id, is_active: !rule.is_active })}
              >
                {rule.is_active ? "Deactivate" : "Activate"}
              </Button>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
