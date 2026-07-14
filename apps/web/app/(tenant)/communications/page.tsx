"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { EmailDeliveryLog, EmailTemplate, EmailTriggerEvent } from "@/lib/types";

const TRIGGER_EVENTS: { value: EmailTriggerEvent; label: string }[] = [
  { value: "manual", label: "Manual (not auto-sent)" },
  { value: "lead_assigned", label: "Lead assigned" },
  { value: "stage_changed", label: "Deal won / lost" },
  { value: "task_reminder", label: "Task reminder" },
];

const MERGE_FIELDS = "{{first_name}}, {{last_name}}, {{company}}, {{reference_number}}, {{tenant_name}}, {{stage_name}}, {{assigned_user_name}}, {{task_title}}, {{task_due_date}}";

export default function CommunicationsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [triggerEvent, setTriggerEvent] = useState<EmailTriggerEvent>("manual");
  const [stageOutcome, setStageOutcome] = useState<"won" | "lost">("won");
  const [subject, setSubject] = useState("");
  const [bodyText, setBodyText] = useState("");

  const templatesQuery = useQuery({ queryKey: ["tenant", "communications", "templates"], queryFn: () => api.get<EmailTemplate[]>("/tenant/communications/templates") });
  const logsQuery = useQuery({ queryKey: ["tenant", "communications", "logs"], queryFn: () => api.get<EmailDeliveryLog[]>("/tenant/communications/logs") });

  const createTemplate = useMutation({
    mutationFn: () =>
      api.post("/tenant/communications/templates", {
        name, trigger_event: triggerEvent, subject, body_text: bodyText,
        trigger_stage_outcome: triggerEvent === "stage_changed" ? stageOutcome : null,
      }),
    onSuccess: () => {
      setName("");
      setSubject("");
      setBodyText("");
      queryClient.invalidateQueries({ queryKey: ["tenant", "communications", "templates"] });
    },
  });

  const toggleTemplate = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => api.patch(`/tenant/communications/templates/${id}`, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "communications", "templates"] }),
  });

  const sendTest = useMutation({
    mutationFn: (id: string) => api.post(`/tenant/communications/templates/${id}/send-test`),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Communications</h1>
        <p className="mt-1 text-sm text-ink-muted">Email templates sent automatically at each trigger event, plus a delivery log with retries.</p>
      </div>

      <Card>
        <CardHeader title="Add a template" description={`Merge fields available: ${MERGE_FIELDS}`} />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            createTemplate.mutate();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[200px]">
              <Label htmlFor="tpl-name">Name</Label>
              <Input id="tpl-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="min-w-[220px]">
              <Label htmlFor="tpl-trigger">Trigger</Label>
              <select
                id="tpl-trigger"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={triggerEvent}
                onChange={(e) => setTriggerEvent(e.target.value as EmailTriggerEvent)}
              >
                {TRIGGER_EVENTS.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            {triggerEvent === "stage_changed" && (
              <div className="min-w-[140px]">
                <Label htmlFor="tpl-outcome">Outcome</Label>
                <select
                  id="tpl-outcome"
                  className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                  value={stageOutcome}
                  onChange={(e) => setStageOutcome(e.target.value as "won" | "lost")}
                >
                  <option value="won">Won</option>
                  <option value="lost">Lost</option>
                </select>
              </div>
            )}
          </div>
          <div>
            <Label htmlFor="tpl-subject">Subject</Label>
            <Input id="tpl-subject" value={subject} onChange={(e) => setSubject(e.target.value)} required />
          </div>
          <div>
            <Label htmlFor="tpl-body">Body</Label>
            <textarea
              id="tpl-body"
              className="focus-ring min-h-[120px] w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
              value={bodyText}
              onChange={(e) => setBodyText(e.target.value)}
              required
            />
          </div>
          <Button type="submit" disabled={createTemplate.isPending || !name || !subject || !bodyText}>
            {createTemplate.isPending ? "Adding…" : "Add template"}
          </Button>
        </form>
        {createTemplate.isError && (
          <div className="mt-3">
            <Alert tone="error">{createTemplate.error instanceof ApiError ? createTemplate.error.message : "Unable to add template."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Templates" />
        <div className="space-y-2">
          {templatesQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No templates yet — no automated emails will be sent.</p>}
          {templatesQuery.data?.map((template) => (
            <div key={template.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
              <div>
                <p className="font-medium text-ink">{template.name}</p>
                <p className="text-xs text-ink-faint">
                  {TRIGGER_EVENTS.find((t) => t.value === template.trigger_event)?.label}
                  {template.trigger_stage_outcome ? ` (${template.trigger_stage_outcome})` : ""} · {template.subject}
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => sendTest.mutate(template.id)} disabled={sendTest.isPending}>
                  Send test
                </Button>
                <Button variant="secondary" onClick={() => toggleTemplate.mutate({ id: template.id, is_active: !template.is_active })}>
                  {template.is_active ? "Deactivate" : "Activate"}
                </Button>
              </div>
            </div>
          ))}
        </div>
        {sendTest.isSuccess && (
          <div className="mt-3">
            <Alert tone="success">Test email sent to your own address.</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Delivery log" />
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-border text-ink-faint">
              <th className="pb-2 font-medium">Recipient</th>
              <th className="pb-2 font-medium">Subject</th>
              <th className="pb-2 font-medium">Status</th>
              <th className="pb-2 font-medium">Attempts</th>
              <th className="pb-2 font-medium">Sent</th>
            </tr>
          </thead>
          <tbody>
            {logsQuery.data?.map((log) => (
              <tr key={log.id} className="border-b border-surface-border/60">
                <td className="py-2 text-ink">{log.recipient}</td>
                <td className="py-2 text-ink-muted">{log.subject}</td>
                <td className={`py-2 capitalize ${log.status === "failed" ? "text-red-400" : log.status === "sent" ? "text-emerald-400" : "text-ink-muted"}`}>
                  {log.status}
                </td>
                <td className="py-2 text-ink-muted">{log.attempt_count}</td>
                <td className="py-2 text-ink-muted">{log.sent_at ? new Date(log.sent_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {logsQuery.data?.length === 0 && <p className="mt-3 text-sm text-ink-muted">No emails sent yet.</p>}
      </Card>
    </div>
  );
}
