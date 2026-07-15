"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { LineItemInput, ProposalTemplate } from "@/lib/types";

function emptyLineItem(): LineItemInput {
  return { description: "", quantity: 1, unit_price: 0 };
}

export default function ProposalTemplatesPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [terms, setTerms] = useState("");
  const [lineItems, setLineItems] = useState<LineItemInput[]>([emptyLineItem()]);

  const templatesQuery = useQuery({ queryKey: ["tenant", "proposal-templates"], queryFn: () => api.get<ProposalTemplate[]>("/tenant/proposal-templates") });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post("/tenant/proposal-templates", {
        name, description, terms,
        line_items: lineItems.filter((item) => item.description.trim()),
      }),
    onSuccess: () => {
      setName("");
      setDescription("");
      setTerms("");
      setLineItems([emptyLineItem()]);
      queryClient.invalidateQueries({ queryKey: ["tenant", "proposal-templates"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (templateId: string) => api.delete(`/tenant/proposal-templates/${templateId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "proposal-templates"] }),
  });

  function updateLineItem(index: number, patch: Partial<LineItemInput>) {
    setLineItems((items) => items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Proposal templates</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Reusable defaults (description, terms, and line items) you can start a new proposal from — every field can still be edited per-proposal afterward.
        </p>
      </div>

      <Card>
        <CardHeader title="Add a template" />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="tpl-name">Name</Label>
              <Input id="tpl-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="tpl-description">Description</Label>
              <Input id="tpl-description" value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
          </div>
          <div>
            <Label htmlFor="tpl-terms">Terms</Label>
            <textarea
              id="tpl-terms"
              className="focus-ring min-h-[80px] w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
              value={terms}
              onChange={(e) => setTerms(e.target.value)}
            />
          </div>

          <div>
            <Label>Line items</Label>
            <div className="space-y-2">
              {lineItems.map((item, index) => (
                <div key={index} className="flex flex-wrap items-end gap-2">
                  <div className="min-w-[220px] flex-1">
                    <Input
                      placeholder="Description"
                      value={item.description}
                      onChange={(e) => updateLineItem(index, { description: e.target.value })}
                    />
                  </div>
                  <div className="w-24">
                    <Input
                      type="number" min={0} step="0.01" placeholder="Qty"
                      value={item.quantity} onChange={(e) => updateLineItem(index, { quantity: Number(e.target.value) })}
                    />
                  </div>
                  <div className="w-32">
                    <Input
                      type="number" min={0} step="0.01" placeholder="Unit price"
                      value={item.unit_price} onChange={(e) => updateLineItem(index, { unit_price: Number(e.target.value) })}
                    />
                  </div>
                  <Button
                    type="button" variant="secondary"
                    onClick={() => setLineItems((items) => items.filter((_, i) => i !== index))}
                    disabled={lineItems.length === 1}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
            <Button type="button" variant="secondary" className="mt-2" onClick={() => setLineItems((items) => [...items, emptyLineItem()])}>
              Add line
            </Button>
          </div>

          <Button type="submit" disabled={createMutation.isPending || !name}>
            {createMutation.isPending ? "Adding…" : "Add template"}
          </Button>
        </form>
        {createMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to add template."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Templates" />
        <div className="space-y-3">
          {templatesQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No templates yet.</p>}
          {templatesQuery.data?.map((template) => (
            <div key={template.id} className="rounded-md border border-surface-border p-3 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-ink">{template.name}</p>
                  <p className="text-xs text-ink-faint">{template.description}</p>
                </div>
                <Button variant="secondary" onClick={() => deleteMutation.mutate(template.id)} disabled={deleteMutation.isPending}>
                  Delete
                </Button>
              </div>
              <ul className="mt-2 space-y-1">
                {template.line_items.map((item) => (
                  <li key={item.id} className="flex justify-between text-xs text-ink-muted">
                    <span>{item.description} × {item.quantity}</span>
                    <span>{item.unit_price}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
