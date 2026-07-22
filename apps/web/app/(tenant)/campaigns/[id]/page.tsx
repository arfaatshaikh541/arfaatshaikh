"use client";

import { Banner, Button, Card } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, api } from "@/lib/api";
import type {
  CampaignDetail,
  CampaignErrorEntry,
  CampaignEvent,
  CampaignProgress,
  ScoreLeadResult,
} from "@/lib/types";

const TERMINAL_STATUSES = new Set(["completed", "partially_completed", "cancelled", "failed"]);
const DELETABLE_STATUSES = new Set(["draft", "estimating", "ready"]);

function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

export default function CampaignDetailPage() {
  const params = useParams<{ id: string }>();
  const campaignId = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [scoreNotice, setScoreNotice] = useState<string | null>(null);

  const campaignQuery = useQuery<CampaignDetail>({
    queryKey: ["campaign", campaignId],
    queryFn: () => api.get<CampaignDetail>(`/campaigns/${campaignId}`),
  });

  const progressQuery = useQuery<CampaignProgress>({
    queryKey: ["campaign", campaignId, "progress"],
    queryFn: () => api.get<CampaignProgress>(`/campaigns/${campaignId}/progress`),
    enabled: !campaignQuery.isError,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && !TERMINAL_STATUSES.has(status) ? 2000 : false;
    },
  });

  // Polls at the same cadence as progress, driven off the same "is this
  // still moving" check - status changes and connector errors happen
  // exactly when progress does, so there's no separate signal to key off.
  const pollWhileActive = () => {
    const currentStatus = progressQuery.data?.status;
    return currentStatus && !TERMINAL_STATUSES.has(currentStatus) ? 2000 : false;
  };

  const eventsQuery = useQuery<CampaignEvent[]>({
    queryKey: ["campaign", campaignId, "events"],
    queryFn: () => api.get<CampaignEvent[]>(`/campaigns/${campaignId}/events`),
    enabled: !campaignQuery.isError,
    refetchInterval: pollWhileActive,
  });

  const errorsQuery = useQuery<CampaignErrorEntry[]>({
    queryKey: ["campaign", campaignId, "errors"],
    queryFn: () => api.get<CampaignErrorEntry[]>(`/campaigns/${campaignId}/errors`),
    enabled: !campaignQuery.isError,
    refetchInterval: pollWhileActive,
  });

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] });
    queryClient.invalidateQueries({ queryKey: ["campaigns"] });
  };

  const runAction = async (action: string, fn: () => Promise<unknown>) => {
    setActionError(null);
    setPendingAction(action);
    try {
      await fn();
      refreshAll();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : `Could not ${action} the campaign.`);
    } finally {
      setPendingAction(null);
    }
  };

  const handleEstimate = () =>
    runAction("estimate", () => api.post(`/campaigns/${campaignId}/estimate`));
  const handleLaunch = () => runAction("launch", () => api.post(`/campaigns/${campaignId}/launch`));
  const handlePause = () => runAction("pause", () => api.post(`/campaigns/${campaignId}/pause`));
  const handleResume = () => runAction("resume", () => api.post(`/campaigns/${campaignId}/resume`));
  const handleCancel = () => runAction("cancel", () => api.post(`/campaigns/${campaignId}/cancel`));
  const handleDelete = () =>
    runAction("delete", async () => {
      await api.delete(`/campaigns/${campaignId}`);
      router.push("/campaigns");
    });

  const handleScoreBusinesses = async () => {
    setActionError(null);
    setScoreNotice(null);
    setPendingAction("score");
    try {
      const results = await api.post<ScoreLeadResult[]>(`/campaigns/${campaignId}/score-businesses`);
      setScoreNotice(
        results.length > 0
          ? `Scored ${results.length} business${results.length === 1 ? "" : "es"} into leads.`
          : "No businesses to score yet.",
      );
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not score businesses.");
    } finally {
      setPendingAction(null);
    }
  };

  if (campaignQuery.isError) {
    return <Banner tone="info">You don&apos;t have permission to view this campaign.</Banner>;
  }

  const campaign = campaignQuery.data;
  const progress = progressQuery.data;
  // `progress` is the actively-polled query, so once it's loaded it is the
  // more current source of truth for status than the one-shot campaign
  // fetch - without this, the page never notices a campaign moving from
  // "queued" to "running" to "completed" after the initial load.
  const status = progress?.status ?? campaign?.status;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{campaign?.name ?? "Campaign"}</h1>
          {campaign && (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {campaign.filter.industry} in {campaign.filter.city}, {campaign.filter.country} via{" "}
              <span className="font-medium">{campaign.source_key}</span> connector
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {status === "draft" && (
            <Button isLoading={pendingAction === "estimate"} onClick={handleEstimate}>
              Estimate
            </Button>
          )}
          {status === "ready" && (
            <Button isLoading={pendingAction === "launch"} onClick={handleLaunch}>
              Launch
            </Button>
          )}
          {(status === "queued" || status === "running") && (
            <>
              <Button variant="secondary" isLoading={pendingAction === "pause"} onClick={handlePause}>
                Pause
              </Button>
              <Button variant="danger" isLoading={pendingAction === "cancel"} onClick={handleCancel}>
                Cancel
              </Button>
            </>
          )}
          {status === "paused" && (
            <>
              <Button isLoading={pendingAction === "resume"} onClick={handleResume}>
                Resume
              </Button>
              <Button variant="danger" isLoading={pendingAction === "cancel"} onClick={handleCancel}>
                Cancel
              </Button>
            </>
          )}
          {(progress?.businesses_found ?? 0) > 0 && (
            <Button
              variant="secondary"
              isLoading={pendingAction === "score"}
              onClick={handleScoreBusinesses}
            >
              Score all businesses
            </Button>
          )}
          {status && DELETABLE_STATUSES.has(status) && (
            <Button variant="ghost" isLoading={pendingAction === "delete"} onClick={handleDelete}>
              Delete
            </Button>
          )}
        </div>
      </div>

      {actionError && <Banner tone="error">{actionError}</Banner>}
      {scoreNotice && <Banner tone="success">{scoreNotice}</Banner>}

      {campaign && (
        <Card>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatBox label="Status" value={status?.replace(/_/g, " ") ?? "—"} />
            <StatBox
              label="Estimated credits"
              value={campaign.estimated_credits !== null ? campaign.estimated_credits : "—"}
            />
            <StatBox label="Result limit" value={campaign.result_limit} />
            <StatBox label="Businesses found" value={progress?.businesses_found ?? 0} />
          </div>
        </Card>
      )}

      {progress && progress.total_tasks > 0 && (
        <Card>
          <h2 className="mb-4 text-lg font-medium">Progress</h2>
          <div className="mb-3 h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
            <div
              className="h-full rounded-full bg-brand-600 transition-all"
              style={{
                width: `${Math.min(
                  100,
                  ((progress.succeeded_tasks + progress.failed_tasks) / progress.total_tasks) * 100,
                )}%`,
              }}
            />
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatBox label="Total pages" value={progress.total_tasks} />
            <StatBox label="Succeeded" value={progress.succeeded_tasks} />
            <StatBox label="Pending" value={progress.pending_tasks} />
            <StatBox label="Failed" value={progress.failed_tasks} />
          </div>
        </Card>
      )}

      {errorsQuery.data && errorsQuery.data.length > 0 && (
        <Card>
          <h2 className="mb-4 text-lg font-medium">Errors</h2>
          <ul className="flex flex-col gap-2">
            {errorsQuery.data.map((error) => (
              <li key={error.id} className="text-sm">
                <span className="font-medium text-red-600 dark:text-red-400">{error.error_type}</span>
                {": "}
                {error.message}
                <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">
                  {new Date(error.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <h2 className="mb-4 text-lg font-medium">History</h2>
        {eventsQuery.data && eventsQuery.data.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {eventsQuery.data.map((event) => (
              <li key={event.id} className="flex items-center justify-between text-sm">
                <span>
                  {event.from_status ? `${event.from_status} → ${event.to_status}` : `${event.to_status}`}
                  {event.message ? ` — ${event.message}` : ""}
                </span>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {new Date(event.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">No history yet.</p>
        )}
      </Card>
    </div>
  );
}
