"use client";

import { Banner, Button, Card } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ApiError, api } from "@/lib/api";
import { LEAD_STATUSES, type Business, type LeadDetail, type Member } from "@/lib/types";

function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}

function ScoreBar({ score, max }: { score: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (score / max) * 100) : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
      <div className="h-full rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const leadId = params.id;
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [statusChoice, setStatusChoice] = useState("");
  const [assigneeChoice, setAssigneeChoice] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [tagInput, setTagInput] = useState("");

  const detailQuery = useQuery<LeadDetail>({
    queryKey: ["lead", leadId],
    queryFn: () => api.get<LeadDetail>(`/leads/${leadId}`),
  });

  const businessId = detailQuery.data?.business_id;
  const businessQuery = useQuery<Business>({
    queryKey: ["business", businessId],
    queryFn: () => api.get<Business>(`/businesses/${businessId}`),
    enabled: Boolean(businessId),
  });

  const membersQuery = useQuery<Member[]>({
    queryKey: ["tenant-members"],
    queryFn: () => api.get<Member[]>("/tenants/members"),
    enabled: !detailQuery.isError,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["lead", leadId] });

  const runAction = async (action: string, fn: () => Promise<unknown>) => {
    setActionError(null);
    setPending(action);
    try {
      await fn();
      refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : `Could not ${action}.`);
    } finally {
      setPending(null);
    }
  };

  const handleChangeStatus = () => {
    if (!statusChoice) return;
    runAction("change status", () => api.post(`/leads/${leadId}/status`, { status: statusChoice }));
  };

  const handleAssign = () => {
    if (!assigneeChoice) return;
    runAction("assign", () =>
      api.post(`/leads/${leadId}/assign`, { assigned_to_user_id: assigneeChoice }),
    );
  };

  const handleUnassign = () => runAction("unassign", () => api.post(`/leads/${leadId}/unassign`));

  const handleAddNote = () => {
    if (!noteBody.trim()) return;
    runAction("add note", async () => {
      await api.post(`/leads/${leadId}/notes`, { body: noteBody.trim() });
      setNoteBody("");
    });
  };

  const handleAddTag = () => {
    if (!tagInput.trim()) return;
    runAction("add tag", async () => {
      await api.post(`/leads/${leadId}/tags`, { tag: tagInput.trim() });
      setTagInput("");
    });
  };

  const handleRemoveTag = (tag: string) =>
    runAction("remove tag", () => api.delete(`/leads/${leadId}/tags/${encodeURIComponent(tag)}`));

  if (detailQuery.isError) {
    return <Banner tone="info">You don&apos;t have permission to view this lead.</Banner>;
  }

  const detail = detailQuery.data;
  const membersById = new Map((membersQuery.data ?? []).map((m) => [m.user_id, m]));
  const assignedMember = detail?.lead.assigned_to_user_id
    ? membersById.get(detail.lead.assigned_to_user_id)
    : null;

  const business = businessQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{business?.name ?? "Lead detail"}</h1>
        {business && (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {[business.category, business.city, business.country].filter(Boolean).join(" · ")}
          </p>
        )}
      </div>
      {actionError && <Banner tone="error">{actionError}</Banner>}

      {business && (
        <Card>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatBox label="Phone" value={business.phone ?? "—"} />
            <StatBox label="Email" value={business.email ?? "—"} />
            <StatBox
              label="Website"
              value={business.website ? business.canonical_domain ?? business.website : "—"}
            />
            <StatBox
              label="Rating"
              value={business.rating !== null ? `${business.rating} (${business.review_count ?? 0})` : "—"}
            />
          </div>
          {business.address && (
            <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">{business.address}</p>
          )}
        </Card>
      )}

      {detail && (
        <>
          <Card>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium">Status</h2>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium capitalize dark:bg-slate-800">
                {detail.lead.status.replace(/_/g, " ")}
              </span>
            </div>
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <select
                value={statusChoice}
                onChange={(e) => setStatusChoice(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              >
                <option value="">Change status to…</option>
                {LEAD_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              <Button
                variant="secondary"
                isLoading={pending === "change status"}
                disabled={!statusChoice}
                onClick={handleChangeStatus}
              >
                Update
              </Button>
            </div>
            {detail.status_history.length > 0 && (
              <ul className="mt-4 flex flex-col gap-1 border-t border-slate-200 pt-3 text-sm dark:border-slate-800">
                {detail.status_history.map((h) => (
                  <li key={h.id} className="flex justify-between text-slate-500 dark:text-slate-400">
                    <span>
                      {h.from_status} → {h.to_status}
                    </span>
                    <span>{new Date(h.changed_at).toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <h2 className="text-lg font-medium">Assignment</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {assignedMember ? `Assigned to ${assignedMember.full_name}` : "Unassigned"}
            </p>
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <select
                value={assigneeChoice}
                onChange={(e) => setAssigneeChoice(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              >
                <option value="">Assign to…</option>
                {(membersQuery.data ?? []).map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.full_name} ({m.email})
                  </option>
                ))}
              </select>
              <Button
                variant="secondary"
                isLoading={pending === "assign"}
                disabled={!assigneeChoice}
                onClick={handleAssign}
              >
                Assign
              </Button>
              {detail.lead.assigned_to_user_id && (
                <Button variant="ghost" isLoading={pending === "unassign"} onClick={handleUnassign}>
                  Unassign
                </Button>
              )}
            </div>
            {detail.assignment_history.length > 0 && (
              <ul className="mt-4 flex flex-col gap-1 border-t border-slate-200 pt-3 text-sm dark:border-slate-800">
                {detail.assignment_history.map((a) => (
                  <li key={a.id} className="flex justify-between text-slate-500 dark:text-slate-400">
                    <span>{membersById.get(a.assigned_to_user_id)?.full_name ?? a.assigned_to_user_id}</span>
                    <span>
                      {new Date(a.assigned_at).toLocaleString()}
                      {a.unassigned_at ? ` → ${new Date(a.unassigned_at).toLocaleString()}` : " (current)"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {detail.latest_score && (
            <Card>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-medium">Score breakdown</h2>
                <span className="text-2xl font-semibold">
                  {detail.latest_score.total_score.toFixed(0)}/{detail.latest_score.max_score.toFixed(0)}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Algorithm {detail.latest_score.algorithm_version} — calculated{" "}
                {new Date(detail.latest_score.calculated_at).toLocaleString()}
              </p>
              <div className="mt-4 flex flex-col gap-3">
                {detail.latest_score.factors.map((factor) => (
                  <div key={factor.key}>
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">{factor.label}</span>
                      <span className="text-slate-500 dark:text-slate-400">
                        {factor.score.toFixed(1)}/{factor.max_score.toFixed(0)}
                      </span>
                    </div>
                    <div className="mt-1">
                      <ScoreBar score={factor.score} max={factor.max_score} />
                    </div>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{factor.explanation}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {(detail.opportunities.length > 0 || detail.recommendations.length > 0) && (
            <Card>
              <h2 className="text-lg font-medium">Opportunities &amp; recommendations</h2>
              <div className="mt-3 grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                    Detected opportunities
                  </h3>
                  <ul className="flex flex-col gap-2 text-sm">
                    {detail.opportunities.map((o) => (
                      <li key={o.id} className="rounded-md bg-slate-50 p-2 dark:bg-slate-800/50">
                        <p className="font-medium capitalize">{o.opportunity_type.replace(/_/g, " ")}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          Confidence {(o.confidence * 100).toFixed(0)}%
                        </p>
                      </li>
                    ))}
                    {detail.opportunities.length === 0 && (
                      <p className="text-slate-500 dark:text-slate-400">None detected.</p>
                    )}
                  </ul>
                </div>
                <div>
                  <h3 className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                    Recommended services
                  </h3>
                  <ul className="flex flex-col gap-2 text-sm">
                    {detail.recommendations.map((r) => (
                      <li key={r.id} className="rounded-md bg-slate-50 p-2 dark:bg-slate-800/50">
                        <p className="font-medium capitalize">{r.recommendation_type.replace(/_/g, " ")}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          Confidence {(r.confidence * 100).toFixed(0)}%
                        </p>
                      </li>
                    ))}
                    {detail.recommendations.length === 0 && (
                      <p className="text-slate-500 dark:text-slate-400">None yet.</p>
                    )}
                  </ul>
                </div>
              </div>
            </Card>
          )}

          {detail.duplicate_candidates.length > 0 && (
            <Card>
              <h2 className="text-lg font-medium">Duplicate candidates</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Possible duplicate businesses found for this lead - review from the Businesses API
                until a dedicated review screen exists.
              </p>
              <ul className="mt-3 flex flex-col gap-2 text-sm">
                {detail.duplicate_candidates.map((c) => (
                  <li key={c.id} className="rounded-md bg-slate-50 p-2 dark:bg-slate-800/50">
                    <p className="font-medium capitalize">
                      {c.match_type.replace(/_/g, " ")} match — {c.status}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Confidence {(c.confidence * 100).toFixed(0)}%
                    </p>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card>
            <h2 className="text-lg font-medium">Tags</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {detail.tags.map((tag) => (
                <span
                  key={tag}
                  className="flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                >
                  {tag}
                  <button
                    type="button"
                    aria-label={`Remove tag ${tag}`}
                    onClick={() => handleRemoveTag(tag)}
                    className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-100"
                  >
                    ×
                  </button>
                </span>
              ))}
              {detail.tags.length === 0 && (
                <p className="text-sm text-slate-500 dark:text-slate-400">No tags yet.</p>
              )}
            </div>
            <div className="mt-3 flex gap-2">
              <input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                placeholder="Add a tag"
                className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
              <Button
                variant="secondary"
                isLoading={pending === "add tag"}
                disabled={!tagInput.trim()}
                onClick={handleAddTag}
              >
                Add
              </Button>
            </div>
          </Card>

          <Card>
            <h2 className="text-lg font-medium">Notes</h2>
            <div className="mt-3 flex flex-col gap-2">
              <textarea
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                rows={3}
                placeholder="Add a note about this lead…"
                className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
              <div>
                <Button
                  variant="secondary"
                  isLoading={pending === "add note"}
                  disabled={!noteBody.trim()}
                  onClick={handleAddNote}
                >
                  Add note
                </Button>
              </div>
            </div>
            {detail.notes.length > 0 && (
              <ul className="mt-4 flex flex-col gap-3 border-t border-slate-200 pt-3 dark:border-slate-800">
                {detail.notes.map((n) => (
                  <li key={n.id} className="text-sm">
                    <p>{n.body}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      {new Date(n.created_at).toLocaleString()}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
