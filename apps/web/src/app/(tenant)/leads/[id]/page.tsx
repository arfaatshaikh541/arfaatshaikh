"use client";

import { Alert, Badge, Button, Card } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { apiFetch } from "@/lib/api-client";
import {
  PRIORITY_LABELS,
  PRIORITY_TONES,
  type LeadDetailOut,
  type LeadNoteOut,
  type LossReasonOut,
  type MemberOut,
  type PipelineStageOut,
  type TagOut,
  type TimelineEntryOut,
} from "@/lib/types";

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const leadId = params.id;
  const { tenantId, membership } = useCurrentTenant();
  const queryClient = useQueryClient();
  const canManageUsers = membership?.role.permissions.some((p) => p.code === "users.manage") ?? false;
  const [noteBody, setNoteBody] = useState("");
  const [pendingLostStage, setPendingLostStage] = useState<string | null>(null);
  const [lossReasonId, setLossReasonId] = useState("");
  const [selectedTagId, setSelectedTagId] = useState("");

  const leadQuery = useQuery({
    queryKey: ["lead", leadId],
    queryFn: () => apiFetch<LeadDetailOut>(`/tenants/me/leads/${leadId}`),
    enabled: Boolean(tenantId && leadId),
  });
  const stagesQuery = useQuery({
    queryKey: ["pipeline-stages", tenantId],
    queryFn: () => apiFetch<PipelineStageOut[]>("/tenants/me/pipeline-stages"),
    enabled: Boolean(tenantId),
  });
  const tagsQuery = useQuery({
    queryKey: ["tags", tenantId],
    queryFn: () => apiFetch<TagOut[]>("/tenants/me/tags"),
    enabled: Boolean(tenantId),
  });
  const lossReasonsQuery = useQuery({
    queryKey: ["loss-reasons", tenantId],
    queryFn: () => apiFetch<LossReasonOut[]>("/tenants/me/loss-reasons"),
    enabled: Boolean(tenantId),
  });
  const membersQuery = useQuery({
    queryKey: ["members", tenantId],
    queryFn: () => apiFetch<MemberOut[]>("/tenants/me/members"),
    enabled: Boolean(tenantId) && canManageUsers,
  });
  const notesQuery = useQuery({
    queryKey: ["lead-notes", leadId],
    queryFn: () => apiFetch<LeadNoteOut[]>(`/tenants/me/leads/${leadId}/notes`),
    enabled: Boolean(tenantId && leadId),
  });
  const timelineQuery = useQuery({
    queryKey: ["lead-timeline", leadId],
    queryFn: () => apiFetch<TimelineEntryOut[]>(`/tenants/me/leads/${leadId}/timeline`),
    enabled: Boolean(tenantId && leadId),
  });

  const invalidateLead = () => {
    queryClient.invalidateQueries({ queryKey: ["lead", leadId] });
    queryClient.invalidateQueries({ queryKey: ["lead-timeline", leadId] });
  };

  const stageMutation = useMutation({
    mutationFn: (body: { to_stage_id: string; loss_reason_id?: string }) =>
      apiFetch(`/tenants/me/leads/${leadId}/stage`, { method: "POST", body }),
    onSuccess: () => {
      invalidateLead();
      setPendingLostStage(null);
      setLossReasonId("");
    },
  });

  const assignMutation = useMutation({
    mutationFn: (membership_id: string | null) =>
      apiFetch(`/tenants/me/leads/${leadId}/assign`, { method: "POST", body: { membership_id } }),
    onSuccess: invalidateLead,
  });

  const noteMutation = useMutation({
    mutationFn: (body: string) =>
      apiFetch(`/tenants/me/leads/${leadId}/notes`, { method: "POST", body: { body } }),
    onSuccess: () => {
      setNoteBody("");
      queryClient.invalidateQueries({ queryKey: ["lead-notes", leadId] });
      invalidateLead();
    },
  });

  const addTagMutation = useMutation({
    mutationFn: (tag_id: string) =>
      apiFetch(`/tenants/me/leads/${leadId}/tags`, { method: "POST", body: { tag_id } }),
    onSuccess: () => {
      setSelectedTagId("");
      invalidateLead();
    },
  });

  const removeTagMutation = useMutation({
    mutationFn: (tagId: string) =>
      apiFetch(`/tenants/me/leads/${leadId}/tags/${tagId}`, { method: "DELETE" }),
    onSuccess: invalidateLead,
  });

  if (leadQuery.isLoading || !leadQuery.data) {
    return <p className="text-sm text-surface-400">Loading…</p>;
  }
  const lead = leadQuery.data;
  const currentStage = stagesQuery.data?.find((s) => s.id === lead.stage_id);

  const handleStageChange = (toStageId: string) => {
    const stage = stagesQuery.data?.find((s) => s.id === toStageId);
    if (stage?.is_lost) {
      setPendingLostStage(toStageId);
      return;
    }
    stageMutation.mutate({ to_stage_id: toStageId });
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-6">
        <Card>
          <div className="mb-4 flex items-start justify-between">
            <div>
              <h1 className="text-xl font-semibold text-surface-50">
                {lead.first_name} {lead.last_name}
              </h1>
              <p className="text-sm text-surface-500">{lead.reference_number}</p>
            </div>
            <Badge tone={PRIORITY_TONES[lead.priority] ?? "neutral"}>
              {PRIORITY_LABELS[lead.priority] ?? lead.priority}
            </Badge>
          </div>
          {lead.is_possible_duplicate ? (
            <Alert tone="info" className="mb-4">
              This lead shares contact details with a recent submission and may be a duplicate.
            </Alert>
          ) : null}
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-surface-500">Email</dt>
              <dd className="text-surface-200">{lead.email ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-surface-500">Phone</dt>
              <dd className="text-surface-200">{lead.phone ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-surface-500">Company</dt>
              <dd className="text-surface-200">{lead.company ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-surface-500">Source</dt>
              <dd className="text-surface-200">{lead.source}</dd>
            </div>
            <div>
              <dt className="text-surface-500">Estimated value</dt>
              <dd className="text-surface-200">
                {lead.estimated_value ? `AED ${lead.estimated_value}` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-surface-500">Consent</dt>
              <dd className="text-surface-200">{lead.consent_given ? "Given" : "Not given"}</dd>
            </div>
          </dl>
        </Card>

        {lead.answers.length > 0 ? (
          <Card>
            <h2 className="mb-3 text-sm font-semibold text-surface-100">Qualification answers</h2>
            <dl className="space-y-2 text-sm">
              {lead.answers.map((answer) => (
                <div key={answer.id}>
                  <dt className="text-surface-500">{answer.question_label_snapshot}</dt>
                  <dd className="text-surface-200">{String(answer.value)}</dd>
                </div>
              ))}
            </dl>
          </Card>
        ) : null}

        <Card>
          <h2 className="mb-3 text-sm font-semibold text-surface-100">Notes</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (noteBody.trim()) noteMutation.mutate(noteBody.trim());
            }}
            className="mb-4 flex gap-2"
          >
            <textarea
              className="flex-1 rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
              rows={2}
              value={noteBody}
              onChange={(e) => setNoteBody(e.target.value)}
              placeholder="Add a note…"
            />
            <Button type="submit" loading={noteMutation.isPending}>
              Add
            </Button>
          </form>
          <div className="space-y-3">
            {notesQuery.data?.map((note) => (
              <div key={note.id} className="border-b border-surface-900 pb-2 text-sm">
                <p className="text-surface-200">{note.body}</p>
                <p className="text-xs text-surface-500">
                  {new Date(note.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold text-surface-100">Activity timeline</h2>
          <div className="space-y-2">
            {timelineQuery.data?.map((entry) => (
              <div key={entry.id} className="flex items-center justify-between text-sm">
                <span className="text-surface-300">{entry.event_type}</span>
                <span className="text-xs text-surface-500">
                  {new Date(entry.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="space-y-6">
        <Card>
          <h2 className="mb-3 text-sm font-semibold text-surface-100">Stage</h2>
          <select
            className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
            value={lead.stage_id}
            onChange={(e) => handleStageChange(e.target.value)}
          >
            {stagesQuery.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <p className="mt-2 text-xs text-surface-500">Current: {currentStage?.name}</p>
          {pendingLostStage ? (
            <div className="mt-3 space-y-2 rounded-md border border-surface-700 p-3">
              <p className="text-xs text-surface-400">A loss reason is required.</p>
              <select
                className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                value={lossReasonId}
                onChange={(e) => setLossReasonId(e.target.value)}
              >
                <option value="">Select a reason…</option>
                {lossReasonsQuery.data?.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
              <Button
                disabled={!lossReasonId}
                loading={stageMutation.isPending}
                onClick={() =>
                  stageMutation.mutate({ to_stage_id: pendingLostStage, loss_reason_id: lossReasonId })
                }
              >
                Confirm
              </Button>
            </div>
          ) : null}
        </Card>

        {canManageUsers ? (
          <Card>
            <h2 className="mb-3 text-sm font-semibold text-surface-100">Assigned to</h2>
            <select
              className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
              value={lead.assigned_membership_id ?? ""}
              onChange={(e) => assignMutation.mutate(e.target.value || null)}
            >
              <option value="">Unassigned</option>
              {membersQuery.data?.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.first_name} {m.last_name}
                </option>
              ))}
            </select>
          </Card>
        ) : null}

        <Card>
          <h2 className="mb-3 text-sm font-semibold text-surface-100">Tags</h2>
          <div className="mb-3 flex flex-wrap gap-2">
            {lead.tag_ids.map((tagId) => {
              const tag = tagsQuery.data?.find((t) => t.id === tagId);
              if (!tag) return null;
              return (
                <span
                  key={tagId}
                  className="inline-flex items-center gap-1 rounded-full bg-surface-800 px-2 py-0.5 text-xs text-surface-200"
                >
                  {tag.name}
                  <button
                    type="button"
                    className="text-surface-500 hover:text-surface-300"
                    onClick={() => removeTagMutation.mutate(tagId)}
                    aria-label={`Remove ${tag.name}`}
                  >
                    ×
                  </button>
                </span>
              );
            })}
          </div>
          <div className="flex gap-2">
            <select
              className="flex-1 rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
              value={selectedTagId}
              onChange={(e) => setSelectedTagId(e.target.value)}
            >
              <option value="">Add a tag…</option>
              {tagsQuery.data
                ?.filter((t) => !lead.tag_ids.includes(t.id))
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
            </select>
            <Button
              variant="secondary"
              disabled={!selectedTagId}
              onClick={() => addTagMutation.mutate(selectedTagId)}
            >
              Add
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
