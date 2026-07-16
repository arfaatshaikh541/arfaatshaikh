"use client";

import { Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { IndicatorRead } from "@/lib/types";

function confidenceTone(confidence: number): "positive" | "warning" | "neutral" {
  return confidence >= 0.4 ? "warning" : "neutral";
}

export default function ThreatIntelPage() {
  const { hasPermission } = useAuth();
  const canView = hasPermission("findings.view");

  const indicatorsQuery = useQuery({
    queryKey: ["threat-intel", "indicators"],
    queryFn: () => apiClient.get<IndicatorRead[]>("/api/threat-intel/indicators"),
    enabled: canView,
  });

  if (!canView) {
    return <p className="text-sm text-ink-500">Not visible to your role.</p>;
  }

  const indicators = indicatorsQuery.data ?? [];
  const matchedCount = indicators.filter((i) => i.matches.length > 0).length;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Threat Intelligence</h1>
        <p className="text-sm text-ink-500">
          Indicators of compromise from connected threat feeds, cross-referenced against your asset
          graph. A match creates a finding automatically.
        </p>
      </div>

      <Card>
        <CardHeader title={`Indicators (${indicators.length})`} description={`${matchedCount} matched an asset`} />
        {indicators.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-ink-500">
                  <th className="py-2 pr-4 font-medium">Value</th>
                  <th className="py-2 pr-4 font-medium">Type</th>
                  <th className="py-2 pr-4 font-medium">Confidence</th>
                  <th className="py-2 pr-4 font-medium">Source</th>
                  <th className="py-2 pr-4 font-medium">Matched assets</th>
                  <th className="py-2 font-medium">Last seen</th>
                </tr>
              </thead>
              <tbody>
                {indicators.map((indicator) => (
                  <tr key={indicator.id} className="border-b border-surface-border/50">
                    <td className="py-2 pr-4 text-ink-900">{indicator.value}</td>
                    <td className="py-2 pr-4 text-ink-500">{indicator.indicator_type}</td>
                    <td className="py-2 pr-4">
                      <StatusBadge
                        label={indicator.confidence.toFixed(2)}
                        tone={confidenceTone(indicator.confidence)}
                      />
                    </td>
                    <td className="py-2 pr-4 text-ink-500">{indicator.source}</td>
                    <td className="py-2 pr-4">
                      {indicator.matches.length > 0 ? (
                        <div className="flex flex-col gap-1">
                          {indicator.matches.map((match) => (
                            <Link
                              key={match.finding_id}
                              href={`/findings/${match.finding_id}`}
                              className="text-accent hover:underline"
                            >
                              {match.asset_display_name}
                            </Link>
                          ))}
                        </div>
                      ) : (
                        <span className="text-ink-500">No matches</span>
                      )}
                    </td>
                    <td className="py-2 text-ink-500">{new Date(indicator.last_seen_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-500">No threat-intelligence indicators yet.</p>
        )}
      </Card>
    </div>
  );
}
