"use client";

import { Alert, Badge, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { ServiceOut } from "@/lib/types";

interface ServiceFormValues {
  name: string;
  description: string;
}

export default function ServicesPage() {
  const { tenantId, membership } = useCurrentTenant();
  const queryClient = useQueryClient();
  const canManage = membership?.role.permissions.some((p) => p.code === "settings.manage") ?? false;
  const [serverError, setServerError] = useState<string | null>(null);

  const servicesQuery = useQuery({
    queryKey: ["services", tenantId],
    queryFn: () => apiFetch<ServiceOut[]>("/tenants/me/services"),
    enabled: Boolean(tenantId),
  });

  const { register, handleSubmit, reset, formState } = useForm<ServiceFormValues>({
    defaultValues: { name: "", description: "" },
  });

  const createMutation = useMutation({
    mutationFn: (values: ServiceFormValues) =>
      apiFetch<ServiceOut>("/tenants/me/services", {
        method: "POST",
        body: { name: values.name, description: values.description || null },
      }),
    onSuccess: () => {
      reset({ name: "", description: "" });
      queryClient.invalidateQueries({ queryKey: ["services", tenantId] });
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiFetch<ServiceOut>(`/tenants/me/services/${id}`, { method: "PATCH", body: { is_active } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["services", tenantId] }),
  });

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Services</h1>
      <p className="mb-6 text-sm text-surface-400">
        Services offered by this workspace. Used on the public enquiry form and when creating leads.
      </p>

      {canManage ? (
        <Card className="mb-6">
          <h2 className="mb-4 text-sm font-semibold text-surface-100">Add a service</h2>
          {serverError ? (
            <Alert tone="error" className="mb-4">
              {serverError}
            </Alert>
          ) : null}
          <form
            onSubmit={handleSubmit((values) => {
              setServerError(null);
              createMutation.mutate(values);
            })}
            className="flex flex-wrap items-end gap-3"
            noValidate
          >
            <div>
              <Label htmlFor="service-name">Name</Label>
              <Input id="service-name" className="w-64" {...register("name", { required: true })} />
              <FormError message={formState.errors.name ? "Name is required" : undefined} />
            </div>
            <div>
              <Label htmlFor="service-description">Description (optional)</Label>
              <Input id="service-description" className="w-72" {...register("description")} />
            </div>
            <Button type="submit" loading={createMutation.isPending}>
              Add service
            </Button>
          </form>
        </Card>
      ) : null}

      <Card>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-800 text-surface-500">
              <th className="pb-2 font-medium">Name</th>
              <th className="pb-2 font-medium">Description</th>
              <th className="pb-2 font-medium">Status</th>
              {canManage ? <th className="pb-2 font-medium">Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {servicesQuery.data?.map((service) => (
              <tr key={service.id} className="border-b border-surface-900">
                <td className="py-2 text-surface-200">{service.name}</td>
                <td className="py-2 text-surface-400">{service.description ?? "—"}</td>
                <td className="py-2">
                  <Badge tone={service.is_active ? "success" : "neutral"}>
                    {service.is_active ? "active" : "inactive"}
                  </Badge>
                </td>
                {canManage ? (
                  <td className="py-2">
                    <Button
                      variant="ghost"
                      onClick={() =>
                        toggleMutation.mutate({ id: service.id, is_active: !service.is_active })
                      }
                    >
                      {service.is_active ? "Deactivate" : "Activate"}
                    </Button>
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
