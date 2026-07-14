"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api-client";
import type { LeadSummary, Page, Pipeline } from "@/lib/types";

const priorityTone: Record<string, string> = {
  high: "text-red-400",
  medium: "text-amber-400",
  low: "text-ink-faint",
};

function LeadsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const view = searchParams.get("view") === "board" ? "board" : "table";
  const [search, setSearch] = useState("");
  const queryClient = useQueryClient();

  const pipelinesQuery = useQuery({ queryKey: ["tenant", "pipelines"], queryFn: () => api.get<Pipeline[]>("/tenant/pipelines") });
  const leadsQuery = useQuery({
    queryKey: ["tenant", "leads", search],
    queryFn: () => api.get<Page<LeadSummary>>(`/tenant/leads?page_size=100${search ? `&q=${encodeURIComponent(search)}` : ""}`),
  });

  const changeStageMutation = useMutation({
    mutationFn: ({ leadId, stageId }: { leadId: string; stageId: string }) =>
      api.post(`/tenant/leads/${leadId}/stage`, { stage_id: stageId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "leads"] }),
  });

  const setView = (next: "table" | "board") => {
    router.replace(`/leads?view=${next}`);
  };

  const pipeline = pipelinesQuery.data?.[0];
  const leads = leadsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Leads</h1>
          <p className="mt-1 text-sm text-ink-muted">{leadsQuery.data?.total ?? 0} leads</p>
        </div>
        <div className="flex gap-2">
          <Button variant={view === "table" ? "primary" : "secondary"} onClick={() => setView("table")}>
            Table
          </Button>
          <Button variant={view === "board" ? "primary" : "secondary"} onClick={() => setView("board")}>
            Board
          </Button>
        </div>
      </div>

      <div className="max-w-sm">
        <Input placeholder="Search name, email, phone, reference…" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      {view === "table" && (
        <Card>
          {leadsQuery.isLoading && <p className="text-sm text-ink-muted">Loading…</p>}
          {!leadsQuery.isLoading && (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-ink-faint">
                  <th className="pb-2 font-medium">Reference</th>
                  <th className="pb-2 font-medium">Name</th>
                  <th className="pb-2 font-medium">Contact</th>
                  <th className="pb-2 font-medium">Company</th>
                  <th className="pb-2 font-medium">Priority</th>
                  <th className="pb-2 font-medium">Stage</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.id} className="border-b border-surface-border/60">
                    <td className="py-2">
                      <Link href={`/leads/${lead.id}`} className="text-accent hover:text-accent-hover">
                        {lead.reference_number}
                      </Link>
                      {lead.is_possible_duplicate && (
                        <span className="ml-2 rounded-full bg-amber-950/50 px-2 py-0.5 text-xs text-amber-400">possible duplicate</span>
                      )}
                    </td>
                    <td className="py-2 text-ink">
                      {lead.first_name} {lead.last_name}
                    </td>
                    <td className="py-2 text-ink-muted">{lead.email ?? lead.phone ?? "—"}</td>
                    <td className="py-2 text-ink-muted">{lead.company ?? "—"}</td>
                    <td className={`py-2 capitalize ${priorityTone[lead.priority]}`}>{lead.priority}</td>
                    <td className="py-2 text-ink-muted">
                      {pipeline?.stages.find((s) => s.id === lead.stage_id)?.name ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {view === "board" && pipeline && (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {pipeline.stages.map((stage) => (
            <div key={stage.id} className="w-64 flex-none">
              <div className="mb-2 flex items-center justify-between px-1">
                <span className="text-sm font-medium text-ink">{stage.name}</span>
                <span className="text-xs text-ink-faint">{leads.filter((l) => l.stage_id === stage.id).length}</span>
              </div>
              <div className="space-y-2">
                {leads
                  .filter((lead) => lead.stage_id === stage.id)
                  .map((lead) => (
                    <div key={lead.id} className="rounded-md border border-surface-border bg-surface-raised p-3">
                      <Link href={`/leads/${lead.id}`} className="text-sm font-medium text-ink hover:text-accent">
                        {lead.first_name} {lead.last_name}
                      </Link>
                      <p className="mt-0.5 text-xs text-ink-faint">{lead.reference_number}</p>
                      <select
                        className="focus-ring mt-2 w-full rounded-md border border-surface-border bg-surface px-2 py-1 text-xs text-ink"
                        value={stage.id}
                        onChange={(e) => changeStageMutation.mutate({ leadId: lead.id, stageId: e.target.value })}
                      >
                        {pipeline.stages.map((s) => (
                          <option key={s.id} value={s.id}>
                            Move to: {s.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function LeadsPage() {
  return (
    <Suspense fallback={null}>
      <LeadsPageInner />
    </Suspense>
  );
}
