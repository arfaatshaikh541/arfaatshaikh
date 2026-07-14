"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { AssignmentRule, AssignmentStrategy, PublicService, TenantMember } from "@/lib/types";

const STRATEGIES: { value: AssignmentStrategy; label: string }[] = [
  { value: "round_robin", label: "Round-robin (cycles through eligible staff)" },
  { value: "service_based", label: "Service-based (match specific services)" },
  { value: "priority_based", label: "Priority-based (match specific priorities)" },
];

export default function AssignmentPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [strategy, setStrategy] = useState<AssignmentStrategy>("round_robin");
  const [selectedServiceIds, setSelectedServiceIds] = useState<string[]>([]);
  const [selectedPriorities, setSelectedPriorities] = useState<string[]>([]);
  const [eligibleUserIds, setEligibleUserIds] = useState<string[]>([]);

  const rulesQuery = useQuery({ queryKey: ["tenant", "assignment", "rules"], queryFn: () => api.get<AssignmentRule[]>("/tenant/assignment/rules") });
  const membersQuery = useQuery({ queryKey: ["tenant", "users"], queryFn: () => api.get<TenantMember[]>("/tenant/users") });
  const servicesQuery = useQuery({ queryKey: ["tenant", "services"], queryFn: () => api.get<PublicService[]>("/tenant/services") });

  const createRule = useMutation({
    mutationFn: () =>
      api.post("/tenant/assignment/rules", {
        name,
        strategy,
        conditions:
          strategy === "service_based" ? { service_ids: selectedServiceIds }
          : strategy === "priority_based" ? { priorities: selectedPriorities }
          : {},
        eligible_user_ids: eligibleUserIds,
      }),
    onSuccess: () => {
      setName("");
      setSelectedServiceIds([]);
      setSelectedPriorities([]);
      setEligibleUserIds([]);
      queryClient.invalidateQueries({ queryKey: ["tenant", "assignment", "rules"] });
    },
  });

  const toggleRule = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => api.patch(`/tenant/assignment/rules/${id}`, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "assignment", "rules"] }),
  });

  const members = membersQuery.data ?? [];
  const memberName = (userId: string) => {
    const member = members.find((m) => m.user_id === userId);
    return member ? `${member.first_name} ${member.last_name}` : userId;
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Lead assignment</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Rules run in order for every new lead — the first active rule that matches and has eligible staff assigns the lead. No match leaves it unassigned.
        </p>
      </div>

      <Card>
        <CardHeader title="Add an assignment rule" />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            createRule.mutate();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[200px]">
              <Label htmlFor="rule-name">Name</Label>
              <Input id="rule-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="min-w-[280px]">
              <Label htmlFor="rule-strategy">Strategy</Label>
              <select
                id="rule-strategy"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={strategy}
                onChange={(e) => setStrategy(e.target.value as AssignmentStrategy)}
              >
                {STRATEGIES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>

          {strategy === "service_based" && (
            <div>
              <Label>Match these services</Label>
              <div className="flex flex-wrap gap-2">
                {servicesQuery.data?.map((service) => (
                  <label key={service.id} className="flex items-center gap-1.5 rounded-full border border-surface-border px-2.5 py-1 text-xs text-ink">
                    <input
                      type="checkbox"
                      checked={selectedServiceIds.includes(service.id)}
                      onChange={(e) =>
                        setSelectedServiceIds((prev) => (e.target.checked ? [...prev, service.id] : prev.filter((id) => id !== service.id)))
                      }
                    />
                    {service.name}
                  </label>
                ))}
              </div>
            </div>
          )}

          {strategy === "priority_based" && (
            <div>
              <Label>Match these priorities</Label>
              <div className="flex flex-wrap gap-2">
                {["low", "medium", "high"].map((priority) => (
                  <label key={priority} className="flex items-center gap-1.5 rounded-full border border-surface-border px-2.5 py-1 text-xs capitalize text-ink">
                    <input
                      type="checkbox"
                      checked={selectedPriorities.includes(priority)}
                      onChange={(e) =>
                        setSelectedPriorities((prev) => (e.target.checked ? [...prev, priority] : prev.filter((p) => p !== priority)))
                      }
                    />
                    {priority}
                  </label>
                ))}
              </div>
            </div>
          )}

          <div>
            <Label>Eligible staff</Label>
            <div className="flex flex-wrap gap-2">
              {members.map((member) => (
                <label key={member.user_id} className="flex items-center gap-1.5 rounded-full border border-surface-border px-2.5 py-1 text-xs text-ink">
                  <input
                    type="checkbox"
                    checked={eligibleUserIds.includes(member.user_id)}
                    onChange={(e) =>
                      setEligibleUserIds((prev) => (e.target.checked ? [...prev, member.user_id] : prev.filter((id) => id !== member.user_id)))
                    }
                  />
                  {member.first_name} {member.last_name}
                </label>
              ))}
            </div>
          </div>

          <Button type="submit" disabled={createRule.isPending || !name || eligibleUserIds.length === 0}>
            {createRule.isPending ? "Adding…" : "Add rule"}
          </Button>
        </form>
        {createRule.isError && (
          <div className="mt-3">
            <Alert tone="error">{createRule.error instanceof ApiError ? createRule.error.message : "Unable to add rule."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Rules" />
        <div className="space-y-2">
          {rulesQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No assignment rules yet — new leads stay unassigned.</p>}
          {rulesQuery.data?.map((rule) => (
            <div key={rule.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
              <div>
                <p className="font-medium text-ink">{rule.name}</p>
                <p className="text-xs text-ink-faint">
                  {STRATEGIES.find((s) => s.value === rule.strategy)?.label} · {rule.eligible_user_ids.map(memberName).join(", ") || "no eligible staff"}
                </p>
              </div>
              <Button variant="secondary" onClick={() => toggleRule.mutate({ id: rule.id, is_active: !rule.is_active })}>
                {rule.is_active ? "Deactivate" : "Activate"}
              </Button>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
