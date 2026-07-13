"use client";

import { Alert, Badge, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError, apiFetch } from "@/lib/api-client";
import type { PlatformTenantOut } from "@/lib/types";

interface TenantCreateValues {
  name: string;
  slug: string;
  timezone: string;
  currency: string;
  owner_email: string;
  owner_first_name: string;
  owner_last_name: string;
  owner_password: string;
}

const STATUS_TONE: Record<string, "success" | "warning" | "danger"> = {
  active: "success",
  suspended: "warning",
  archived: "danger",
};

export default function PlatformTenantsPage() {
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);

  const tenantsQuery = useQuery({
    queryKey: ["platform-tenants"],
    queryFn: () => apiFetch<PlatformTenantOut[]>("/platform/tenants", { withTenant: false }),
  });

  const { register, handleSubmit, reset, formState } = useForm<TenantCreateValues>({
    defaultValues: {
      name: "",
      slug: "",
      timezone: "Asia/Dubai",
      currency: "AED",
      owner_email: "",
      owner_first_name: "",
      owner_last_name: "",
      owner_password: "",
    },
  });

  const createMutation = useMutation({
    mutationFn: (values: TenantCreateValues) =>
      apiFetch<PlatformTenantOut>("/platform/tenants", {
        method: "POST",
        withTenant: false,
        body: { ...values, legal_name: null },
      }),
    onSuccess: () => {
      reset();
      queryClient.invalidateQueries({ queryKey: ["platform-tenants"] });
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Tenants</h1>
      <p className="mb-6 text-sm text-surface-400">Every workspace on the platform.</p>

      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}

      <Card className="mb-6">
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Create a tenant</h2>
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
              <Label htmlFor="t-name">Business name</Label>
              <Input id="t-name" {...register("name", { required: true })} />
              <FormError message={formState.errors.name ? "Name is required" : undefined} />
            </div>
            <div>
              <Label htmlFor="t-slug">Slug</Label>
              <Input id="t-slug" {...register("slug", { required: true })} />
              <FormError message={formState.errors.slug ? "Slug is required" : undefined} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="t-timezone">Timezone</Label>
              <Input id="t-timezone" {...register("timezone")} />
            </div>
            <div>
              <Label htmlFor="t-currency">Currency</Label>
              <Input id="t-currency" {...register("currency")} />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label htmlFor="t-owner-first">Owner first name</Label>
              <Input id="t-owner-first" {...register("owner_first_name", { required: true })} />
            </div>
            <div>
              <Label htmlFor="t-owner-last">Owner last name</Label>
              <Input id="t-owner-last" {...register("owner_last_name", { required: true })} />
            </div>
            <div>
              <Label htmlFor="t-owner-email">Owner email</Label>
              <Input id="t-owner-email" type="email" {...register("owner_email", { required: true })} />
            </div>
          </div>
          <div>
            <Label htmlFor="t-owner-password">Owner temporary password</Label>
            <Input
              id="t-owner-password"
              type="password"
              {...register("owner_password", { required: true, minLength: 8 })}
            />
            <FormError
              message={formState.errors.owner_password ? "At least 8 characters" : undefined}
            />
          </div>
          <Button type="submit" loading={createMutation.isPending}>
            Create tenant
          </Button>
        </form>
      </Card>

      <Card>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-800 text-surface-500">
              <th className="pb-2 font-medium">Name</th>
              <th className="pb-2 font-medium">Slug</th>
              <th className="pb-2 font-medium">Status</th>
              <th className="pb-2 font-medium">Currency</th>
              <th className="pb-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {tenantsQuery.data?.map((tenant) => (
              <tr key={tenant.id} className="border-b border-surface-900">
                <td className="py-2 text-surface-200">{tenant.name}</td>
                <td className="py-2 text-surface-400">{tenant.slug}</td>
                <td className="py-2">
                  <Badge tone={STATUS_TONE[tenant.status] ?? "neutral"}>{tenant.status}</Badge>
                </td>
                <td className="py-2 text-surface-400">{tenant.currency}</td>
                <td className="py-2">
                  <Link
                    href={`/platform/tenants/${tenant.id}`}
                    className="text-accent-500 hover:text-accent-400"
                  >
                    View
                  </Link>
                </td>
              </tr>
            ))}
            {tenantsQuery.data && tenantsQuery.data.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-4 text-center text-surface-500">
                  No tenants yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
