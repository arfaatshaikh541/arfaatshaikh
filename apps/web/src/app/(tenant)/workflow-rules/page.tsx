"use client";

import { Alert, Badge, Button, Card, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { ApiError, apiFetch } from "@/lib/api-client";
import type {
  MessageTemplateOut,
  TagOut,
  WorkflowActionValue,
  WorkflowConditionValue,
  WorkflowExecutionLogOut,
  WorkflowRuleOut,
} from "@/lib/types";
import {
  WORKFLOW_ACTION_TYPES,
  WORKFLOW_CONDITION_FIELDS,
  WORKFLOW_CONDITION_OPERATORS,
  WORKFLOW_TRIGGER_TYPES,
} from "@/lib/types";

const selectClass =
  "w-full rounded-md border border-surface-700 bg-surface-900 px-2 py-1.5 text-sm text-surface-50";

function emptyCondition(): WorkflowConditionValue {
  return { field: "source", operator: "equals", value: "" };
}

function emptyAction(): WorkflowActionValue {
  return { type: "create_task", title: "Follow up", priority: "normal" };
}

export default function WorkflowRulesPage() {
  const { tenantId, membership } = useCurrentTenant();
  const queryClient = useQueryClient();
  const canManage = membership?.role.permissions.some((p) => p.code === "workflows.manage") ?? false;
  const [serverError, setServerError] = useState<string | null>(null);

  const rulesQuery = useQuery({
    queryKey: ["workflow-rules", tenantId],
    queryFn: () => apiFetch<WorkflowRuleOut[]>("/tenants/me/workflow-rules"),
    enabled: Boolean(tenantId) && canManage,
  });
  const logQuery = useQuery({
    queryKey: ["workflow-execution-log", tenantId],
    queryFn: () => apiFetch<WorkflowExecutionLogOut[]>("/tenants/me/workflow-rules/execution-log"),
    enabled: Boolean(tenantId) && canManage,
  });
  const tagsQuery = useQuery({
    queryKey: ["tags", tenantId],
    queryFn: () => apiFetch<TagOut[]>("/tenants/me/tags"),
    enabled: Boolean(tenantId) && canManage,
  });
  const templatesQuery = useQuery({
    queryKey: ["message-templates", tenantId],
    queryFn: () => apiFetch<MessageTemplateOut[]>("/tenants/me/message-templates"),
    enabled: Boolean(tenantId) && canManage,
  });

  const [name, setName] = useState("");
  const [triggerType, setTriggerType] = useState<string>(WORKFLOW_TRIGGER_TYPES[0][0]);
  const [conditions, setConditions] = useState<WorkflowConditionValue[]>([]);
  const [actions, setActions] = useState<WorkflowActionValue[]>([emptyAction()]);

  const resetForm = () => {
    setName("");
    setTriggerType(WORKFLOW_TRIGGER_TYPES[0][0]);
    setConditions([]);
    setActions([emptyAction()]);
  };

  const createMutation = useMutation({
    mutationFn: () =>
      apiFetch<WorkflowRuleOut>("/tenants/me/workflow-rules", {
        method: "POST",
        body: { name, trigger_type: triggerType, conditions, actions },
      }),
    onSuccess: () => {
      resetForm();
      queryClient.invalidateQueries({ queryKey: ["workflow-rules", tenantId] });
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiFetch<WorkflowRuleOut>(`/tenants/me/workflow-rules/${id}`, {
        method: "PATCH",
        body: { is_active },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workflow-rules", tenantId] }),
  });

  if (!canManage) {
    return (
      <Alert tone="info">
        You don&apos;t have permission to manage workflow automation. Ask an Owner or Administrator.
      </Alert>
    );
  }

  const updateCondition = (index: number, patch: Partial<WorkflowConditionValue>) => {
    setConditions((prev) => prev.map((c, i) => (i === index ? { ...c, ...patch } : c)));
  };
  const updateAction = (index: number, patch: WorkflowActionValue) => {
    setActions((prev) => prev.map((a, i) => (i === index ? patch : a)));
  };

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Workflow automation</h1>
      <p className="mb-6 text-sm text-surface-400">
        Every trigger, condition, and action is a fixed, structured option - there is no code
        field anywhere here, so a rule can never run arbitrary logic.
      </p>

      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}

      <Card className="mb-6">
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Add a rule</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setServerError(null);
            createMutation.mutate();
          }}
          className="space-y-4"
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="rule-name">Name</Label>
              <Input id="rule-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <Label htmlFor="trigger-type">When</Label>
              <select
                id="trigger-type"
                className={selectClass}
                value={triggerType}
                onChange={(e) => setTriggerType(e.target.value)}
              >
                {WORKFLOW_TRIGGER_TYPES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <Label>Conditions (all must match; none = always)</Label>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setConditions((prev) => [...prev, emptyCondition()])}
              >
                + Add condition
              </Button>
            </div>
            <div className="space-y-2">
              {conditions.map((condition, index) => (
                <div key={index} className="flex items-center gap-2">
                  <select
                    className={selectClass}
                    value={condition.field}
                    onChange={(e) => updateCondition(index, { field: e.target.value })}
                  >
                    {WORKFLOW_CONDITION_FIELDS.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                  <select
                    className={selectClass}
                    value={condition.operator}
                    onChange={(e) => updateCondition(index, { operator: e.target.value })}
                  >
                    {WORKFLOW_CONDITION_OPERATORS.map((op) => (
                      <option key={op} value={op}>
                        {op}
                      </option>
                    ))}
                  </select>
                  <Input
                    className="flex-1"
                    value={String(condition.value ?? "")}
                    onChange={(e) => updateCondition(index, { value: e.target.value })}
                    placeholder="value"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setConditions((prev) => prev.filter((_, i) => i !== index))}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <Label>Actions (run in order)</Label>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setActions((prev) => [...prev, emptyAction()])}
              >
                + Add action
              </Button>
            </div>
            <div className="space-y-3">
              {actions.map((action, index) => (
                <div key={index} className="rounded-md border border-surface-800 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <select
                      className={selectClass + " w-64"}
                      value={action.type}
                      onChange={(e) => {
                        const type = e.target.value;
                        if (type === "create_task") {
                          updateAction(index, { type, title: "Follow up", priority: "normal" });
                        } else if (type === "send_email") {
                          updateAction(index, { type, template_key: "follow_up" });
                        } else if (type === "add_tag") {
                          updateAction(index, { type, tag_id: tagsQuery.data?.[0]?.id ?? "" });
                        } else {
                          updateAction(index, { type, title: "Workflow notification", target: "assignee" });
                        }
                      }}
                    >
                      {WORKFLOW_ACTION_TYPES.map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => setActions((prev) => prev.filter((_, i) => i !== index))}
                    >
                      Remove
                    </Button>
                  </div>

                  {action.type === "create_task" ? (
                    <div className="grid grid-cols-3 gap-2">
                      <Input
                        placeholder="Task title"
                        value={String(action.title ?? "")}
                        onChange={(e) => updateAction(index, { ...action, title: e.target.value })}
                      />
                      <select
                        className={selectClass}
                        value={String(action.priority ?? "normal")}
                        onChange={(e) => updateAction(index, { ...action, priority: e.target.value })}
                      >
                        <option value="low">low</option>
                        <option value="normal">normal</option>
                        <option value="high">high</option>
                      </select>
                      <Input
                        type="number"
                        placeholder="Due in hours"
                        value={String(action.due_offset_hours ?? "")}
                        onChange={(e) =>
                          updateAction(index, {
                            ...action,
                            due_offset_hours: e.target.value ? Number(e.target.value) : undefined,
                          })
                        }
                      />
                      <label className="col-span-3 flex items-center gap-2 text-xs text-surface-400">
                        <input
                          type="checkbox"
                          checked={action.assign_to === "assignee"}
                          onChange={(e) =>
                            updateAction(index, {
                              ...action,
                              assign_to: e.target.checked ? "assignee" : undefined,
                            })
                          }
                        />
                        Assign to the lead&apos;s current assignee
                      </label>
                    </div>
                  ) : null}

                  {action.type === "send_email" ? (
                    <select
                      className={selectClass}
                      value={String(action.template_key ?? "")}
                      onChange={(e) => updateAction(index, { ...action, template_key: e.target.value })}
                    >
                      {(templatesQuery.data ?? []).map((t) => (
                        <option key={t.key} value={t.key}>
                          {t.key}
                        </option>
                      ))}
                      <option value="follow_up">follow_up</option>
                      <option value="acknowledgement">acknowledgement</option>
                    </select>
                  ) : null}

                  {action.type === "add_tag" ? (
                    <select
                      className={selectClass}
                      value={String(action.tag_id ?? "")}
                      onChange={(e) => updateAction(index, { ...action, tag_id: e.target.value })}
                    >
                      <option value="">Select a tag…</option>
                      {tagsQuery.data?.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  ) : null}

                  {action.type === "create_notification" ? (
                    <Input
                      placeholder="Notification title"
                      value={String(action.title ?? "")}
                      onChange={(e) => updateAction(index, { ...action, title: e.target.value })}
                    />
                  ) : null}
                </div>
              ))}
            </div>
          </div>

          <Button type="submit" loading={createMutation.isPending}>
            Add rule
          </Button>
        </form>
      </Card>

      <Card className="mb-6">
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Rules</h2>
        <div className="space-y-3">
          {rulesQuery.data?.map((rule) => (
            <div key={rule.id} className="rounded-md border border-surface-800 p-3">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-sm font-medium text-surface-100">{rule.name}</span>
                <div className="flex items-center gap-2">
                  <Badge tone={rule.is_active ? "success" : "neutral"}>
                    {rule.is_active ? "active" : "inactive"}
                  </Badge>
                  <Button
                    variant="ghost"
                    onClick={() => toggleMutation.mutate({ id: rule.id, is_active: !rule.is_active })}
                  >
                    {rule.is_active ? "Deactivate" : "Activate"}
                  </Button>
                </div>
              </div>
              <p className="text-xs text-surface-500">
                When <strong>{rule.trigger_type}</strong>
                {rule.conditions.length > 0
                  ? " and " +
                    rule.conditions.map((c) => `${c.field} ${c.operator} ${c.value}`).join(", ")
                  : ""}{" "}
                → {rule.actions.map((a) => a.type).join(", ")}
              </p>
            </div>
          ))}
          {rulesQuery.data && rulesQuery.data.length === 0 ? (
            <p className="text-sm text-surface-500">No workflow rules yet.</p>
          ) : null}
        </div>
      </Card>

      <Card>
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Recent executions</h2>
        <div className="space-y-2">
          {logQuery.data?.map((entry) => (
            <div key={entry.id} className="flex items-center justify-between text-sm">
              <span className="text-surface-300">
                {entry.trigger_type} - {entry.actions_taken.map((a) => `${a.type}:${a.result}`).join(", ")}
              </span>
              <span className="text-xs text-surface-500">
                {new Date(entry.executed_at).toLocaleString()}
              </span>
            </div>
          ))}
          {logQuery.data && logQuery.data.length === 0 ? (
            <p className="text-sm text-surface-500">No rules have fired yet.</p>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
