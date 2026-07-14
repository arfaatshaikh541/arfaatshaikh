"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { WorkflowItem, WorkflowTriggerEvent } from "@/lib/types";

const TRIGGER_EVENTS: { value: WorkflowTriggerEvent; label: string; configField?: { key: string; label: string; placeholder: string } }[] = [
  { value: "lead_created", label: "Lead created" },
  { value: "stage_changed", label: "Stage changed", configField: { key: "stage_name", label: "Stage name", placeholder: "e.g. Qualified" } },
  { value: "score_threshold_reached", label: "Score threshold reached", configField: { key: "min_score", label: "Minimum score", placeholder: "e.g. 50" } },
  { value: "tag_added", label: "Tag added", configField: { key: "tag_name", label: "Tag name", placeholder: "e.g. Hot Lead" } },
  { value: "appointment_booked", label: "Appointment booked", configField: { key: "appointment_type_name", label: "Appointment type (optional)", placeholder: "Leave blank for any" } },
  { value: "appointment_completed", label: "Appointment completed", configField: { key: "appointment_type_name", label: "Appointment type (optional)", placeholder: "Leave blank for any" } },
];

export default function WorkflowsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [triggerEvent, setTriggerEvent] = useState<WorkflowTriggerEvent>("lead_created");
  const [configValue, setConfigValue] = useState("");

  const workflowsQuery = useQuery({ queryKey: ["tenant", "workflows"], queryFn: () => api.get<WorkflowItem[]>("/tenant/workflows") });
  const triggerMeta = TRIGGER_EVENTS.find((t) => t.value === triggerEvent);

  const createMutation = useMutation({
    mutationFn: () => {
      const trigger_config: Record<string, unknown> = {};
      if (triggerMeta?.configField && configValue.trim()) {
        trigger_config[triggerMeta.configField.key] = triggerMeta.configField.key === "min_score" ? Number(configValue) : configValue.trim();
      }
      return api.post("/tenant/workflows", { name, description, trigger_event: triggerEvent, trigger_config, conditions: [] });
    },
    onSuccess: () => {
      setName("");
      setDescription("");
      setConfigValue("");
      queryClient.invalidateQueries({ queryKey: ["tenant", "workflows"] });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => api.patch(`/tenant/workflows/${id}`, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "workflows"] }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Workflow automation</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Trigger-condition-action sequences that run automatically for every matching lead. Steps run within the next scheduling sweep (up to 15 minutes), even ones with no configured delay.
        </p>
      </div>

      <Card>
        <CardHeader title="Add a workflow" description="Add steps (with optional delays and conditions) after creating the workflow." />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[200px]">
              <Label htmlFor="wf-name">Name</Label>
              <Input id="wf-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="min-w-[260px]">
              <Label htmlFor="wf-trigger">Trigger</Label>
              <select
                id="wf-trigger"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={triggerEvent}
                onChange={(e) => { setTriggerEvent(e.target.value as WorkflowTriggerEvent); setConfigValue(""); }}
              >
                {TRIGGER_EVENTS.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            {triggerMeta?.configField && (
              <div className="min-w-[220px]">
                <Label htmlFor="wf-config">{triggerMeta.configField.label}</Label>
                <Input id="wf-config" placeholder={triggerMeta.configField.placeholder} value={configValue} onChange={(e) => setConfigValue(e.target.value)} />
              </div>
            )}
          </div>
          <div>
            <Label htmlFor="wf-description">Description</Label>
            <Input id="wf-description" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <Button type="submit" disabled={createMutation.isPending || !name}>
            {createMutation.isPending ? "Adding…" : "Add workflow"}
          </Button>
        </form>
        {createMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to add workflow."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Workflows" />
        <div className="space-y-2">
          {workflowsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No workflows yet.</p>}
          {workflowsQuery.data?.map((workflow) => (
            <div key={workflow.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
              <Link href={`/workflows/${workflow.id}`} className="flex-1 text-ink hover:text-accent">
                <p className="font-medium">{workflow.name}</p>
                <p className="text-xs text-ink-faint">
                  {TRIGGER_EVENTS.find((t) => t.value === workflow.trigger_event)?.label}
                  {workflow.conditions.length > 0 && ` · ${workflow.conditions.length} condition(s)`}
                </p>
              </Link>
              <Button variant="secondary" onClick={() => toggleMutation.mutate({ id: workflow.id, is_active: !workflow.is_active })}>
                {workflow.is_active ? "Deactivate" : "Activate"}
              </Button>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
