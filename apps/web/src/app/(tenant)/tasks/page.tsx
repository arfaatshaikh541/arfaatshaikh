"use client";

import { Alert, Badge, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { MemberOut, TaskListOut, TaskOut, TaskTypeOut } from "@/lib/types";
import { TASK_PRIORITIES } from "@/lib/types";

interface TaskFormValues {
  title: string;
  description: string;
  priority: string;
  due_at: string;
  assigned_membership_id: string;
  task_type_id: string;
}

const PRIORITY_TONE: Record<string, "danger" | "warning" | "neutral"> = {
  high: "danger",
  normal: "warning",
  low: "neutral",
};

export default function TasksPage() {
  const { tenantId, membership } = useCurrentTenant();
  const { data: user } = useCurrentUser();
  const queryClient = useQueryClient();
  const canManage = membership?.role.permissions.some((p) => p.code === "tasks.manage") ?? false;
  const [serverError, setServerError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("open");
  const [overdueOnly, setOverdueOnly] = useState(false);

  const tasksQuery = useQuery({
    queryKey: ["tasks", tenantId],
    queryFn: () => apiFetch<TaskListOut>("/tenants/me/tasks?page_size=100"),
    enabled: Boolean(tenantId),
  });
  const membersQuery = useQuery({
    queryKey: ["members", tenantId],
    queryFn: () => apiFetch<MemberOut[]>("/tenants/me/members"),
    enabled: Boolean(tenantId),
  });
  const taskTypesQuery = useQuery({
    queryKey: ["task-types", tenantId],
    queryFn: () => apiFetch<TaskTypeOut[]>("/tenants/me/task-types"),
    enabled: Boolean(tenantId),
  });

  const membersById = new Map((membersQuery.data ?? []).map((m) => [m.id, m]));
  const ownMembershipId = membersQuery.data?.find((m) => m.user_id === user?.id)?.id;

  const { register, handleSubmit, reset, formState } = useForm<TaskFormValues>({
    defaultValues: {
      title: "",
      description: "",
      priority: "normal",
      due_at: "",
      assigned_membership_id: "",
      task_type_id: "",
    },
  });

  const createTaskMutation = useMutation({
    mutationFn: (values: TaskFormValues) =>
      apiFetch<TaskOut>("/tenants/me/tasks", {
        method: "POST",
        body: {
          title: values.title,
          description: values.description || null,
          priority: values.priority,
          due_at: values.due_at ? new Date(values.due_at).toISOString() : null,
          assigned_membership_id: values.assigned_membership_id || null,
          task_type_id: values.task_type_id || null,
        },
      }),
    onSuccess: () => {
      reset();
      queryClient.invalidateQueries({ queryKey: ["tasks", tenantId] });
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const completeMutation = useMutation({
    mutationFn: (taskId: string) =>
      apiFetch<TaskOut>(`/tenants/me/tasks/${taskId}/complete`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks", tenantId] }),
  });

  const items = tasksQuery.data?.items ?? [];
  const filtered = items.filter((t) => {
    if (statusFilter !== "all" && t.status !== statusFilter) return false;
    if (overdueOnly && !t.is_overdue) return false;
    return true;
  });

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Tasks &amp; follow-ups</h1>
      <p className="mb-6 text-sm text-surface-400">
        Overdue status is computed from the due date and current status, not a stored flag.
      </p>

      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}

      <Card className="mb-6">
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Add a task</h2>
        <form
          onSubmit={handleSubmit((values) => {
            setServerError(null);
            createTaskMutation.mutate(values);
          })}
          className="space-y-3"
          noValidate
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="task-title">Title</Label>
              <Input id="task-title" {...register("title", { required: true })} />
              <FormError message={formState.errors.title ? "Title is required" : undefined} />
            </div>
            <div>
              <Label htmlFor="task-priority">Priority</Label>
              <select
                id="task-priority"
                className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                {...register("priority")}
              >
                {TASK_PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <Label htmlFor="task-description">Description (optional)</Label>
            <Input id="task-description" {...register("description")} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label htmlFor="task-due">Due date</Label>
              <Input id="task-due" type="datetime-local" {...register("due_at")} />
            </div>
            <div>
              <Label htmlFor="task-assignee">Assignee</Label>
              <select
                id="task-assignee"
                className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                {...register("assigned_membership_id")}
              >
                <option value="">Unassigned</option>
                {membersQuery.data?.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.first_name} {m.last_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="task-type">Type (optional)</Label>
              <select
                id="task-type"
                className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                {...register("task_type_id")}
              >
                <option value="">None</option>
                {taskTypesQuery.data?.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <Button type="submit" loading={createTaskMutation.isPending}>
            Add task
          </Button>
        </form>
      </Card>

      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-4">
          <h2 className="text-sm font-semibold text-surface-100">Tasks</h2>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-surface-700 bg-surface-900 px-2 py-1 text-sm text-surface-100"
          >
            <option value="open">Open</option>
            <option value="completed">Completed</option>
            <option value="all">All</option>
          </select>
          <label className="flex items-center gap-2 text-sm text-surface-300">
            <input
              type="checkbox"
              checked={overdueOnly}
              onChange={(e) => setOverdueOnly(e.target.checked)}
            />
            Overdue only
          </label>
          {ownMembershipId ? (
            <span className="text-xs text-surface-500">You: {membersById.get(ownMembershipId)?.first_name}</span>
          ) : null}
        </div>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-800 text-surface-500">
              <th className="pb-2 font-medium">Title</th>
              <th className="pb-2 font-medium">Priority</th>
              <th className="pb-2 font-medium">Assignee</th>
              <th className="pb-2 font-medium">Due</th>
              <th className="pb-2 font-medium">Status</th>
              {canManage ? <th className="pb-2 font-medium">Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {filtered.map((task) => {
              const assignee = task.assigned_membership_id
                ? membersById.get(task.assigned_membership_id)
                : null;
              return (
                <tr key={task.id} className="border-b border-surface-900">
                  <td className="py-2 text-surface-200">{task.title}</td>
                  <td className="py-2">
                    <Badge tone={PRIORITY_TONE[task.priority] ?? "neutral"}>{task.priority}</Badge>
                  </td>
                  <td className="py-2 text-surface-400">
                    {assignee ? `${assignee.first_name} ${assignee.last_name}` : "Unassigned"}
                  </td>
                  <td className="py-2 text-surface-400">
                    {task.due_at ? new Date(task.due_at).toLocaleString() : "—"}
                    {task.is_overdue ? (
                      <Badge tone="danger" className="ml-2">
                        overdue
                      </Badge>
                    ) : null}
                  </td>
                  <td className="py-2">
                    <Badge tone={task.status === "completed" ? "success" : "neutral"}>
                      {task.status}
                    </Badge>
                  </td>
                  {canManage ? (
                    <td className="py-2">
                      {task.status === "open" ? (
                        <Button variant="ghost" onClick={() => completeMutation.mutate(task.id)}>
                          Complete
                        </Button>
                      ) : null}
                    </td>
                  ) : null}
                </tr>
              );
            })}
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-4 text-center text-surface-500">
                  No tasks match these filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
