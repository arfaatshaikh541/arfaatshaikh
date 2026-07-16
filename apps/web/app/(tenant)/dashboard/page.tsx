"use client";

import { Card, CardHeader, SeverityBadge, StatusBadge } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type {
  EntitlementsRead,
  IncidentSummaryRead,
  ResilienceSummaryRead,
  RiskSummaryRead,
  SubscriptionRead,
  TenantRead,
} from "@/lib/types";

const SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;

function scoreTone(score: number): "positive" | "warning" | "neutral" {
  if (score >= 80) return "positive";
  if (score >= 50) return "warning";
  return "neutral";
}

export default function DashboardPage() {
  const { activeMembership, hasPermission } = useAuth();

  const tenantQuery = useQuery({
    queryKey: ["tenancy", "current"],
    queryFn: () => apiClient.get<TenantRead>("/api/tenancy/current"),
  });

  const entitlementsQuery = useQuery({
    queryKey: ["subscriptions", "entitlements"],
    queryFn: () => apiClient.get<EntitlementsRead>("/api/subscriptions/entitlements"),
    enabled: hasPermission("subscriptions.view"),
  });

  const subscriptionQuery = useQuery({
    queryKey: ["subscriptions", "current"],
    queryFn: () => apiClient.get<SubscriptionRead>("/api/subscriptions/current"),
    enabled: hasPermission("subscriptions.view"),
  });

  const riskSummaryQuery = useQuery({
    queryKey: ["findings", "summary"],
    queryFn: () => apiClient.get<RiskSummaryRead>("/api/findings/summary"),
    enabled: hasPermission("findings.view"),
  });

  const incidentSummaryQuery = useQuery({
    queryKey: ["incidents", "summary"],
    queryFn: () => apiClient.get<IncidentSummaryRead>("/api/incidents/summary"),
    enabled: hasPermission("incidents.view"),
  });

  const resilienceSummaryQuery = useQuery({
    queryKey: ["resilience", "summary"],
    queryFn: () => apiClient.get<ResilienceSummaryRead>("/api/resilience/summary"),
    enabled: hasPermission("assets.view"),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">
          {activeMembership?.tenant_name ?? "Dashboard"}
        </h1>
        <p className="text-sm text-ink-500">Executive overview of your current security posture.</p>
      </div>

      {hasPermission("findings.view") ? (
        <Card>
          <CardHeader
            title="Security score"
            description="100 minus a fixed penalty per open finding, weighted by severity — a simple, explainable
              signal, not a full actuarial risk model."
          />
          {riskSummaryQuery.data ? (
            <div className="flex flex-wrap items-center gap-6">
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-semibold text-ink-900">
                  {riskSummaryQuery.data.security_score}
                </span>
                <span className="text-sm text-ink-500">/ 100</span>
                <StatusBadge
                  label={
                    riskSummaryQuery.data.security_score >= 80
                      ? "Healthy"
                      : riskSummaryQuery.data.security_score >= 50
                        ? "Needs attention"
                        : "At risk"
                  }
                  tone={scoreTone(riskSummaryQuery.data.security_score)}
                />
              </div>
              <div className="flex flex-wrap gap-3">
                {SEVERITY_ORDER.map((severity) => {
                  const count = riskSummaryQuery.data!.open_findings_by_severity[severity] ?? 0;
                  if (count === 0) return null;
                  return (
                    <div key={severity} className="flex items-center gap-1.5 text-sm">
                      <SeverityBadge severity={severity} />
                      <span className="text-ink-700">{count} open</span>
                    </div>
                  );
                })}
                {riskSummaryQuery.data.open_findings_total === 0 ? (
                  <p className="text-sm text-ink-500">No open findings.</p>
                ) : null}
              </div>
              <Link href="/findings" className="text-sm text-accent hover:underline">
                View all findings &rarr;
              </Link>
            </div>
          ) : (
            <p className="text-sm text-ink-500">Loading…</p>
          )}
        </Card>
      ) : null}

      {hasPermission("incidents.view") ? (
        <Card>
          <CardHeader title="Open incidents" />
          {incidentSummaryQuery.data ? (
            <div className="flex flex-wrap items-center gap-6">
              <span className="text-4xl font-semibold text-ink-900">
                {incidentSummaryQuery.data.open_incidents_total}
              </span>
              <div className="flex flex-wrap gap-3">
                {SEVERITY_ORDER.map((severity) => {
                  const count = incidentSummaryQuery.data!.open_incidents_by_severity[severity] ?? 0;
                  if (count === 0) return null;
                  return (
                    <div key={severity} className="flex items-center gap-1.5 text-sm">
                      <SeverityBadge severity={severity} />
                      <span className="text-ink-700">{count} open</span>
                    </div>
                  );
                })}
                {incidentSummaryQuery.data.open_incidents_total === 0 ? (
                  <p className="text-sm text-ink-500">No open incidents.</p>
                ) : null}
              </div>
              <Link href="/incidents" className="text-sm text-accent hover:underline">
                View all incidents &rarr;
              </Link>
            </div>
          ) : (
            <p className="text-sm text-ink-500">Loading…</p>
          )}
        </Card>
      ) : null}

      {hasPermission("assets.view") ? (
        <Card>
          <CardHeader title="Recovery confidence" />
          {resilienceSummaryQuery.data ? (
            resilienceSummaryQuery.data.recovery_confidence_score === null ? (
              <p className="text-sm text-ink-500">No backup jobs discovered yet.</p>
            ) : (
              <div className="flex flex-wrap items-center gap-6">
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-semibold text-ink-900">
                    {resilienceSummaryQuery.data.recovery_confidence_score}
                  </span>
                  <span className="text-sm text-ink-500">/ 100</span>
                  <StatusBadge
                    label={
                      resilienceSummaryQuery.data.recovery_confidence_score >= 80
                        ? "Resilient"
                        : resilienceSummaryQuery.data.recovery_confidence_score >= 50
                          ? "Needs attention"
                          : "At risk"
                    }
                    tone={scoreTone(resilienceSummaryQuery.data.recovery_confidence_score)}
                  />
                </div>
                <span className="text-sm text-ink-700">
                  {resilienceSummaryQuery.data.backup_job_total} backup jobs
                </span>
                <Link href="/resilience" className="text-sm text-accent hover:underline">
                  View resilience &rarr;
                </Link>
              </div>
            )
          ) : (
            <p className="text-sm text-ink-500">Loading…</p>
          )}
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardHeader title="Workspace status" />
          {tenantQuery.data ? (
            <StatusBadge
              label={tenantQuery.data.status}
              tone={tenantQuery.data.status === "active" ? "positive" : "warning"}
            />
          ) : (
            <p className="text-sm text-ink-500">Loading…</p>
          )}
        </Card>

        <Card>
          <CardHeader title="Subscription" />
          {subscriptionQuery.data ? (
            <p className="text-sm text-ink-700">
              {subscriptionQuery.data.plan_name} <span className="text-ink-500">({subscriptionQuery.data.status})</span>
            </p>
          ) : (
            <p className="text-sm text-ink-500">
              {hasPermission("subscriptions.view") ? "Loading…" : "Not visible to your role."}
            </p>
          )}
        </Card>

        <Card>
          <CardHeader title="Entitled modules" />
          {entitlementsQuery.data ? (
            <ul className="flex flex-wrap gap-1.5">
              {entitlementsQuery.data.entitled_modules.map((moduleKey) => (
                <li key={moduleKey}>
                  <StatusBadge label={moduleKey.replace(/_/g, " ")} />
                </li>
              ))}
              {entitlementsQuery.data.entitled_modules.length === 0 ? (
                <p className="text-sm text-ink-500">No modules entitled yet.</p>
              ) : null}
            </ul>
          ) : (
            <p className="text-sm text-ink-500">
              {hasPermission("subscriptions.view") ? "Loading…" : "Not visible to your role."}
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}
