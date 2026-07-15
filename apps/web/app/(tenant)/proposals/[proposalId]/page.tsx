"use client";

import { use, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { LineItemInput, ProposalItem, ProposalStatus } from "@/lib/types";

const STATUS_TONE: Record<ProposalStatus, string> = {
  draft: "text-ink-faint",
  sent: "text-accent",
  viewed: "text-amber-400",
  accepted: "text-emerald-400",
  rejected: "text-red-400",
  expired: "text-ink-faint",
};

function toLineItemInputs(proposal: ProposalItem): LineItemInput[] {
  if (proposal.line_items.length === 0) return [{ description: "", quantity: 1, unit_price: 0 }];
  return proposal.line_items.map((item) => ({ description: item.description, quantity: item.quantity, unit_price: item.unit_price }));
}

export default function ProposalDetailPage({ params }: { params: Promise<{ proposalId: string }> }) {
  const { proposalId } = use(params);
  const queryClient = useQueryClient();
  const [lineItems, setLineItems] = useState<LineItemInput[] | null>(null);

  const proposalQuery = useQuery({ queryKey: ["proposal", proposalId], queryFn: () => api.get<ProposalItem>(`/tenant/proposals/${proposalId}`) });

  useEffect(() => {
    if (proposalQuery.data && lineItems === null) {
      setLineItems(toLineItemInputs(proposalQuery.data));
    }
  }, [proposalQuery.data, lineItems]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["proposal", proposalId] });

  const saveLineItemsMutation = useMutation({
    mutationFn: (items: LineItemInput[]) => api.put(`/tenant/proposals/${proposalId}/line-items`, { line_items: items.filter((i) => i.description.trim()) }),
    onSuccess: invalidate,
  });

  const sendMutation = useMutation({
    mutationFn: () => api.post(`/tenant/proposals/${proposalId}/send`),
    onSuccess: invalidate,
  });

  function updateLineItem(index: number, patch: Partial<LineItemInput>) {
    setLineItems((items) => (items ?? []).map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  const proposal = proposalQuery.data;
  if (proposalQuery.isLoading || !proposal) return <p className="text-sm text-ink-muted">Loading…</p>;

  const isDraft = proposal.status === "draft";
  const publicUrl = proposal.public_token
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/proposals/view/${proposal.public_token}`
    : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">{proposal.title}</h1>
          <p className={`mt-1 text-sm font-medium capitalize ${STATUS_TONE[proposal.status]}`}>{proposal.status}</p>
        </div>
        {(proposal.status === "draft" || proposal.status === "sent") && (
          <Button onClick={() => sendMutation.mutate()} disabled={sendMutation.isPending}>
            {sendMutation.isPending ? "Sending…" : proposal.status === "sent" ? "Resend" : "Send to client"}
          </Button>
        )}
      </div>

      {sendMutation.isError && <Alert tone="error">{sendMutation.error instanceof ApiError ? sendMutation.error.message : "Unable to send proposal."}</Alert>}

      {publicUrl && (
        <Card>
          <CardHeader title="Client link" description="Share this link, or rely on the email sent automatically when you send the proposal." />
          <Input readOnly value={publicUrl} onFocus={(e) => e.currentTarget.select()} />
        </Card>
      )}

      {proposal.status === "accepted" && (
        <Alert tone="success">Accepted by {proposal.accepted_by_name} on {proposal.accepted_at ? new Date(proposal.accepted_at).toLocaleString() : ""}.</Alert>
      )}
      {proposal.status === "rejected" && (
        <Alert tone="error">Rejected{proposal.rejection_reason ? `: ${proposal.rejection_reason}` : "."}</Alert>
      )}

      <Card>
        <CardHeader title="Line items" description={isDraft ? "Editable while this proposal is still a draft." : "Locked once sent — resend after editing a draft copy if needed."} />
        <div className="space-y-2">
          {(lineItems ?? []).map((item, index) => (
            <div key={index} className="flex flex-wrap items-end gap-2">
              <div className="min-w-[220px] flex-1">
                <Input
                  placeholder="Description" value={item.description} disabled={!isDraft}
                  onChange={(e) => updateLineItem(index, { description: e.target.value })}
                />
              </div>
              <div className="w-24">
                <Input
                  type="number" min={0} step="0.01" placeholder="Qty" value={item.quantity} disabled={!isDraft}
                  onChange={(e) => updateLineItem(index, { quantity: Number(e.target.value) })}
                />
              </div>
              <div className="w-32">
                <Input
                  type="number" min={0} step="0.01" placeholder="Unit price" value={item.unit_price} disabled={!isDraft}
                  onChange={(e) => updateLineItem(index, { unit_price: Number(e.target.value) })}
                />
              </div>
              {isDraft && (
                <Button
                  type="button" variant="secondary"
                  onClick={() => setLineItems((items) => (items ?? []).filter((_, i) => i !== index))}
                  disabled={(lineItems ?? []).length === 1}
                >
                  Remove
                </Button>
              )}
            </div>
          ))}
          {isDraft && (
            <div className="flex gap-2 pt-2">
              <Button type="button" variant="secondary" onClick={() => setLineItems((items) => [...(items ?? []), { description: "", quantity: 1, unit_price: 0 }])}>
                Add line
              </Button>
              <Button
                type="button"
                onClick={() => saveLineItemsMutation.mutate(lineItems ?? [])}
                disabled={saveLineItemsMutation.isPending}
              >
                {saveLineItemsMutation.isPending ? "Saving…" : "Save line items"}
              </Button>
            </div>
          )}
        </div>
        {saveLineItemsMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{saveLineItemsMutation.error instanceof ApiError ? saveLineItemsMutation.error.message : "Unable to save line items."}</Alert>
          </div>
        )}

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

      <Card>
        <CardHeader title="Terms" />
        <p className="whitespace-pre-wrap text-sm text-ink-muted">{proposal.terms || "No terms specified."}</p>
        {proposal.valid_until && <p className="mt-2 text-xs text-ink-faint">Valid until {proposal.valid_until}</p>}
      </Card>
    </div>
  );
}
