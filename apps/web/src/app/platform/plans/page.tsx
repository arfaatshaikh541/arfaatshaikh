"use client";

import { Alert, Badge, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError, apiFetch } from "@/lib/api-client";
import type { SubscriptionPlanOut } from "@/lib/types";

interface PlanFormValues {
  code: string;
  name: string;
  price_cents: number;
  currency: string;
  features: string;
}

export default function PlatformPlansPage() {
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);

  const plansQuery = useQuery({
    queryKey: ["platform-plans"],
    queryFn: () => apiFetch<SubscriptionPlanOut[]>("/platform/plans", { withTenant: false }),
  });

  const { register, handleSubmit, reset, formState } = useForm<PlanFormValues>({
    defaultValues: { code: "", name: "", price_cents: 0, currency: "AED", features: "" },
  });

  const createMutation = useMutation({
    mutationFn: (values: PlanFormValues) =>
      apiFetch<SubscriptionPlanOut>("/platform/plans", {
        method: "POST",
        withTenant: false,
        body: {
          code: values.code,
          name: values.name,
          price_cents: values.price_cents,
          currency: values.currency,
          features: values.features
            .split(",")
            .map((f) => f.trim())
            .filter(Boolean),
        },
      }),
    onSuccess: () => {
      reset();
      queryClient.invalidateQueries({ queryKey: ["platform-plans"] });
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiFetch<SubscriptionPlanOut>(`/platform/plans/${id}`, {
        method: "PATCH",
        withTenant: false,
        body: { is_active },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["platform-plans"] }),
  });

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Subscription plans</h1>
      <p className="mb-6 text-sm text-surface-400">
        The platform-wide plan catalog. Deactivating a plan doesn&apos;t affect tenants already on it.
      </p>

      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}

      <Card className="mb-6">
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Add a plan</h2>
        <form
          onSubmit={handleSubmit((values) => {
            setServerError(null);
            createMutation.mutate(values);
          })}
          className="space-y-3"
          noValidate
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="plan-code">Code</Label>
              <Input id="plan-code" {...register("code", { required: true })} />
              <FormError message={formState.errors.code ? "Code is required" : undefined} />
            </div>
            <div>
              <Label htmlFor="plan-name">Name</Label>
              <Input id="plan-name" {...register("name", { required: true })} />
              <FormError message={formState.errors.name ? "Name is required" : undefined} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="plan-price">Price (in cents)</Label>
              <Input
                id="plan-price"
                type="number"
                {...register("price_cents", { required: true, valueAsNumber: true, min: 0 })}
              />
            </div>
            <div>
              <Label htmlFor="plan-currency">Currency</Label>
              <Input id="plan-currency" {...register("currency")} />
            </div>
          </div>
          <div>
            <Label htmlFor="plan-features">Features (comma-separated)</Label>
            <Input id="plan-features" placeholder="leads, pipeline, reporting" {...register("features")} />
          </div>
          <Button type="submit" loading={createMutation.isPending}>
            Add plan
          </Button>
        </form>
      </Card>

      <Card>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-800 text-surface-500">
              <th className="pb-2 font-medium">Code</th>
              <th className="pb-2 font-medium">Name</th>
              <th className="pb-2 font-medium">Price</th>
              <th className="pb-2 font-medium">Features</th>
              <th className="pb-2 font-medium">Status</th>
              <th className="pb-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {plansQuery.data?.map((plan) => (
              <tr key={plan.id} className="border-b border-surface-900">
                <td className="py-2 text-surface-200">{plan.code}</td>
                <td className="py-2 text-surface-200">{plan.name}</td>
                <td className="py-2 text-surface-400">
                  {(plan.price_cents / 100).toFixed(2)} {plan.currency}
                </td>
                <td className="py-2 text-surface-400">{plan.features.join(", ") || "—"}</td>
                <td className="py-2">
                  <Badge tone={plan.is_active ? "success" : "neutral"}>
                    {plan.is_active ? "active" : "inactive"}
                  </Badge>
                </td>
                <td className="py-2">
                  <Button
                    variant="ghost"
                    onClick={() => toggleMutation.mutate({ id: plan.id, is_active: !plan.is_active })}
                  >
                    {plan.is_active ? "Deactivate" : "Activate"}
                  </Button>
                </td>
              </tr>
            ))}
            {plansQuery.data && plansQuery.data.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-4 text-center text-surface-500">
                  No plans yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
