"use client";

import { Alert, Button, Card, CardHeader, SeverityBadge, StatusBadge } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { FindingActivityRead, FindingDetail, MembershipRead } from "@/lib/types";

const STATUS_TONE: Record<string, "positive" | "warning" | "neutral"> = {
  open: "warning",
  assigned: "warning",
  remediated: "positive",
  resolved: "positive",
  accepted_risk: "neutral",
  false_positive: "neutral",
};

export default function FindingDetailPage() {
  const params = useParams<{ id: string }>();
  const findingId = params.id;
  const { hasPermission, me } = useAuth();
  const canAssign = hasPermission("findings.assign");
  const canAcceptRisk = hasPermission("findings.accept_risk");
  const canRemediate = hasPermission("findings.remediate");
  const canAssignUsers = canAssign && hasPermission("users.manage");
  const queryClient = useQueryClient();

  const [actionError, setActionError] = useState<string | null>(null);
  const [isActing, setIsActing] = useState(false);
  const [selectedAssignee, setSelectedAssignee] = useState("");
  const [acceptRiskReason, setAcceptRiskReason] = useState("");
  const [acceptRiskExpiresAt, setAcceptRiskExpiresAt] = useState("");
  const [remediateNote, setRemediateNote] = useState("");
  const [dismissReason, setDismissReason] = useState("");

  const findingQuery = useQuery({
    queryKey: ["findings", findingId],
    queryFn: () => apiClient.get<FindingDetail>(`/api/findings/${findingId}`),
    enabled: Boolean(findingId),
  });

  const activityQuery = useQuery({
    queryKey: ["findings", findingId, "activity"],
    queryFn: () => apiClient.get<FindingActivityRead[]>(`/api/findings/${findingId}/activity`),
    enabled: Boolean(findingId),
  });

  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => apiClient.get<MembershipRead[]>("/api/users"),
    enabled: canAssignUsers,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["findings", findingId] });
    queryClient.invalidateQueries({ queryKey: ["findings", findingId, "activity"] });
    queryClient.invalidateQueries({ queryKey: ["findings"] });
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

  const assignTo = (userId: string) =>
    runAction(() => apiClient.post(`/api/findings/${findingId}/assign`, { user_id: userId }));

  const acceptRisk = () =>
    runAction(() =>
      apiClient.post(`/api/findings/${findingId}/accept-risk`, {
        reason: acceptRiskReason,
        expires_at: acceptRiskExpiresAt ? new Date(acceptRiskExpiresAt).toISOString() : null,
      }),
    );

  const remediate = () =>
    runAction(() =>
      apiClient.post(`/api/findings/${findingId}/remediate`, { note: remediateNote || null }),
    );

  const dismiss = () =>
    runAction(() => apiClient.post(`/api/findings/${findingId}/dismiss`, { reason: dismissReason }));

  const reopen = () => runAction(() => apiClient.post(`/api/findings/${findingId}/reopen`));

  const finding = findingQuery.data;
  if (!finding) {
    return <p className="text-sm text-ink-500">Loading…</p>;
  }

  const isOpenOrAssigned = finding.status === "open" || finding.status === "assigned";
  const isClosed = ["remediated", "resolved", "accepted_risk", "false_positive"].includes(finding.status);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/findings" className="text-sm text-ink-500 hover:underline">
            &larr; Findings
          </Link>
          <h1 className="mt-1 text-xl font-semibold text-ink-900">{finding.title}</h1>
          <p className="text-sm text-ink-500">
            Affects{" "}
            <Link href={`/assets/${finding.asset_id}`} className="hover:underline">
              {finding.asset_display_name}
            </Link>{" "}
            ({finding.asset_criticality} criticality)
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <SeverityBadge severity={finding.severity as "critical" | "high" | "medium" | "low"} />
          <StatusBadge
            label={finding.status.replace(/_/g, " ")}
            tone={STATUS_TONE[finding.status] ?? "neutral"}
          />
        </div>
      </div>

      {actionError ? <Alert tone="error">{actionError}</Alert> : null}

      <Card>
        <CardHeader title="Description" />
        <p className="text-sm text-ink-700">{finding.description}</p>
        <dl className="mt-4 grid grid-cols-2 gap-y-2 text-sm">
          <dt className="text-ink-500">Risk score</dt>
          <dd className="text-ink-900">{finding.risk_score} / 100</dd>
          <dt className="text-ink-500">First observed</dt>
          <dd className="text-ink-900">{new Date(finding.first_observed_at).toLocaleString()}</dd>
          <dt className="text-ink-500">Last observed</dt>
          <dd className="text-ink-900">{new Date(finding.last_observed_at).toLocaleString()}</dd>
          {finding.resolution_note ? (
            <>
              <dt className="text-ink-500">Resolution note</dt>
              <dd className="text-ink-900">{finding.resolution_note}</dd>
            </>
          ) : null}
          {finding.accepted_risk_expires_at ? (
            <>
              <dt className="text-ink-500">Accepted risk expires</dt>
              <dd className="text-ink-900">{new Date(finding.accepted_risk_expires_at).toLocaleString()}</dd>
            </>
          ) : null}
        </dl>
      </Card>

      <Card>
        <CardHeader title="Evidence" />
        <pre className="overflow-x-auto rounded bg-surface-800 p-3 text-xs text-ink-700">
          {JSON.stringify(finding.evidence, null, 2)}
        </pre>
      </Card>

      {isOpenOrAssigned && (canAssign || canAcceptRisk || canRemediate) ? (
        <Card>
          <CardHeader title="Take action" />
          <div className="flex flex-col gap-6">
            {canAssign ? (
              <div className="flex flex-col gap-2">
                <p className="text-sm font-medium text-ink-700">Assign</p>
                <div className="flex flex-wrap gap-2">
                  {me ? (
                    <Button size="sm" variant="secondary" onClick={() => assignTo(me.user.id)} isLoading={isActing}>
                      Assign to me
                    </Button>
                  ) : null}
                  {canAssignUsers ? (
                    <>
                      <select
                        value={selectedAssignee}
                        onChange={(e) => setSelectedAssignee(e.target.value)}
                        className="h-9 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
                      >
                        <option value="">Assign to teammate…</option>
                        {usersQuery.data?.map((u) => (
                          <option key={u.user_id} value={u.user_id}>
                            {u.full_name} ({u.email})
                          </option>
                        ))}
                      </select>
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={!selectedAssignee}
                        isLoading={isActing}
                        onClick={() => assignTo(selectedAssignee)}
                      >
                        Assign
                      </Button>
                    </>
                  ) : null}
                </div>
              </div>
            ) : null}

            {canRemediate ? (
              <div className="flex flex-col gap-2">
                <p className="text-sm font-medium text-ink-700">Mark remediated</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Remediation note (optional)"
                    value={remediateNote}
                    onChange={(e) => setRemediateNote(e.target.value)}
                    className="h-9 flex-1 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
                  />
                  <Button size="sm" isLoading={isActing} onClick={remediate}>
                    Remediate
                  </Button>
                </div>
              </div>
            ) : null}

            {canAcceptRisk ? (
              <div className="flex flex-col gap-2">
                <p className="text-sm font-medium text-ink-700">Accept risk</p>
                <input
                  type="text"
                  placeholder="Reason (required)"
                  value={acceptRiskReason}
                  onChange={(e) => setAcceptRiskReason(e.target.value)}
                  className="h-9 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
                />
                <div className="flex items-center gap-2">
                  <label htmlFor="expires-at" className="text-sm text-ink-500">
                    Expires (optional)
                  </label>
                  <input
                    id="expires-at"
                    type="date"
                    value={acceptRiskExpiresAt}
                    onChange={(e) => setAcceptRiskExpiresAt(e.target.value)}
                    className="h-9 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
                  />
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={acceptRiskReason.trim().length < 3}
                    isLoading={isActing}
                    onClick={acceptRisk}
                  >
                    Accept risk
                  </Button>
                </div>
              </div>
            ) : null}

            {canRemediate ? (
              <div className="flex flex-col gap-2">
                <p className="text-sm font-medium text-ink-700">Dismiss as false positive</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Reason (required)"
                    value={dismissReason}
                    onChange={(e) => setDismissReason(e.target.value)}
                    className="h-9 flex-1 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={dismissReason.trim().length < 3}
                    isLoading={isActing}
                    onClick={dismiss}
                  >
                    Dismiss
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </Card>
      ) : null}

      {isClosed && canAssign ? (
        <Card>
          <CardHeader title="Reopen" description="Re-activate this finding if it needs attention again." />
          <Button size="sm" variant="secondary" isLoading={isActing} onClick={reopen}>
            Reopen
          </Button>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Activity" />
        {activityQuery.data && activityQuery.data.length > 0 ? (
          <ul className="flex flex-col gap-2 text-sm">
            {activityQuery.data.map((entry, idx) => (
              <li key={idx} className="flex justify-between border-b border-surface-border/50 pb-2">
                <div>
                  <span className="text-ink-900">{entry.action.replace(/_/g, " ").replace("findings.", "")}</span>
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
