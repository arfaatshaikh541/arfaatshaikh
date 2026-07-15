"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { LeadSummary, Page, ProposalItem, ProposalStatus, ProposalTemplate } from "@/lib/types";

const STATUS_TONE: Record<ProposalStatus, string> = {
  draft: "text-ink-faint",
  sent: "text-accent",
  viewed: "text-amber-400",
  accepted: "text-emerald-400",
  rejected: "text-red-400",
  expired: "text-ink-faint",
};

export default function ProposalsPage() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const leadIdFilter = searchParams.get("leadId") ?? "";

  const [leadId, setLeadId] = useState(leadIdFilter);
  const [title, setTitle] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [taxRate, setTaxRate] = useState("0");
  const [validUntil, setValidUntil] = useState("");

  const proposalsQuery = useQuery({
    queryKey: ["tenant", "proposals", leadIdFilter],
    queryFn: () => api.get<ProposalItem[]>(`/tenant/proposals${leadIdFilter ? `?lead_id=${leadIdFilter}` : ""}`),
  });
  const leadsQuery = useQuery({
    queryKey: ["tenant", "leads", "picker"],
    queryFn: () => api.get<Page<LeadSummary>>("/tenant/leads?page_size=200").then((r) => r.items),
  });
  const templatesQuery = useQuery({ queryKey: ["tenant", "proposal-templates"], queryFn: () => api.get<ProposalTemplate[]>("/tenant/proposal-templates") });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post<ProposalItem>("/tenant/proposals", {
        lead_id: leadId,
        title,
        template_id: templateId || null,
        tax_rate: Number(taxRate),
        valid_until: validUntil || null,
      }),
    onSuccess: () => {
      setTitle("");
      setTemplateId("");
      setTaxRate("0");
      setValidUntil("");
      queryClient.invalidateQueries({ queryKey: ["tenant", "proposals"] });
    },
  });

  const leads = leadsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Proposals</h1>
        <p className="mt-1 text-sm text-ink-muted">
          {leadIdFilter ? "Proposals for this lead." : "Proposals sent to your leads, from draft through acceptance."}
        </p>
      </div>

      <Card>
        <CardHeader title="Create a proposal" description="Optionally start from a template — its terms and line items are copied in, and can still be edited before sending." />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="prop-lead">Lead</Label>
              <select
                id="prop-lead"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={leadId}
                onChange={(e) => setLeadId(e.target.value)}
                required
              >
                <option value="">Select a lead…</option>
                {leads.map((lead) => (
                  <option key={lead.id} value={lead.id}>
                    {lead.first_name} {lead.last_name} ({lead.reference_number})
                  </option>
                ))}
              </select>
            </div>
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="prop-title">Title</Label>
              <Input id="prop-title" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="prop-template">Template (optional)</Label>
              <select
                id="prop-template"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                <option value="">No template — blank proposal</option>
                {templatesQuery.data?.map((template) => (
                  <option key={template.id} value={template.id}>{template.name}</option>
                ))}
              </select>
            </div>
            <div className="w-32">
              <Label htmlFor="prop-tax">Tax rate (%)</Label>
              <Input id="prop-tax" type="number" min={0} max={100} step="0.01" value={taxRate} onChange={(e) => setTaxRate(e.target.value)} />
            </div>
            <div className="w-44">
              <Label htmlFor="prop-valid-until">Valid until (optional)</Label>
              <Input id="prop-valid-until" type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} />
            </div>
          </div>
          <p className="text-xs text-ink-faint">
            Line items can be added on the proposal detail page after creating it (or copied automatically from the selected template).
          </p>
          <Button type="submit" disabled={createMutation.isPending || !leadId || !title}>
            {createMutation.isPending ? "Creating…" : "Create proposal"}
          </Button>
        </form>
        {createMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to create proposal."}</Alert>
          </div>
        )}
        {createMutation.isSuccess && (
          <div className="mt-3">
            <Alert tone="success">
              Proposal created. <Link href={`/proposals/${createMutation.data.id}`} className="underline">Open it</Link> to add line items and send it.
            </Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Proposals" />
        <div className="space-y-2">
          {proposalsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No proposals yet.</p>}
          {proposalsQuery.data?.map((proposal) => (
            <Link
              key={proposal.id}
              href={`/proposals/${proposal.id}`}
              className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm hover:border-ink-muted"
            >
              <div>
                <p className="font-medium text-ink">{proposal.title}</p>
                <p className="text-xs text-ink-faint">{proposal.currency} {proposal.total.toFixed(2)}</p>
              </div>
              <span className={`text-xs font-medium capitalize ${STATUS_TONE[proposal.status]}`}>{proposal.status}</span>
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}
