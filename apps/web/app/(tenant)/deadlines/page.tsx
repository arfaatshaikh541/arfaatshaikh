"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { DeadlineItem, DeadlineStatus, LeadSummary, Page } from "@/lib/types";

const STATUS_TONE: Record<DeadlineStatus, string> = {
  open: "text-accent",
  completed: "text-emerald-400",
};

function isOverdue(deadline: DeadlineItem): boolean {
  return deadline.status === "open" && deadline.due_date < new Date().toISOString().slice(0, 10);
}

export default function DeadlinesPage() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const leadIdFilter = searchParams.get("leadId") ?? "";

  const [leadId, setLeadId] = useState(leadIdFilter);
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [recurrenceIntervalDays, setRecurrenceIntervalDays] = useState("");

  const deadlinesQuery = useQuery({
    queryKey: ["tenant", "deadlines", leadIdFilter],
    queryFn: () => api.get<DeadlineItem[]>(`/tenant/deadlines${leadIdFilter ? `?lead_id=${leadIdFilter}` : ""}`),
  });
  const leadsQuery = useQuery({
    queryKey: ["tenant", "leads", "picker"],
    queryFn: () => api.get<Page<LeadSummary>>("/tenant/leads?page_size=200").then((r) => r.items),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post("/tenant/deadlines", {
        lead_id: leadId, title, due_date: dueDate,
        recurrence_interval_days: recurrenceIntervalDays ? Number(recurrenceIntervalDays) : null,
      }),
    onSuccess: () => {
      setTitle("");
      setDueDate("");
      setRecurrenceIntervalDays("");
      queryClient.invalidateQueries({ queryKey: ["tenant", "deadlines"] });
    },
  });

  const completeMutation = useMutation({
    mutationFn: (id: string) => api.post(`/tenant/deadlines/${id}/complete`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "deadlines"] }),
  });

  const leads = leadsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Deadlines</h1>
        <p className="mt-1 text-sm text-ink-muted">
          {leadIdFilter ? "Deadlines for this lead." : "Compliance and service deadlines, with optional recurring reminders."}
        </p>
      </div>

      <Card>
        <CardHeader title="Add a deadline" />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="deadline-lead">Lead</Label>
              <select
                id="deadline-lead"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={leadId}
                onChange={(e) => setLeadId(e.target.value)}
                required
              >
                <option value="">Select a lead…</option>
                {leads.map((lead) => (
                  <option key={lead.id} value={lead.id}>
                    {lead.first_name} {lead.last_name} ({lead.reference_number})
                  </option>
                ))}
              </select>
            </div>
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="deadline-title">Title</Label>
              <Input id="deadline-title" placeholder="e.g. Trade license renewal" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="w-44">
              <Label htmlFor="deadline-due">Due date</Label>
              <Input id="deadline-due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} required />
            </div>
            <div className="w-56">
              <Label htmlFor="deadline-recurrence">Repeats every (days, optional)</Label>
              <Input
                id="deadline-recurrence" type="number" min={1} placeholder="e.g. 365 for annual"
                value={recurrenceIntervalDays} onChange={(e) => setRecurrenceIntervalDays(e.target.value)}
              />
            </div>
          </div>
          <Button type="submit" disabled={createMutation.isPending || !leadId || !title || !dueDate}>
            {createMutation.isPending ? "Adding…" : "Add deadline"}
          </Button>
        </form>
        {createMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to add deadline."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Deadlines" />
        <div className="space-y-2">
          {deadlinesQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No deadlines yet.</p>}
          {deadlinesQuery.data?.map((deadline) => (
            <div key={deadline.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
              <div>
                <p className={deadline.status === "completed" ? "text-ink-faint line-through" : "text-ink"}>{deadline.title}</p>
                <p className="text-xs text-ink-faint">
                  Due {deadline.due_date}
                  {deadline.recurrence_interval_days && ` · repeats every ${deadline.recurrence_interval_days}d`}
                  {isOverdue(deadline) && <span className="ml-1 text-red-400">· overdue</span>}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs font-medium capitalize ${STATUS_TONE[deadline.status]}`}>{deadline.status}</span>
                {deadline.status === "open" && (
                  <Button variant="secondary" onClick={() => completeMutation.mutate(deadline.id)} disabled={completeMutation.isPending}>
                    Complete
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
