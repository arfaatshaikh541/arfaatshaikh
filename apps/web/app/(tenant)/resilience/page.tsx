"use client";

import { Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { ResilienceSummaryRead } from "@/lib/types";

function scoreTone(score: number): "positive" | "warning" | "neutral" {
  if (score >= 80) return "positive";
  if (score >= 50) return "warning";
  return "neutral";
}

export default function ResiliencePage() {
  const { hasPermission } = useAuth();
  const canView = hasPermission("assets.view");

  const summaryQuery = useQuery({
    queryKey: ["resilience", "summary"],
    queryFn: () => apiClient.get<ResilienceSummaryRead>("/api/resilience/summary"),
    enabled: canView,
  });

  if (!canView) {
    return <p className="text-sm text-ink-500">Not visible to your role.</p>;
  }

  const summary = summaryQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Resilience</h1>
        <p className="text-sm text-ink-500">
          Recover confidently: how ready your backups are to survive a ransomware incident.
        </p>
      </div>

      <Card>
        <CardHeader
          title="Recovery Confidence Score"
          description="100 minus a fixed penalty per backup job that didn't succeed, isn't immutable, or
            hasn't run in over 48 hours — averaged across every backup job you have. Not a substitute for
            an actual restore test."
        />
        {summary ? (
          summary.recovery_confidence_score === null ? (
            <p className="text-sm text-ink-500">
              No backup jobs discovered yet. Connect a backup platform integration to get started.
            </p>
          ) : (
            <div className="flex flex-wrap items-center gap-6">
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-semibold text-ink-900">
                  {summary.recovery_confidence_score}
                </span>
                <span className="text-sm text-ink-500">/ 100</span>
                <StatusBadge
                  label={
                    summary.recovery_confidence_score >= 80
                      ? "Resilient"
                      : summary.recovery_confidence_score >= 50
                        ? "Needs attention"
                        : "At risk"
                  }
                  tone={scoreTone(summary.recovery_confidence_score)}
                />
              </div>
              <div className="flex flex-wrap gap-4 text-sm text-ink-700">
                <span>{summary.backup_job_total} backup jobs</span>
                <span>{summary.backup_jobs_immutable} immutable</span>
                <span>{summary.backup_jobs_stale} stale</span>
                <span>{summary.backup_jobs_failed} failed last run</span>
              </div>
            </div>
          )
        ) : (
          <p className="text-sm text-ink-500">Loading…</p>
        )}
      </Card>

      {summary && summary.jobs.length > 0 ? (
        <Card>
          <CardHeader title="Backup jobs" />
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-ink-500">
                  <th className="py-2 pr-4 font-medium">Job</th>
                  <th className="py-2 pr-4 font-medium">Last run</th>
                  <th className="py-2 pr-4 font-medium">Immutable</th>
                  <th className="py-2 pr-4 font-medium">Freshness</th>
                  <th className="py-2 font-medium">Score</th>
                </tr>
              </thead>
              <tbody>
                {summary.jobs.map((job) => (
                  <tr key={job.asset_id} className="border-b border-surface-border/50">
                    <td className="py-2 pr-4 text-ink-900">{job.job_name}</td>
                    <td className="py-2 pr-4">
                      <StatusBadge
                        label={job.last_run_status ?? "unknown"}
                        tone={job.last_run_status === "success" ? "positive" : "warning"}
                      />
                    </td>
                    <td className="py-2 pr-4">
                      <StatusBadge
                        label={job.immutable ? "Immutable" : "Not immutable"}
                        tone={job.immutable ? "positive" : "warning"}
                      />
                    </td>
                    <td className="py-2 pr-4">
                      <StatusBadge label={job.is_stale ? "Stale" : "Fresh"} tone={job.is_stale ? "warning" : "positive"} />
                    </td>
                    <td className="py-2 text-ink-700">{job.score} / 100</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
