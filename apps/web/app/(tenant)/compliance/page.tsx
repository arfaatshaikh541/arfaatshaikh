"use client";

import { Button, Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { EvidenceList } from "@/components/EvidenceList";
import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { ControlRead, FrameworkRead } from "@/lib/types";

const STATUS_OPTIONS = [
  { value: "met", label: "Met" },
  { value: "partial", label: "Partial" },
  { value: "not_met", label: "Not met" },
  { value: "not_applicable", label: "Not applicable" },
];

const STATUS_TONE: Record<string, "positive" | "warning" | "neutral"> = {
  met: "positive",
  partial: "warning",
  not_met: "neutral",
  not_applicable: "neutral",
};

function scoreTone(score: number): "positive" | "warning" | "neutral" {
  if (score >= 80) return "positive";
  if (score >= 50) return "warning";
  return "neutral";
}

function ControlRow({ control, canManage }: { control: ControlRead; canManage: boolean }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState(control.status);
  const [note, setNote] = useState(control.note ?? "");
  const [showEvidence, setShowEvidence] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const dirty = status !== control.status || note !== (control.note ?? "");

  const save = async () => {
    setError(null);
    setIsSaving(true);
    try {
      await apiClient.patch(`/api/compliance/controls/${control.id}`, { status, note: note || null });
      queryClient.invalidateQueries({ queryKey: ["compliance", "frameworks"] });
      queryClient.invalidateQueries({ queryKey: ["compliance", "summary"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="border-b border-surface-border/50 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-ink-900">{control.title}</p>
          <p className="text-xs text-ink-500">{control.description}</p>
        </div>
        <StatusBadge label={control.status.replace(/_/g, " ")} tone={STATUS_TONE[control.status] ?? "neutral"} />
      </div>

      {error ? <p className="mt-2 text-xs text-severity-critical">{error}</p> : null}

      {canManage ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-9 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Note (optional)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="h-9 flex-1 min-w-[12rem] rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          />
          <Button size="sm" disabled={!dirty} isLoading={isSaving} onClick={save}>
            Save
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setShowEvidence((v) => !v)}>
            {showEvidence ? "Hide evidence" : "Evidence"}
          </Button>
        </div>
      ) : (
        <div className="mt-2 flex items-center gap-2">
          {control.note ? <p className="text-xs text-ink-500">Note: {control.note}</p> : null}
          <Button size="sm" variant="ghost" onClick={() => setShowEvidence((v) => !v)}>
            {showEvidence ? "Hide evidence" : "Evidence"}
          </Button>
        </div>
      )}

      {showEvidence ? (
        <div className="mt-3">
          <EvidenceList targetType="compliance_control" targetId={control.id} canManage={canManage} />
        </div>
      ) : null}
    </div>
  );
}

export default function CompliancePage() {
  const { hasPermission } = useAuth();
  const canView = hasPermission("compliance.view");
  const canManage = hasPermission("compliance.manage");

  const frameworksQuery = useQuery({
    queryKey: ["compliance", "frameworks"],
    queryFn: () => apiClient.get<FrameworkRead[]>("/api/compliance/frameworks"),
    enabled: canView,
  });

  if (!canView) {
    return <p className="text-sm text-ink-500">Not visible to your role.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Compliance</h1>
        <p className="text-sm text-ink-500">
          Prove your security: track control status against known frameworks and attach evidence for an
          audit.
        </p>
      </div>

      {frameworksQuery.data?.map((framework) => (
        <Card key={framework.id}>
          <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
            <CardHeader title={framework.name} description={framework.description} />
            <div className="flex items-center gap-2">
              <span className="text-2xl font-semibold text-ink-900">{framework.score}</span>
              <span className="text-sm text-ink-500">/ 100</span>
              <StatusBadge
                label={
                  framework.score >= 80 ? "Strong" : framework.score >= 50 ? "Needs attention" : "At risk"
                }
                tone={scoreTone(framework.score)}
              />
            </div>
          </div>
          <div>
            {framework.controls.map((control) => (
              <ControlRow key={control.id} control={control} canManage={canManage} />
            ))}
          </div>
        </Card>
      ))}

      {!frameworksQuery.data ? <p className="text-sm text-ink-500">Loading…</p> : null}
    </div>
  );
}
