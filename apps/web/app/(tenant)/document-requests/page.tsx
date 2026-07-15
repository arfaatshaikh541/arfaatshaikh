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
import type { DocumentRequestItem, DocumentRequestStatus, LeadSummary, Page } from "@/lib/types";

const STATUS_TONE: Record<DocumentRequestStatus, string> = {
  requested: "text-accent",
  uploaded: "text-amber-400",
  approved: "text-emerald-400",
  rejected: "text-red-400",
};

export default function DocumentRequestsPage() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const leadIdFilter = searchParams.get("leadId") ?? "";

  const [leadId, setLeadId] = useState(leadIdFilter);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const requestsQuery = useQuery({
    queryKey: ["tenant", "document-requests", leadIdFilter],
    queryFn: () => api.get<DocumentRequestItem[]>(`/tenant/document-requests${leadIdFilter ? `?lead_id=${leadIdFilter}` : ""}`),
  });
  const leadsQuery = useQuery({
    queryKey: ["tenant", "leads", "picker"],
    queryFn: () => api.get<Page<LeadSummary>>("/tenant/leads?page_size=200").then((r) => r.items),
  });

  const createMutation = useMutation({
    mutationFn: () => api.post<DocumentRequestItem>("/tenant/document-requests", { lead_id: leadId, title, description }),
    onSuccess: () => {
      setTitle("");
      setDescription("");
      queryClient.invalidateQueries({ queryKey: ["tenant", "document-requests"] });
    },
  });

  const leads = leadsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Document requests</h1>
        <p className="mt-1 text-sm text-ink-muted">
          {leadIdFilter ? "Document requests for this lead." : "Requests for documents from your leads, with a shareable upload link for each."}
        </p>
      </div>

      <Card>
        <CardHeader title="Request a document" />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="doc-lead">Lead</Label>
              <select
                id="doc-lead"
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
              <Label htmlFor="doc-title">Title</Label>
              <Input id="doc-title" placeholder="e.g. Passport copy" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
          </div>
          <div>
            <Label htmlFor="doc-description">Description (optional)</Label>
            <Input id="doc-description" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <Button type="submit" disabled={createMutation.isPending || !leadId || !title}>
            {createMutation.isPending ? "Requesting…" : "Request document"}
          </Button>
        </form>
        {createMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to request document."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Requests" />
        <div className="space-y-2">
          {requestsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No document requests yet.</p>}
          {requestsQuery.data?.map((request) => (
            <Link
              key={request.id}
              href={`/document-requests/${request.id}`}
              className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm hover:border-ink-muted"
            >
              <div>
                <p className="font-medium text-ink">{request.title}</p>
                {request.description && <p className="text-xs text-ink-faint">{request.description}</p>}
              </div>
              <span className={`text-xs font-medium capitalize ${STATUS_TONE[request.status]}`}>{request.status}</span>
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}
