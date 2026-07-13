"use client";

import { Badge, Card } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { apiFetch } from "@/lib/api-client";
import { PRIORITY_LABELS, PRIORITY_TONES, type LeadOut, type PipelineStageOut } from "@/lib/types";

const PAGE_SIZE = 100;

export default function LeadsBoardPage() {
  const { tenantId } = useCurrentTenant();
  const queryClient = useQueryClient();
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOverStage, setDragOverStage] = useState<string | null>(null);

  const stagesQuery = useQuery({
    queryKey: ["pipeline-stages", tenantId],
    queryFn: () => apiFetch<PipelineStageOut[]>("/tenants/me/pipeline-stages"),
    enabled: Boolean(tenantId),
  });

  const leadsQuery = useQuery({
    queryKey: ["leads-board", tenantId],
    queryFn: () =>
      apiFetch<{ items: LeadOut[]; total: number }>(
        `/tenants/me/leads?page=1&page_size=${PAGE_SIZE}`
      ),
    enabled: Boolean(tenantId),
  });

  const changeStageMutation = useMutation({
    mutationFn: ({ leadId, toStageId }: { leadId: string; toStageId: string }) =>
      apiFetch(`/tenants/me/leads/${leadId}/stage`, {
        method: "POST",
        body: { to_stage_id: toStageId },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads-board", tenantId] });
      queryClient.invalidateQueries({ queryKey: ["leads", tenantId] });
    },
  });

  const leadsByStage = new Map<string, LeadOut[]>();
  for (const lead of leadsQuery.data?.items ?? []) {
    const list = leadsByStage.get(lead.stage_id) ?? [];
    list.push(lead);
    leadsByStage.set(lead.stage_id, list);
  }

  const handleDrop = (stageId: string) => {
    setDragOverStage(null);
    if (!draggingId) return;
    const lead = leadsQuery.data?.items.find((l) => l.id === draggingId);
    if (lead && lead.stage_id !== stageId) {
      // Lost stages require a loss reason via the lead detail page; the
      // board only performs the change when it doesn't need one.
      const stage = stagesQuery.data?.find((s) => s.id === stageId);
      if (stage?.is_lost) {
        window.location.href = `/leads/${draggingId}`;
        return;
      }
      changeStageMutation.mutate({ leadId: draggingId, toStageId: stageId });
    }
    setDraggingId(null);
  };

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Pipeline board</h1>
      <p className="mb-6 text-sm text-surface-400">Drag a lead card to change its stage.</p>

      <div className="flex gap-4 overflow-x-auto pb-4">
        {stagesQuery.data?.map((stage) => (
          <div
            key={stage.id}
            className={`w-64 flex-shrink-0 rounded-lg border p-3 ${
              dragOverStage === stage.id
                ? "border-accent-500 bg-accent-600/5"
                : "border-surface-800 bg-surface-900"
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOverStage(stage.id);
            }}
            onDragLeave={() => setDragOverStage((s) => (s === stage.id ? null : s))}
            onDrop={() => handleDrop(stage.id)}
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-surface-100">{stage.name}</h2>
              <span className="text-xs text-surface-500">
                {leadsByStage.get(stage.id)?.length ?? 0}
              </span>
            </div>
            <div className="space-y-2">
              {(leadsByStage.get(stage.id) ?? []).map((lead) => (
                <Card
                  key={lead.id}
                  draggable
                  onDragStart={() => setDraggingId(lead.id)}
                  onDragEnd={() => setDraggingId(null)}
                  className={`cursor-move p-3 ${draggingId === lead.id ? "opacity-40" : ""}`}
                >
                  <Link href={`/leads/${lead.id}`} className="block">
                    <p className="text-sm font-medium text-surface-100">
                      {lead.first_name} {lead.last_name}
                    </p>
                    <p className="text-xs text-surface-500">{lead.company ?? lead.reference_number}</p>
                    <Badge tone={PRIORITY_TONES[lead.priority] ?? "neutral"} className="mt-2">
                      {PRIORITY_LABELS[lead.priority] ?? lead.priority}
                    </Badge>
                  </Link>
                </Card>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
