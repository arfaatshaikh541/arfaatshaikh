"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type {
  EmailTemplate,
  Pipeline,
  WorkflowActionType,
  WorkflowItem,
  WorkflowRunItem,
  WorkflowStepItem,
  WorkflowStepLogItem,
} from "@/lib/types";

const ACTION_TYPES: { value: WorkflowActionType; label: string }[] = [
  { value: "add_tag", label: "Add tag" },
  { value: "create_task", label: "Create task" },
  { value: "change_stage", label: "Change stage" },
  { value: "send_email_template", label: "Send email template" },
];

function RunLogs({ runId }: { runId: string }) {
  const logsQuery = useQuery({
    queryKey: ["workflow-run", runId, "logs"],
    queryFn: () => api.get<WorkflowStepLogItem[]>(`/tenant/workflows/runs/${runId}/logs`),
  });
  return (
    <div className="mt-2 space-y-1 border-l-2 border-surface-border pl-3">
      {logsQuery.data?.map((log) => (
        <p key={log.id} className="text-xs text-ink-muted">
          <span className={log.status === "failed" ? "text-red-400" : "text-emerald-400"}>{log.status}</span> — {log.result_summary}
        </p>
      ))}
      {logsQuery.data?.length === 0 && <p className="text-xs text-ink-faint">No steps executed yet.</p>}
    </div>
  );
}

export default function WorkflowDetailPage({ params }: { params: Promise<{ workflowId: string }> }) {
  const { workflowId } = use(params);
  const queryClient = useQueryClient();

  const [delayMinutes, setDelayMinutes] = useState("0");
  const [actionType, setActionType] = useState<WorkflowActionType>("add_tag");
  const [tagName, setTagName] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDueInHours, setTaskDueInHours] = useState("24");
  const [stageName, setStageName] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  const workflowQuery = useQuery({
    queryKey: ["workflow", workflowId],
    queryFn: () => api.get<WorkflowItem[]>("/tenant/workflows").then((all) => all.find((w) => w.id === workflowId)),
  });
  const stepsQuery = useQuery({ queryKey: ["workflow", workflowId, "steps"], queryFn: () => api.get<WorkflowStepItem[]>(`/tenant/workflows/${workflowId}/steps`) });
  const runsQuery = useQuery({ queryKey: ["workflow", workflowId, "runs"], queryFn: () => api.get<WorkflowRunItem[]>(`/tenant/workflows/${workflowId}/runs`) });
  const pipelinesQuery = useQuery({ queryKey: ["tenant", "pipelines"], queryFn: () => api.get<Pipeline[]>("/tenant/pipelines") });
  const templatesQuery = useQuery({ queryKey: ["tenant", "communications", "templates"], queryFn: () => api.get<EmailTemplate[]>("/tenant/communications/templates") });

  const addStepMutation = useMutation({
    mutationFn: () => {
      let action_config: Record<string, unknown> = {};
      if (actionType === "add_tag") action_config = { tag_name: tagName };
      if (actionType === "create_task") action_config = { title: taskTitle, due_in_hours: Number(taskDueInHours) };
      if (actionType === "change_stage") action_config = { stage_name: stageName };
      if (actionType === "send_email_template") action_config = { template_id: templateId };
      return api.post(`/tenant/workflows/${workflowId}/steps`, { delay_minutes: Number(delayMinutes), action_type: actionType, action_config });
    },
    onSuccess: () => {
      setDelayMinutes("0");
      setTagName("");
      setTaskTitle("");
      setStageName("");
      setTemplateId("");
      queryClient.invalidateQueries({ queryKey: ["workflow", workflowId, "steps"] });
    },
  });

  const stages = pipelinesQuery.data?.[0]?.stages ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">{workflowQuery.data?.name ?? "Workflow"}</h1>
        <p className="mt-1 text-sm text-ink-muted">{workflowQuery.data?.description}</p>
      </div>

      <Card>
        <CardHeader title="Add a step" description="Steps run in order, each waiting the configured delay after the previous one (or after the trigger, for the first step)." />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            addStepMutation.mutate();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <div className="w-40">
              <Label htmlFor="delay">Delay (minutes)</Label>
              <Input id="delay" type="number" min={0} value={delayMinutes} onChange={(e) => setDelayMinutes(e.target.value)} />
            </div>
            <div className="min-w-[220px]">
              <Label htmlFor="action-type">Action</Label>
              <select
                id="action-type"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={actionType}
                onChange={(e) => setActionType(e.target.value as WorkflowActionType)}
              >
                {ACTION_TYPES.map((a) => (
                  <option key={a.value} value={a.value}>{a.label}</option>
                ))}
              </select>
            </div>
          </div>

          {actionType === "add_tag" && (
            <div className="max-w-xs">
              <Label htmlFor="tag-name">Tag name</Label>
              <Input id="tag-name" value={tagName} onChange={(e) => setTagName(e.target.value)} />
            </div>
          )}
          {actionType === "create_task" && (
            <div className="flex flex-wrap gap-3">
              <div className="min-w-[220px]">
                <Label htmlFor="task-title">Task title</Label>
                <Input id="task-title" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} />
              </div>
              <div className="w-40">
                <Label htmlFor="task-due">Due in (hours)</Label>
                <Input id="task-due" type="number" min={1} value={taskDueInHours} onChange={(e) => setTaskDueInHours(e.target.value)} />
              </div>
            </div>
          )}
          {actionType === "change_stage" && (
            <div className="max-w-xs">
              <Label htmlFor="stage-name">Stage</Label>
              <select
                id="stage-name"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={stageName}
                onChange={(e) => setStageName(e.target.value)}
              >
                <option value="">Select…</option>
                {stages.map((s) => (
                  <option key={s.id} value={s.name}>{s.name}</option>
                ))}
              </select>
            </div>
          )}
          {actionType === "send_email_template" && (
            <div className="max-w-xs">
              <Label htmlFor="template">Email template</Label>
              <select
                id="template"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                <option value="">Select…</option>
                {templatesQuery.data?.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
          )}

          <Button type="submit" disabled={addStepMutation.isPending}>
            {addStepMutation.isPending ? "Adding…" : "Add step"}
          </Button>
        </form>
        {addStepMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{addStepMutation.error instanceof ApiError ? addStepMutation.error.message : "Unable to add step."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Steps" />
        <div className="space-y-2">
          {stepsQuery.data?.map((step, index) => (
            <div key={step.id} className="rounded-md border border-surface-border p-3 text-sm">
              <p className="text-ink">
                {index + 1}. {ACTION_TYPES.find((a) => a.value === step.action_type)?.label}
                {step.delay_minutes > 0 && <span className="text-ink-faint"> — after {step.delay_minutes} min</span>}
              </p>
              <p className="mt-1 text-xs text-ink-faint">{JSON.stringify(step.action_config)}</p>
            </div>
          ))}
          {stepsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No steps yet — this workflow won&apos;t do anything until you add one.</p>}
        </div>
      </Card>

      <Card>
        <CardHeader title="Run history" />
        <div className="space-y-2">
          {runsQuery.data?.map((run) => (
            <div key={run.id} className="rounded-md border border-surface-border p-3 text-sm">
              <button className="w-full text-left" onClick={() => setExpandedRunId(expandedRunId === run.id ? null : run.id)}>
                <span className="text-ink">{new Date(run.triggered_at).toLocaleString()}</span>{" "}
                <span className="capitalize text-ink-faint">— {run.status}</span>
              </button>
              {expandedRunId === run.id && <RunLogs runId={run.id} />}
            </div>
          ))}
          {runsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No runs yet.</p>}
        </div>
      </Card>
    </div>
  );
}
