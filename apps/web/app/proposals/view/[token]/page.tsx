"use client";

import { use, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { PublicProposal } from "@/lib/types";

export default function PublicProposalPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [acceptedByName, setAcceptedByName] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);

  const proposalQuery = useQuery({
    queryKey: ["public", "proposal", token],
    queryFn: () => api.get<PublicProposal>(`/public/proposals/${token}`),
  });

  const acceptMutation = useMutation({
    mutationFn: () => api.post<{ status: string }>(`/public/proposals/${token}/accept`, { accepted_by_name: acceptedByName }),
  });

  const rejectMutation = useMutation({
    mutationFn: () => api.post<{ status: string }>(`/public/proposals/${token}/reject`, { rejection_reason: rejectionReason }),
  });

  if (proposalQuery.isLoading) {
    return <div className="flex min-h-screen items-center justify-center text-ink-muted">Loading…</div>;
  }
  if (proposalQuery.isError || !proposalQuery.data) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Alert tone="error">This proposal could not be found.</Alert>
      </div>
    );
  }

  const proposal = proposalQuery.data;
  const finalStatus = acceptMutation.data?.status ?? rejectMutation.data?.status ?? proposal.status;
  const isFinal = finalStatus === "accepted" || finalStatus === "rejected" || finalStatus === "expired";

  return (
    <div className="min-h-screen bg-surface px-4 py-12">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-xl font-semibold text-ink">Proposal from {proposal.tenant_name}</h1>
        <p className="mt-1 text-sm text-ink-muted">{proposal.title}</p>

        {finalStatus === "accepted" && (
          <div className="mt-6">
            <Alert tone="success">This proposal has been accepted. Thank you!</Alert>
          </div>
        )}
        {finalStatus === "rejected" && (
          <div className="mt-6">
            <Alert tone="warning">This proposal has been declined.</Alert>
          </div>
        )}
        {finalStatus === "expired" && (
          <div className="mt-6">
            <Alert tone="error">This proposal has expired. Please contact {proposal.tenant_name} for an updated quote.</Alert>
          </div>
        )}

        <Card className="mt-6">
          <CardHeader title="Line items" />
          <div className="space-y-2">
            {proposal.line_items.map((item, index) => (
              <div key={index} className="flex justify-between text-sm">
                <span className="text-ink">{item.description} × {item.quantity}</span>
                <span className="text-ink-muted">{proposal.currency} {(item.quantity * item.unit_price).toFixed(2)}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 space-y-1 border-t border-surface-border pt-3 text-sm">
            <div className="flex justify-between text-ink-muted">
              <span>Subtotal</span><span>{proposal.currency} {proposal.subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-ink-muted">
              <span>Tax ({proposal.tax_rate}%)</span><span>{proposal.currency} {proposal.tax_amount.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-base font-semibold text-ink">
              <span>Total</span><span>{proposal.currency} {proposal.total.toFixed(2)}</span>
            </div>
          </div>
        </Card>

        {proposal.terms && (
          <Card className="mt-6">
            <CardHeader title="Terms" />
            <p className="whitespace-pre-wrap text-sm text-ink-muted">{proposal.terms}</p>
            {proposal.valid_until && <p className="mt-2 text-xs text-ink-faint">Valid until {proposal.valid_until}</p>}
          </Card>
        )}

        {!isFinal && (
          <Card className="mt-6">
            <CardHeader title="Respond to this proposal" />

            {acceptMutation.isError && (
              <div className="mb-3">
                <Alert tone="error">{acceptMutation.error instanceof ApiError ? acceptMutation.error.message : "Unable to accept this proposal."}</Alert>
              </div>
            )}
            {rejectMutation.isError && (
              <div className="mb-3">
                <Alert tone="error">{rejectMutation.error instanceof ApiError ? rejectMutation.error.message : "Unable to decline this proposal."}</Alert>
              </div>
            )}

            {!showRejectForm ? (
              <div className="space-y-4">
                <div>
                  <Label htmlFor="accepted-by-name">Your full name</Label>
                  <Input id="accepted-by-name" value={acceptedByName} onChange={(e) => setAcceptedByName(e.target.value)} placeholder="Jane Client" />
                </div>
                <div className="flex gap-3">
                  <Button
                    onClick={() => acceptMutation.mutate()}
                    disabled={!acceptedByName.trim() || acceptMutation.isPending}
                  >
                    {acceptMutation.isPending ? "Accepting…" : "Accept proposal"}
                  </Button>
                  <Button variant="secondary" onClick={() => setShowRejectForm(true)}>
                    Decline
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <Label htmlFor="rejection-reason">Reason (optional)</Label>
                  <Input id="rejection-reason" value={rejectionReason} onChange={(e) => setRejectionReason(e.target.value)} placeholder="e.g. Went with another provider" />
                </div>
                <div className="flex gap-3">
                  <Button variant="secondary" onClick={() => rejectMutation.mutate()} disabled={rejectMutation.isPending}>
                    {rejectMutation.isPending ? "Submitting…" : "Confirm decline"}
                  </Button>
                  <Button variant="secondary" onClick={() => setShowRejectForm(false)}>
                    Back
                  </Button>
                </div>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
