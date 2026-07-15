"use client";

import { Alert, Button, Card, CardHeader, SeverityBadge, StatusBadge } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { FindingListItem } from "@/lib/types";

const STATUS_TONE: Record<string, "positive" | "warning" | "neutral"> = {
  open: "warning",
  assigned: "warning",
  remediated: "positive",
  resolved: "positive",
  accepted_risk: "neutral",
  false_positive: "neutral",
};

export default function FindingsPage() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const canTriggerCorrelation = hasPermission("findings.remediate");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [isCorrelating, setIsCorrelating] = useState(false);

  const findingsQuery = useQuery({
    queryKey: ["findings", { severity, status, search }],
    queryFn: () =>
      apiClient.get<FindingListItem[]>("/api/findings", {
        ...(severity ? { severity } : {}),
        ...(status ? { status } : {}),
        ...(search ? { search } : {}),
      }),
  });

  const runCorrelation = async () => {
    setActionError(null);
    setActionNotice(null);
    setIsCorrelating(true);
    try {
      await apiClient.post("/api/findings/correlate");
      setActionNotice("Correlation started — new and updated findings will appear shortly.");
      queryClient.invalidateQueries({ queryKey: ["findings"] });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsCorrelating(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Findings</h1>
          <p className="text-sm text-ink-500">
            Issues detected by correlating your asset graph against known risk patterns — administrator
            accounts without MFA, unencrypted or unresponsive devices, exposed cloud storage, and failed
            backups.
          </p>
        </div>
        {canTriggerCorrelation ? (
          <Button variant="secondary" onClick={runCorrelation} isLoading={isCorrelating} className="shrink-0">
            Run correlation now
          </Button>
        ) : null}
      </div>

      {actionError ? <Alert tone="error">{actionError}</Alert> : null}
      {actionNotice ? <Alert tone="success">{actionNotice}</Alert> : null}

      <Card>
        <div className="flex flex-wrap gap-3">
          <input
            type="search"
            placeholder="Search by title…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-10 min-w-[200px] flex-1 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          />
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="h-10 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          >
            <option value="">All severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-10 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="assigned">Assigned</option>
            <option value="remediated">Remediated</option>
            <option value="resolved">Resolved</option>
            <option value="accepted_risk">Accepted risk</option>
            <option value="false_positive">False positive</option>
          </select>
        </div>
      </Card>

      <Card>
        <CardHeader title={`Findings${findingsQuery.data ? ` (${findingsQuery.data.length})` : ""}`} />
        {findingsQuery.data && findingsQuery.data.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-ink-500">
                  <th className="py-2 pr-4 font-medium">Finding</th>
                  <th className="py-2 pr-4 font-medium">Severity</th>
                  <th className="py-2 pr-4 font-medium">Asset</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium">Risk score</th>
                  <th className="py-2 font-medium">Last observed</th>
                </tr>
              </thead>
              <tbody>
                {findingsQuery.data.map((finding) => (
                  <tr key={finding.id} className="border-b border-surface-border/50">
                    <td className="py-2 pr-4 text-ink-900">
                      <Link href={`/findings/${finding.id}`} className="hover:underline">
                        {finding.title}
                      </Link>
                    </td>
                    <td className="py-2 pr-4">
                      <SeverityBadge severity={finding.severity as "critical" | "high" | "medium" | "low"} />
                    </td>
                    <td className="py-2 pr-4 text-ink-500">
                      <Link href={`/assets/${finding.asset_id}`} className="hover:underline">
                        {finding.asset_display_name}
                      </Link>
                    </td>
                    <td className="py-2 pr-4">
                      <StatusBadge
                        label={finding.status.replace(/_/g, " ")}
                        tone={STATUS_TONE[finding.status] ?? "neutral"}
                      />
                    </td>
                    <td className="py-2 pr-4 text-ink-500">{finding.risk_score}</td>
                    <td className="py-2 text-ink-500">{new Date(finding.last_observed_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-500">
            No findings yet. Connect an integration and sync it, or run correlation manually above.
          </p>
        )}
      </Card>
    </div>
  );
}
