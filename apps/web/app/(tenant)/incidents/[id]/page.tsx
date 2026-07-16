"use client";

import { Alert, Button, Card, CardHeader, SeverityBadge, StatusBadge } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { EvidenceList } from "@/components/EvidenceList";
import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type {
  AssetListItem,
  FindingListItem,
  IncidentActivityRead,
  IncidentDetail,
  MembershipRead,
} from "@/lib/types";

const STATUS_TONE: Record<string, "positive" | "warning" | "neutral"> = {
  declared: "warning",
  investigating: "warning",
  contained: "neutral",
  resolved: "positive",
  closed: "positive",
};

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const incidentId = params.id;
  const { hasPermission } = useAuth();
  const canManage = hasPermission("incidents.manage");
  const canClose = hasPermission("incidents.close");
  const canViewEvidence = hasPermission("evidence.view");
  const canAssignUsers = canManage && hasPermission("users.manage");
  const queryClient = useQueryClient();

  const [actionError, setActionError] = useState<string | null>(null);
  const [isActing, setIsActing] = useState(false);
  const [noteMessage, setNoteMessage] = useState("");
  const [closureSummary, setClosureSummary] = useState("");
  const [selectedFindingId, setSelectedFindingId] = useState("");
  const [selectedAssetId, setSelectedAssetId] = useState("");

  const incidentQuery = useQuery({
    queryKey: ["incidents", incidentId],
    queryFn: () => apiClient.get<IncidentDetail>(`/api/incidents/${incidentId}`),
    enabled: Boolean(incidentId),
  });

  const activityQuery = useQuery({
    queryKey: ["incidents", incidentId, "activity"],
    queryFn: () => apiClient.get<IncidentActivityRead[]>(`/api/incidents/${incidentId}/activity`),
    enabled: Boolean(incidentId),
  });

  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => apiClient.get<MembershipRead[]>("/api/users"),
    enabled: canAssignUsers,
  });

  const findingsQuery = useQuery({
    queryKey: ["findings"],
    queryFn: () => apiClient.get<FindingListItem[]>("/api/findings"),
    enabled: canManage,
  });

  const assetsQuery = useQuery({
    queryKey: ["assets"],
    queryFn: () => apiClient.get<AssetListItem[]>("/api/assets"),
    enabled: canManage,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["incidents", incidentId] });
    queryClient.invalidateQueries({ queryKey: ["incidents", incidentId, "activity"] });
    queryClient.invalidateQueries({ queryKey: ["incidents"] });
  };

  const runAction = async (fn: () => Promise<unknown>) => {
    setActionError(null);
    setIsActing(true);
    try {
      await fn();
      invalidate();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsActing(false);
    }
  };

  const setStatus = (status: string) =>
    runAction(() => apiClient.patch(`/api/incidents/${incidentId}/status`, { status }));

  const addNote = () =>
    runAction(async () => {
      await apiClient.post(`/api/incidents/${incidentId}/notes`, { message: noteMessage });
      setNoteMessage("");
    });

  const close = () =>
    runAction(async () => {
      await apiClient.post(`/api/incidents/${incidentId}/close`, { closure_summary: closureSummary });
      setClosureSummary("");
    });

  const reopen = () => runAction(() => apiClient.post(`/api/incidents/${incidentId}/reopen`));

  const assign = (userId: string) =>
    runAction(() => apiClient.patch(`/api/incidents/${incidentId}`, { assigned_to_user_id: userId }));

  const linkFinding = () =>
    runAction(async () => {
      await apiClient.post(`/api/incidents/${incidentId}/link-finding`, { finding_id: selectedFindingId });
      setSelectedFindingId("");
    });

  const linkAsset = () =>
    runAction(async () => {
      await apiClient.post(`/api/incidents/${incidentId}/link-asset`, { asset_id: selectedAssetId });
      setSelectedAssetId("");
    });

  const incident = incidentQuery.data;
  if (!incident) {
    return <p className="text-sm text-ink-500">Loading…</p>;
  }

  const isOpen = incident.status !== "closed";
  const linkedFindingIds = new Set(incident.findings.map((f) => f.id));
  const linkedAssetIds = new Set(incident.assets.map((a) => a.id));
  const availableFindings = (findingsQuery.data ?? []).filter((f) => !linkedFindingIds.has(f.id));
  const availableAssets = (assetsQuery.data ?? []).filter((a) => !linkedAssetIds.has(a.id));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/incidents" className="text-sm text-ink-500 hover:underline">
            &larr; Incidents
          </Link>
          <h1 className="mt-1 text-xl font-semibold text-ink-900">{incident.title}</h1>
          {incident.description ? <p className="text-sm text-ink-500">{incident.description}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <SeverityBadge severity={incident.severity as "critical" | "high" | "medium" | "low"} />
          <StatusBadge label={incident.status} tone={STATUS_TONE[incident.status] ?? "neutral"} />
        </div>
      </div>

      {actionError ? <Alert tone="error">{actionError}</Alert> : null}

      <Card>
        <CardHeader title="Details" />
        <dl className="grid grid-cols-2 gap-y-2 text-sm">
          <dt className="text-ink-500">Declared</dt>
          <dd className="text-ink-900">{new Date(incident.declared_at).toLocaleString()}</dd>
          <dt className="text-ink-500">Resolved</dt>
          <dd className="text-ink-900">
            {incident.resolved_at ? new Date(incident.resolved_at).toLocaleString() : "Not yet"}
          </dd>
          <dt className="text-ink-500">Closed</dt>
          <dd className="text-ink-900">
            {incident.closed_at ? new Date(incident.closed_at).toLocaleString() : "Not yet"}
          </dd>
          {incident.closure_summary ? (
            <>
              <dt className="text-ink-500">Closure summary</dt>
              <dd className="text-ink-900">{incident.closure_summary}</dd>
            </>
          ) : null}
        </dl>

        {canAssignUsers ? (
          <div className="mt-4 flex items-center gap-2">
            <label htmlFor="assignee" className="text-sm text-ink-500">
              Assigned to
            </label>
            <select
              id="assignee"
              value={incident.assigned_to_user_id ?? ""}
              onChange={(e) => {
                if (e.target.value) assign(e.target.value);
              }}
              className="h-9 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
            >
              <option value="">Unassigned</option>
              {usersQuery.data?.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.full_name} ({u.email})
                </option>
              ))}
            </select>
          </div>
        ) : null}
      </Card>

      {isOpen && canManage ? (
        <Card>
          <CardHeader title="Update status" />
          <div className="flex flex-wrap gap-2">
            {["investigating", "contained", "resolved"].map((status) => (
              <Button
                key={status}
                size="sm"
                variant={incident.status === status ? "primary" : "secondary"}
                isLoading={isActing}
                onClick={() => setStatus(status)}
              >
                {status}
              </Button>
            ))}
          </div>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Linked findings" />
          {incident.findings.length > 0 ? (
            <ul className="flex flex-col gap-1.5 text-sm">
              {incident.findings.map((f) => (
                <li key={f.id} className="flex justify-between border-b border-surface-border/50 pb-1.5">
                  <Link href={`/findings/${f.id}`} className="text-ink-900 hover:underline">
                    {f.title}
                  </Link>
                  <SeverityBadge severity={f.severity as "critical" | "high" | "medium" | "low"} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-500">No findings linked yet.</p>
          )}
          {isOpen && canManage ? (
            <div className="mt-4 flex gap-2">
              <select
                value={selectedFindingId}
                onChange={(e) => setSelectedFindingId(e.target.value)}
                className="h-9 flex-1 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
              >
                <option value="">Link a finding…</option>
                {availableFindings.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.title}
                  </option>
                ))}
              </select>
              <Button size="sm" variant="secondary" disabled={!selectedFindingId} isLoading={isActing} onClick={linkFinding}>
                Link
              </Button>
            </div>
          ) : null}
        </Card>

        <Card>
          <CardHeader title="Linked assets" />
          {incident.assets.length > 0 ? (
            <ul className="flex flex-col gap-1.5 text-sm">
              {incident.assets.map((a) => (
                <li key={a.id} className="flex justify-between border-b border-surface-border/50 pb-1.5">
                  <Link href={`/assets/${a.id}`} className="text-ink-900 hover:underline">
                    {a.display_name}
                  </Link>
                  <span className="text-ink-500">{a.criticality}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-500">No assets linked yet.</p>
          )}
          {isOpen && canManage ? (
            <div className="mt-4 flex gap-2">
              <select
                value={selectedAssetId}
                onChange={(e) => setSelectedAssetId(e.target.value)}
                className="h-9 flex-1 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
              >
                <option value="">Link an asset…</option>
                {availableAssets.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.display_name}
                  </option>
                ))}
              </select>
              <Button size="sm" variant="secondary" disabled={!selectedAssetId} isLoading={isActing} onClick={linkAsset}>
                Link
              </Button>
            </div>
          ) : null}
        </Card>
      </div>

      {isOpen && canManage ? (
        <Card>
          <CardHeader title="Add a note" />
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="What's happening…"
              value={noteMessage}
              onChange={(e) => setNoteMessage(e.target.value)}
              className="h-9 flex-1 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
            />
            <Button size="sm" disabled={!noteMessage.trim()} isLoading={isActing} onClick={addNote}>
              Add note
            </Button>
          </div>
        </Card>
      ) : null}

      {isOpen && canClose ? (
        <Card>
          <CardHeader title="Close incident" />
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Closure summary (required)"
              value={closureSummary}
              onChange={(e) => setClosureSummary(e.target.value)}
              className="h-9 flex-1 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
            />
            <Button
              size="sm"
              variant="secondary"
              disabled={closureSummary.trim().length < 3}
              isLoading={isActing}
              onClick={close}
            >
              Close
            </Button>
          </div>
        </Card>
      ) : null}

      {!isOpen && canManage ? (
        <Card>
          <CardHeader title="Reopen" description="Re-activate this incident if it needs attention again." />
          <Button size="sm" variant="secondary" isLoading={isActing} onClick={reopen}>
            Reopen
          </Button>
        </Card>
      ) : null}

      {canViewEvidence ? (
        <Card>
          <CardHeader title="Evidence" description="Attach documentation, URLs or notes for an audit trail." />
          <EvidenceList targetType="incident" targetId={incidentId} canManage={canManage} />
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Activity" />
        {activityQuery.data && activityQuery.data.length > 0 ? (
          <ul className="flex flex-col gap-2 text-sm">
            {activityQuery.data.map((entry, idx) => (
              <li key={idx} className="flex justify-between border-b border-surface-border/50 pb-2">
                <div>
                  <span className="text-ink-900">{entry.action.replace(/_/g, " ").replace("incidents.", "")}</span>
                  <span className="ml-2 text-ink-500">by {entry.actor_label}</span>
                </div>
                <span className="text-ink-500">{new Date(entry.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-500">No activity recorded yet.</p>
        )}
      </Card>
    </div>
  );
}
