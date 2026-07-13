"use client";

import { Badge, Button, Card, Input } from "@leadflow/ui";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { apiFetch } from "@/lib/api-client";
import {
  PRIORITY_LABELS,
  PRIORITY_TONES,
  type LeadListOut,
  type PipelineStageOut,
  type ServiceOut,
} from "@/lib/types";

const PAGE_SIZE = 20;

export default function LeadsPage() {
  const { tenantId } = useCurrentTenant();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [stageId, setStageId] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [priority, setPriority] = useState("");

  const stagesQuery = useQuery({
    queryKey: ["pipeline-stages", tenantId],
    queryFn: () => apiFetch<PipelineStageOut[]>("/tenants/me/pipeline-stages"),
    enabled: Boolean(tenantId),
  });
  const servicesQuery = useQuery({
    queryKey: ["services", tenantId],
    queryFn: () => apiFetch<ServiceOut[]>("/tenants/me/services"),
    enabled: Boolean(tenantId),
  });

  const leadsQuery = useQuery({
    queryKey: ["leads", tenantId, page, search, stageId, serviceId, priority],
    queryFn: () =>
      apiFetch<LeadListOut>(
        `/tenants/me/leads?${new URLSearchParams({
          page: String(page),
          page_size: String(PAGE_SIZE),
          ...(search ? { search } : {}),
          ...(stageId ? { stage_id: stageId } : {}),
          ...(serviceId ? { service_id: serviceId } : {}),
          ...(priority ? { priority } : {}),
        }).toString()}`
      ),
    enabled: Boolean(tenantId),
  });

  const stageName = (id: string) => stagesQuery.data?.find((s) => s.id === id)?.name ?? "—";
  const totalPages = leadsQuery.data ? Math.max(1, Math.ceil(leadsQuery.data.total / PAGE_SIZE)) : 1;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-surface-50">Leads</h1>
          <p className="text-sm text-surface-400">{leadsQuery.data?.total ?? 0} total</p>
        </div>
        <Link href="/leads/new">
          <Button>New lead</Button>
        </Link>
      </div>

      <Card className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-surface-200">Search</label>
            <Input
              className="w-64"
              placeholder="Name, email, phone, reference…"
              value={search}
              onChange={(e) => {
                setPage(1);
                setSearch(e.target.value);
              }}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-surface-200">Stage</label>
            <select
              className="rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
              value={stageId}
              onChange={(e) => {
                setPage(1);
                setStageId(e.target.value);
              }}
            >
              <option value="">All stages</option>
              {stagesQuery.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-surface-200">Service</label>
            <select
              className="rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
              value={serviceId}
              onChange={(e) => {
                setPage(1);
                setServiceId(e.target.value);
              }}
            >
              <option value="">All services</option>
              {servicesQuery.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-surface-200">Priority</label>
            <select
              className="rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
              value={priority}
              onChange={(e) => {
                setPage(1);
                setPriority(e.target.value);
              }}
            >
              <option value="">All priorities</option>
              {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      <Card>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-800 text-surface-500">
              <th className="pb-2 font-medium">Reference</th>
              <th className="pb-2 font-medium">Name</th>
              <th className="pb-2 font-medium">Company</th>
              <th className="pb-2 font-medium">Stage</th>
              <th className="pb-2 font-medium">Priority</th>
              <th className="pb-2 font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {leadsQuery.data?.items.map((lead) => (
              <tr key={lead.id} className="border-b border-surface-900 hover:bg-surface-900">
                <td className="py-2">
                  <Link href={`/leads/${lead.id}`} className="text-accent-500 hover:text-accent-400">
                    {lead.reference_number}
                  </Link>
                </td>
                <td className="py-2 text-surface-200">
                  {lead.first_name} {lead.last_name}
                </td>
                <td className="py-2 text-surface-400">{lead.company ?? "—"}</td>
                <td className="py-2 text-surface-400">{stageName(lead.stage_id)}</td>
                <td className="py-2">
                  <Badge tone={PRIORITY_TONES[lead.priority] ?? "neutral"}>
                    {PRIORITY_LABELS[lead.priority] ?? lead.priority}
                  </Badge>
                </td>
                <td className="py-2 text-surface-400">{lead.source}</td>
              </tr>
            ))}
            {leadsQuery.data?.items.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-6 text-center text-surface-500">
                  No leads match these filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
        <div className="mt-4 flex items-center justify-between">
          <span className="text-xs text-surface-500">
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <Button
              variant="ghost"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
