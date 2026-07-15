"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { LeadSummary, Page, PortalAccountItem } from "@/lib/types";

export default function PortalAccountsPage() {
  const queryClient = useQueryClient();
  const [leadId, setLeadId] = useState("");

  const accountsQuery = useQuery({ queryKey: ["tenant", "portal-accounts"], queryFn: () => api.get<PortalAccountItem[]>("/tenant/portal-accounts") });
  const leadsQuery = useQuery({
    queryKey: ["tenant", "leads", "picker"],
    queryFn: () => api.get<Page<LeadSummary>>("/tenant/leads?page_size=200").then((r) => r.items),
  });

  const inviteMutation = useMutation({
    mutationFn: () => api.post("/tenant/portal-accounts/invite", { lead_id: leadId }),
    onSuccess: () => {
      setLeadId("");
      queryClient.invalidateQueries({ queryKey: ["tenant", "portal-accounts"] });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => api.post(`/tenant/portal-accounts/${id}/revoke`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "portal-accounts"] }),
  });

  const leads = leadsQuery.data ?? [];
  const invitedLeadIds = new Set((accountsQuery.data ?? []).map((a) => a.lead_id));
  const invitableLeads = leads.filter((l) => l.email && !invitedLeadIds.has(l.id));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Client portal access</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Invite a lead to their own self-service portal, where they can view proposals, upload requested documents, and track progress.
        </p>
      </div>

      <Card>
        <CardHeader title="Invite a lead" />
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            inviteMutation.mutate();
          }}
        >
          <div className="min-w-[260px] flex-1">
            <Label htmlFor="portal-lead">Lead</Label>
            <select
              id="portal-lead"
              className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
              value={leadId}
              onChange={(e) => setLeadId(e.target.value)}
              required
            >
              <option value="">Select a lead…</option>
              {invitableLeads.map((lead) => (
                <option key={lead.id} value={lead.id}>
                  {lead.first_name} {lead.last_name} ({lead.reference_number})
                </option>
              ))}
            </select>
          </div>
          <Button type="submit" disabled={inviteMutation.isPending || !leadId}>
            {inviteMutation.isPending ? "Inviting…" : "Send invite"}
          </Button>
        </form>
        <p className="mt-2 text-xs text-ink-faint">Only leads with an email address on file, who don&apos;t already have portal access, are listed.</p>
        {inviteMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{inviteMutation.error instanceof ApiError ? inviteMutation.error.message : "Unable to send invite."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Portal accounts" />
        <div className="space-y-2">
          {accountsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No one has been invited yet.</p>}
          {accountsQuery.data?.map((account) => (
            <div key={account.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
              <div>
                <p className="text-ink">{account.email}</p>
                <p className="text-xs text-ink-faint">Invited {new Date(account.created_at).toLocaleDateString()}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs font-medium ${account.is_active ? "text-emerald-400" : "text-red-400"}`}>
                  {account.is_active ? "Active" : "Revoked"}
                </span>
                {account.is_active && (
                  <Button variant="secondary" onClick={() => revokeMutation.mutate(account.id)} disabled={revokeMutation.isPending}>
                    Revoke
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
