"use client";

import { Alert, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { LeadDetailOut, ServiceOut } from "@/lib/types";

interface NewLeadValues {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  company: string;
  service_id: string;
  estimated_value: string;
}

export default function NewLeadPage() {
  const { tenantId } = useCurrentTenant();
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);

  const servicesQuery = useQuery({
    queryKey: ["services", tenantId],
    queryFn: () => apiFetch<ServiceOut[]>("/tenants/me/services"),
    enabled: Boolean(tenantId),
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<NewLeadValues>();

  const onSubmit = async (values: NewLeadValues) => {
    setServerError(null);
    try {
      const lead = await apiFetch<LeadDetailOut>("/tenants/me/leads", {
        method: "POST",
        body: {
          first_name: values.first_name,
          last_name: values.last_name || "",
          email: values.email || null,
          phone: values.phone || null,
          company: values.company || null,
          service_id: values.service_id || null,
          estimated_value: values.estimated_value ? Number(values.estimated_value) : null,
          consent_given: true,
        },
      });
      router.push(`/leads/${lead.id}`);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  return (
    <div className="max-w-xl">
      <h1 className="mb-6 text-xl font-semibold text-surface-50">New lead</h1>
      <Card>
        {serverError ? (
          <Alert tone="error" className="mb-4">
            {serverError}
          </Alert>
        ) : null}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="first_name">First name</Label>
              <Input id="first_name" {...register("first_name", { required: true })} />
              <FormError message={errors.first_name ? "First name is required" : undefined} />
            </div>
            <div>
              <Label htmlFor="last_name">Last name</Label>
              <Input id="last_name" {...register("last_name")} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" {...register("email")} />
            </div>
            <div>
              <Label htmlFor="phone">Phone</Label>
              <Input id="phone" {...register("phone")} />
            </div>
          </div>
          <div>
            <Label htmlFor="company">Company</Label>
            <Input id="company" {...register("company")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="service_id">Service</Label>
              <select
                id="service_id"
                className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                {...register("service_id")}
              >
                <option value="">None</option>
                {servicesQuery.data?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="estimated_value">Estimated value (AED)</Label>
              <Input id="estimated_value" type="number" {...register("estimated_value")} />
            </div>
          </div>
          <Button type="submit" loading={isSubmitting}>
            Create lead
          </Button>
        </form>
      </Card>
    </div>
  );
}
