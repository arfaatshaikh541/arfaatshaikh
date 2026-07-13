"use client";

import { Alert, Badge, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { AssignmentRuleOut, MemberOut, ServiceOut } from "@/lib/types";
import { ASSIGNMENT_STRATEGIES } from "@/lib/types";

const TYPES_WITH_MEMBERS = new Set(["round_robin", "service_based", "branch_based", "priority_based"]);
const TYPES_WITH_SERVICE = new Set(["service_based"]);
const TYPES_WITH_PRIORITY = new Set(["priority_based"]);

interface RuleFormValues {
  name: string;
  strategy: string;
  member_ids: string[];
  service_id: string;
  priority: string;
  fallback_membership_id: string;
}

export default function AssignmentPage() {
  const { tenantId, membership } = useCurrentTenant();
  const queryClient = useQueryClient();
  const canManage = membership?.role.permissions.some((p) => p.code === "assignment.manage") ?? false;
  const [serverError, setServerError] = useState<string | null>(null);

  const rulesQuery = useQuery({
    queryKey: ["assignment-rules", tenantId],
    queryFn: () => apiFetch<AssignmentRuleOut[]>("/tenants/me/assignment-rules"),
    enabled: Boolean(tenantId),
  });
  const membersQuery = useQuery({
    queryKey: ["members", tenantId],
    queryFn: () => apiFetch<MemberOut[]>("/tenants/me/members"),
    enabled: Boolean(tenantId),
  });
  const servicesQuery = useQuery({
    queryKey: ["services", tenantId],
    queryFn: () => apiFetch<ServiceOut[]>("/tenants/me/services"),
    enabled: Boolean(tenantId) && canManage,
  });

  const { register, handleSubmit, reset, watch, formState } = useForm<RuleFormValues>({
    defaultValues: {
      name: "",
      strategy: "round_robin",
      member_ids: [],
      service_id: "",
      priority: "hot",
      fallback_membership_id: "",
    },
  });
  const strategy = watch("strategy");

  const membersById = new Map((membersQuery.data ?? []).map((m) => [m.id, m]));

  const createRuleMutation = useMutation({
    mutationFn: (values: RuleFormValues) => {
      let config: Record<string, unknown> = {};
      if (TYPES_WITH_MEMBERS.has(values.strategy)) config = { membership_ids: values.member_ids };
      if (TYPES_WITH_SERVICE.has(values.strategy)) config = { ...config, service_id: values.service_id };
      if (TYPES_WITH_PRIORITY.has(values.strategy)) config = { ...config, priority: values.priority };
      return apiFetch<AssignmentRuleOut>("/tenants/me/assignment-rules", {
        method: "POST",
        body: {
          name: values.name,
          strategy: values.strategy,
          config,
          fallback_membership_id:
            values.strategy === "manual_fallback" ? values.fallback_membership_id || null : null,
        },
      });
    },
    onSuccess: () => {
      reset();
      queryClient.invalidateQueries({ queryKey: ["assignment-rules", tenantId] });
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const toggleRuleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiFetch<AssignmentRuleOut>(`/tenants/me/assignment-rules/${id}`, {
        method: "PATCH",
        body: { is_active },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assignment-rules", tenantId] }),
  });

  const describeConfig = (rule: AssignmentRuleOut): string => {
    if (rule.strategy === "manual_fallback") {
      const fallback = rule.fallback_membership_id ? membersById.get(rule.fallback_membership_id) : null;
      return fallback ? `Fallback to ${fallback.first_name} ${fallback.last_name}` : "No fallback set";
    }
    const ids = (rule.config.membership_ids as string[] | undefined) ?? [];
    const names = ids
      .map((id) => membersById.get(id))
      .filter(Boolean)
      .map((m) => `${m!.first_name} ${m!.last_name}`);
    return names.length > 0 ? names.join(", ") : "No members configured";
  };

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Lead assignment</h1>
      <p className="mb-6 text-sm text-surface-400">
        Active rules run in order for every new lead; the first rule with a matching, active
        candidate wins. A manual-fallback rule catches anything the rules above didn&apos;t match.
      </p>

      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}

      {canManage ? (
        <Card className="mb-6">
          <h2 className="mb-4 text-sm font-semibold text-surface-100">Add an assignment rule</h2>
          <form
            onSubmit={handleSubmit((values) => {
              setServerError(null);
              createRuleMutation.mutate(values);
            })}
            className="space-y-3"
            noValidate
          >
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="assign-name">Name</Label>
                <Input id="assign-name" {...register("name", { required: true })} />
                <FormError message={formState.errors.name ? "Name is required" : undefined} />
              </div>
              <div>
                <Label htmlFor="assign-strategy">Strategy</Label>
                <select
                  id="assign-strategy"
                  className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                  {...register("strategy")}
                >
                  {ASSIGNMENT_STRATEGIES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {TYPES_WITH_SERVICE.has(strategy) ? (
              <div>
                <Label htmlFor="assign-service">Service</Label>
                <select
                  id="assign-service"
                  className="w-64 rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                  {...register("service_id")}
                >
                  <option value="">Select a service…</option>
                  {servicesQuery.data?.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            {TYPES_WITH_PRIORITY.has(strategy) ? (
              <div>
                <Label htmlFor="assign-priority">Priority</Label>
                <select
                  id="assign-priority"
                  className="w-48 rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                  {...register("priority")}
                >
                  <option value="hot">Hot</option>
                  <option value="warm">Warm</option>
                  <option value="standard">Standard</option>
                  <option value="low_priority">Low priority</option>
                </select>
              </div>
            ) : null}

            {TYPES_WITH_MEMBERS.has(strategy) ? (
              <div>
                <Label>Candidates</Label>
                <div className="flex flex-wrap gap-3 rounded-md border border-surface-800 p-3">
                  {membersQuery.data?.map((m) => (
                    <label key={m.id} className="flex items-center gap-2 text-sm text-surface-300">
                      <input type="checkbox" value={m.id} {...register("member_ids")} />
                      {m.first_name} {m.last_name}
                    </label>
                  ))}
                  {membersQuery.data && membersQuery.data.length === 0 ? (
                    <p className="text-sm text-surface-500">No active members.</p>
                  ) : null}
                </div>
              </div>
            ) : null}

            {strategy === "manual_fallback" ? (
              <div>
                <Label htmlFor="assign-fallback">Fallback assignee</Label>
                <select
                  id="assign-fallback"
                  className="w-64 rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                  {...register("fallback_membership_id")}
                >
                  <option value="">Select a member…</option>
                  {membersQuery.data?.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.first_name} {m.last_name}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            <Button type="submit" loading={createRuleMutation.isPending}>
              Add rule
            </Button>
          </form>
        </Card>
      ) : null}

      <Card>
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Rules</h2>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-800 text-surface-500">
              <th className="pb-2 font-medium">Name</th>
              <th className="pb-2 font-medium">Strategy</th>
              <th className="pb-2 font-medium">Candidates</th>
              <th className="pb-2 font-medium">Status</th>
              {canManage ? <th className="pb-2 font-medium">Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {rulesQuery.data?.map((rule) => (
              <tr key={rule.id} className="border-b border-surface-900">
                <td className="py-2 text-surface-200">{rule.name}</td>
                <td className="py-2 text-surface-400">{rule.strategy}</td>
                <td className="py-2 text-surface-400">{describeConfig(rule)}</td>
                <td className="py-2">
                  <Badge tone={rule.is_active ? "success" : "neutral"}>
                    {rule.is_active ? "active" : "inactive"}
                  </Badge>
                </td>
                {canManage ? (
                  <td className="py-2">
                    <Button
                      variant="ghost"
                      onClick={() =>
                        toggleRuleMutation.mutate({ id: rule.id, is_active: !rule.is_active })
                      }
                    >
                      {rule.is_active ? "Deactivate" : "Activate"}
                    </Button>
                  </td>
                ) : null}
              </tr>
            ))}
            {rulesQuery.data && rulesQuery.data.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-4 text-center text-surface-500">
                  No assignment rules yet - new leads stay unassigned.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
