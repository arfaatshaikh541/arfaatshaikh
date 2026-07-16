"use client";

import { Button, Card, CardHeader, SeverityBadge, StatusBadge } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { ExecutiveSummaryRead } from "@/lib/types";

const SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;

function scoreTone(score: number): "positive" | "warning" | "neutral" {
  if (score >= 80) return "positive";
  if (score >= 50) return "warning";
  return "neutral";
}

function scoreLabel(score: number): string {
  if (score >= 80) return "Strong";
  if (score >= 50) return "Needs attention";
  return "At risk";
}

function ScoreRow({ title, score }: { title: string; score: number }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-48 text-sm text-ink-500">{title}</span>
      <span className="text-2xl font-semibold text-ink-900">{score}</span>
      <span className="text-sm text-ink-500">/ 100</span>
      <StatusBadge label={scoreLabel(score)} tone={scoreTone(score)} />
    </div>
  );
}

export default function ReportsPage() {
  const { hasPermission } = useAuth();
  const canView = hasPermission("reports.view");

  const summaryQuery = useQuery({
    queryKey: ["reports", "executive-summary"],
    queryFn: () => apiClient.get<ExecutiveSummaryRead>("/api/reports/executive-summary"),
    enabled: canView,
  });

  if (!canView) {
    return <p className="text-sm text-ink-500">Not visible to your role.</p>;
  }

  const summary = summaryQuery.data;

  const downloadJson = () => {
    if (!summary) return;
    const blob = new Blob([JSON.stringify(summary, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `gridkeep-executive-summary-${summary.generated_at.slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Executive Report</h1>
          <p className="text-sm text-ink-500">
            One consolidated view of your security posture, synthesized across every module — for
            someone who needs the overall picture, not day-to-day operational access.
          </p>
        </div>
        <Button variant="secondary" disabled={!summary} onClick={downloadJson} className="shrink-0">
          Download JSON
        </Button>
      </div>

      {!summary ? <p className="text-sm text-ink-500">Loading…</p> : null}

      {summary ? (
        <>
          <Card>
            <CardHeader
              title="Overall posture"
              description={`Generated ${new Date(summary.generated_at).toLocaleString()}`}
            />
            <div className="flex flex-col gap-3">
              <ScoreRow title="Security score" score={summary.security_score} />
              {summary.recovery_confidence_score !== null ? (
                <ScoreRow title="Recovery confidence" score={summary.recovery_confidence_score} />
              ) : null}
              {summary.compliance_overall_score !== null ? (
                <ScoreRow title="Compliance" score={summary.compliance_overall_score} />
              ) : null}
            </div>
          </Card>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Card>
              <CardHeader title="Assets" />
              <span className="text-3xl font-semibold text-ink-900">{summary.asset_total}</span>
              <p className="text-sm text-ink-500">discovered assets</p>
            </Card>

            <Card>
              <CardHeader title="Open findings" />
              <span className="text-3xl font-semibold text-ink-900">{summary.open_findings_total}</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {SEVERITY_ORDER.map((severity) => {
                  const count = summary.open_findings_by_severity[severity] ?? 0;
                  if (count === 0) return null;
                  return (
                    <div key={severity} className="flex items-center gap-1 text-sm">
                      <SeverityBadge severity={severity} />
                      <span className="text-ink-700">{count}</span>
                    </div>
                  );
                })}
              </div>
            </Card>

            <Card>
              <CardHeader title="Open incidents" />
              <span className="text-3xl font-semibold text-ink-900">{summary.open_incidents_total}</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {SEVERITY_ORDER.map((severity) => {
                  const count = summary.open_incidents_by_severity[severity] ?? 0;
                  if (count === 0) return null;
                  return (
                    <div key={severity} className="flex items-center gap-1 text-sm">
                      <SeverityBadge severity={severity} />
                      <span className="text-ink-700">{count}</span>
                    </div>
                  );
                })}
              </div>
            </Card>
          </div>

          {summary.compliance_frameworks.length > 0 ? (
            <Card>
              <CardHeader title="Compliance frameworks" />
              <div className="flex flex-col gap-2">
                {summary.compliance_frameworks.map((framework) => (
                  <div key={framework.id} className="flex items-center justify-between border-b border-surface-border/50 pb-2">
                    <span className="text-sm text-ink-900">{framework.name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-ink-700">{framework.score} / 100</span>
                      <StatusBadge label={scoreLabel(framework.score)} tone={scoreTone(framework.score)} />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
