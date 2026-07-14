"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { TenantSummary } from "@/lib/types";

interface Plan {
  id: string;
  code: string;
  name: string;
}

const schema = z.object({
  name: z.string().min(1, "Company name is required."),
  slug: z.string().optional(),
  plan_code: z.string().min(1, "Select a plan."),
  owner_email: z.string().email("Enter a valid email address."),
  owner_first_name: z.string().min(1, "First name is required."),
  owner_last_name: z.string().min(1, "Last name is required."),
});
type FormValues = z.infer<typeof schema>;

const statusTone: Record<string, string> = {
  active: "text-emerald-400",
  suspended: "text-red-400",
  read_only: "text-amber-400",
  archived: "text-ink-faint",
};

export default function TenantsPage() {
  const [showForm, setShowForm] = useState(false);
  const queryClient = useQueryClient();
  const tenantsQuery = useQuery({ queryKey: ["platform", "tenants"], queryFn: () => api.get<TenantSummary[]>("/platform/tenants") });
  const plansQuery = useQuery({ queryKey: ["platform", "plans"], queryFn: () => api.get<Plan[]>("/platform/plans") });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const createMutation = useMutation({
    mutationFn: (values: FormValues) => api.post("/platform/tenants", values),
    onSuccess: () => {
      reset();
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["platform", "tenants"] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Tenants</h1>
          <p className="mt-1 text-sm text-ink-muted">Every company subscribed to the platform.</p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "Create tenant"}</Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader title="Create a new tenant" description="Provisions the workspace and its owner account." />
          <form className="space-y-4" onSubmit={handleSubmit((values) => createMutation.mutate(values))} noValidate>
            {createMutation.isError && (
              <Alert tone="error">
                {createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to create tenant."}
              </Alert>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="name">Company name</Label>
                <Input id="name" {...register("name")} />
                <FieldError>{errors.name?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="slug">Slug (optional)</Label>
                <Input id="slug" placeholder="auto-generated" {...register("slug")} />
              </div>
            </div>
            <div>
              <Label htmlFor="plan_code">Plan</Label>
              <select
                id="plan_code"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                {...register("plan_code")}
              >
                <option value="">Select a plan</option>
                {plansQuery.data?.map((plan) => (
                  <option key={plan.id} value={plan.code}>
                    {plan.name}
                  </option>
                ))}
              </select>
              <FieldError>{errors.plan_code?.message}</FieldError>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label htmlFor="owner_email">Owner email</Label>
                <Input id="owner_email" type="email" {...register("owner_email")} />
                <FieldError>{errors.owner_email?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="owner_first_name">Owner first name</Label>
                <Input id="owner_first_name" {...register("owner_first_name")} />
                <FieldError>{errors.owner_first_name?.message}</FieldError>
              </div>
              <div>
                <Label htmlFor="owner_last_name">Owner last name</Label>
                <Input id="owner_last_name" {...register("owner_last_name")} />
                <FieldError>{errors.owner_last_name?.message}</FieldError>
              </div>
            </div>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating…" : "Create tenant"}
            </Button>
          </form>
        </Card>
      )}

      <Card>
        {tenantsQuery.isLoading && <p className="text-sm text-ink-muted">Loading…</p>}
        {tenantsQuery.data && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-border text-ink-faint">
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Slug</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {tenantsQuery.data.map((tenant) => (
                <tr key={tenant.id} className="border-b border-surface-border/60">
                  <td className="py-2">
                    <Link href={`/admin/tenants/${tenant.id}`} className="text-ink hover:text-accent">
                      {tenant.name}
                    </Link>
                  </td>
                  <td className="py-2 text-ink-muted">{tenant.slug}</td>
                  <td className={`py-2 capitalize ${statusTone[tenant.status] ?? "text-ink"}`}>
                    {tenant.status.replace("_", " ")}
                  </td>
                  <td className="py-2 text-ink-muted">{new Date(tenant.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
