"use client";

import { Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { apiClient } from "@/lib/api-client";
import type { AssetListItem } from "@/lib/types";

const CRITICALITY_TONE: Record<string, "positive" | "warning" | "neutral"> = {
  low: "neutral",
  medium: "warning",
  high: "warning",
  critical: "warning",
};

export default function AssetsPage() {
  const [search, setSearch] = useState("");
  const [assetType, setAssetType] = useState("");
  const [criticality, setCriticality] = useState("");

  const assetsQuery = useQuery({
    queryKey: ["assets", { search, assetType, criticality }],
    queryFn: () =>
      apiClient.get<AssetListItem[]>("/api/assets", {
        ...(search ? { search } : {}),
        ...(assetType ? { asset_type: assetType } : {}),
        ...(criticality ? { criticality } : {}),
      }),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Assets</h1>
        <p className="text-sm text-ink-500">
          Everything discovered from your connected integrations, deduplicated into a single inventory.
        </p>
      </div>

      <Card>
        <div className="flex flex-wrap gap-3">
          <input
            type="search"
            placeholder="Search by name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-10 min-w-[200px] flex-1 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          />
          <select
            value={assetType}
            onChange={(e) => setAssetType(e.target.value)}
            className="h-10 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          >
            <option value="">All types</option>
            <option value="identity_user">Identity user</option>
            <option value="endpoint_device">Endpoint device</option>
            <option value="cloud_account">Cloud account</option>
            <option value="cloud_resource">Cloud resource</option>
            <option value="backup_job">Backup job</option>
          </select>
          <select
            value={criticality}
            onChange={(e) => setCriticality(e.target.value)}
            className="h-10 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          >
            <option value="">All criticalities</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      </Card>

      <Card>
        <CardHeader title={`Inventory${assetsQuery.data ? ` (${assetsQuery.data.length})` : ""}`} />
        {assetsQuery.data && assetsQuery.data.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-ink-500">
                  <th className="py-2 pr-4 font-medium">Name</th>
                  <th className="py-2 pr-4 font-medium">Type</th>
                  <th className="py-2 pr-4 font-medium">Source</th>
                  <th className="py-2 pr-4 font-medium">Criticality</th>
                  <th className="py-2 pr-4 font-medium">Exposure</th>
                  <th className="py-2 pr-4 font-medium">Lifecycle</th>
                  <th className="py-2 font-medium">Last observed</th>
                </tr>
              </thead>
              <tbody>
                {assetsQuery.data.map((asset) => (
                  <tr key={asset.id} className="border-b border-surface-border/50">
                    <td className="py-2 pr-4 text-ink-900">
                      <Link href={`/assets/${asset.id}`} className="hover:underline">
                        {asset.display_name}
                      </Link>
                    </td>
                    <td className="py-2 pr-4 text-ink-500">{asset.asset_type.replace(/_/g, " ")}</td>
                    <td className="py-2 pr-4 text-ink-500">{asset.source}</td>
                    <td className="py-2 pr-4">
                      <StatusBadge
                        label={asset.criticality}
                        tone={CRITICALITY_TONE[asset.criticality] ?? "neutral"}
                      />
                    </td>
                    <td className="py-2 pr-4 text-ink-500">{asset.exposure}</td>
                    <td className="py-2 pr-4 text-ink-500">{asset.lifecycle_status}</td>
                    <td className="py-2 text-ink-500">{new Date(asset.last_observed_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-500">
            No assets yet. Connect an integration and trigger a sync to populate the inventory.
          </p>
        )}
      </Card>
    </div>
  );
}
