"use client";

import { Alert, Button, Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { AssetChangeRead, AssetDetail, MembershipRead } from "@/lib/types";

const CRITICALITY_TONE: Record<string, "positive" | "warning" | "neutral"> = {
  low: "neutral",
  medium: "warning",
  high: "warning",
  critical: "warning",
};

const CRITICALITY_OPTIONS = ["low", "medium", "high", "critical"];

export default function AssetDetailPage() {
  const params = useParams<{ id: string }>();
  const assetId = params.id;
  const { hasPermission } = useAuth();
  const canManage = hasPermission("assets.manage");
  const canAssignOwners = canManage && hasPermission("users.manage");
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [isUpdatingCriticality, setIsUpdatingCriticality] = useState(false);
  const [selectedOwnerId, setSelectedOwnerId] = useState("");
  const [isAssigningOwner, setIsAssigningOwner] = useState(false);

  const assetQuery = useQuery({
    queryKey: ["assets", assetId],
    queryFn: () => apiClient.get<AssetDetail>(`/api/assets/${assetId}`),
    enabled: Boolean(assetId),
  });

  const changesQuery = useQuery({
    queryKey: ["assets", assetId, "changes"],
    queryFn: () => apiClient.get<AssetChangeRead[]>(`/api/assets/${assetId}/changes`),
    enabled: Boolean(assetId),
  });

  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => apiClient.get<MembershipRead[]>("/api/users"),
    enabled: canAssignOwners,
  });

  const asset = assetQuery.data;

  const setCriticality = async (criticality: string) => {
    setActionError(null);
    setIsUpdatingCriticality(true);
    try {
      await apiClient.patch(`/api/assets/${assetId}/criticality`, { criticality });
      queryClient.invalidateQueries({ queryKey: ["assets", assetId] });
      queryClient.invalidateQueries({ queryKey: ["assets"] });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsUpdatingCriticality(false);
    }
  };

  const assignOwner = async () => {
    if (!selectedOwnerId) return;
    setActionError(null);
    setIsAssigningOwner(true);
    try {
      await apiClient.post(`/api/assets/${assetId}/owners`, { user_id: selectedOwnerId });
      setSelectedOwnerId("");
      queryClient.invalidateQueries({ queryKey: ["assets", assetId] });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsAssigningOwner(false);
    }
  };

  if (!asset) {
    return <p className="text-sm text-ink-500">Loading…</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <Link href="/assets" className="text-sm text-ink-500 hover:underline">
            &larr; Assets
          </Link>
          <h1 className="mt-1 text-xl font-semibold text-ink-900">{asset.display_name}</h1>
          <p className="text-sm text-ink-500">
            {asset.asset_type.replace(/_/g, " ")} · via {asset.source}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge label={asset.lifecycle_status} />
          <StatusBadge label={asset.criticality} tone={CRITICALITY_TONE[asset.criticality] ?? "neutral"} />
        </div>
      </div>

      {actionError ? <Alert tone="error">{actionError}</Alert> : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Overview" />
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-ink-500">Exposure</dt>
            <dd className="text-ink-900">{asset.exposure}</dd>
            <dt className="text-ink-500">Confidence</dt>
            <dd className="text-ink-900">{Math.round(asset.confidence * 100)}%</dd>
            <dt className="text-ink-500">Last observed</dt>
            <dd className="text-ink-900">{new Date(asset.last_observed_at).toLocaleString()}</dd>
            <dt className="text-ink-500">Last assessed</dt>
            <dd className="text-ink-900">
              {asset.last_assessed_at ? new Date(asset.last_assessed_at).toLocaleString() : "Never"}
            </dd>
          </dl>

          {canManage ? (
            <div className="mt-4 flex flex-col gap-1.5">
              <label htmlFor="criticality" className="text-sm font-medium text-ink-700">
                Criticality
              </label>
              <select
                id="criticality"
                value={asset.criticality}
                disabled={isUpdatingCriticality}
                onChange={(e) => setCriticality(e.target.value)}
                className="h-10 w-40 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
              >
                {CRITICALITY_OPTIONS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
        </Card>

        <Card>
          <CardHeader title="Identifiers" />
          {asset.identifiers.length > 0 ? (
            <ul className="flex flex-col gap-1.5 text-sm">
              {asset.identifiers.map((id, idx) => (
                <li key={idx} className="flex justify-between border-b border-surface-border/50 pb-1.5">
                  <span className="text-ink-500">{id.identifier_type.replace(/_/g, " ")}</span>
                  <span className="text-ink-900">{id.identifier_value}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-500">No identifiers recorded.</p>
          )}
        </Card>

        <Card>
          <CardHeader title="Relationships" />
          {asset.relationships.length > 0 ? (
            <ul className="flex flex-col gap-1.5 text-sm">
              {asset.relationships.map((rel, idx) => (
                <li key={idx} className="flex justify-between border-b border-surface-border/50 pb-1.5">
                  <span className="text-ink-500">
                    {rel.direction === "outbound" ? rel.relationship_type.replace(/_/g, " ") : `${rel.relationship_type.replace(/_/g, " ")} (inbound)`}
                  </span>
                  <Link href={`/assets/${rel.related_asset_id}`} className="text-ink-900 hover:underline">
                    {rel.related_asset_display_name}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-500">No relationships recorded.</p>
          )}
        </Card>

        <Card>
          <CardHeader title="Owners" />
          {asset.owners.length > 0 ? (
            <ul className="flex flex-col gap-1.5 text-sm">
              {asset.owners.map((owner, idx) => (
                <li key={idx} className="flex justify-between border-b border-surface-border/50 pb-1.5">
                  <span className="text-ink-900">{owner.email}</span>
                  <span className="text-ink-500">{owner.ownership_type}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-500">No owners assigned.</p>
          )}
          {canAssignOwners ? (
            <div className="mt-4 flex gap-2">
              <select
                value={selectedOwnerId}
                onChange={(e) => setSelectedOwnerId(e.target.value)}
                className="h-10 flex-1 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
              >
                <option value="">Assign an owner…</option>
                {usersQuery.data?.map((u) => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.full_name} ({u.email})
                  </option>
                ))}
              </select>
              <Button size="sm" onClick={assignOwner} isLoading={isAssigningOwner} disabled={!selectedOwnerId}>
                Assign
              </Button>
            </div>
          ) : null}
        </Card>

        {Object.keys(asset.tags).length > 0 ? (
          <Card>
            <CardHeader title="Tags" />
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(asset.tags).map(([key, value]) => (
                <StatusBadge key={key} label={`${key}: ${value}`} />
              ))}
            </div>
          </Card>
        ) : null}

        <Card>
          <CardHeader title="Change history" />
          {changesQuery.data && changesQuery.data.length > 0 ? (
            <ul className="flex flex-col gap-1.5 text-sm">
              {changesQuery.data.map((change, idx) => (
                <li key={idx} className="border-b border-surface-border/50 pb-1.5">
                  <div className="flex justify-between">
                    <span className="text-ink-900">{change.field_name.replace(/_/g, " ")}</span>
                    <span className="text-ink-500">{new Date(change.changed_at).toLocaleString()}</span>
                  </div>
                  <p className="text-ink-500">
                    {change.old_value ?? <em>unset</em>} &rarr; {change.new_value ?? <em>unset</em>}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-500">No changes recorded yet.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
