"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";

interface Service {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
}

const schema = z.object({
  name: z.string().min(1, "Service name is required."),
  description: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export default function ServicesPage() {
  const queryClient = useQueryClient();
  const servicesQuery = useQuery({ queryKey: ["tenant", "services"], queryFn: () => api.get<Service[]>("/tenant/services") });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const createMutation = useMutation({
    mutationFn: (values: FormValues) => api.post("/tenant/services", { name: values.name, description: values.description ?? "" }),
    onSuccess: () => {
      reset();
      queryClient.invalidateQueries({ queryKey: ["tenant", "services"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Services</h1>
        <p className="mt-1 text-sm text-ink-muted">The services offered on your public enquiry form.</p>
      </div>

      <Card>
        <CardHeader title="Add a service" />
        <form className="flex flex-wrap items-end gap-3" onSubmit={handleSubmit((values) => createMutation.mutate(values))} noValidate>
          <div className="min-w-[220px]">
            <Label htmlFor="name">Name</Label>
            <Input id="name" {...register("name")} />
            <FieldError>{errors.name?.message}</FieldError>
          </div>
          <div className="min-w-[280px] flex-1">
            <Label htmlFor="description">Description</Label>
            <Input id="description" {...register("description")} />
          </div>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Adding…" : "Add service"}
          </Button>
        </form>
        {createMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to add service."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Current services" />
        <div className="space-y-2">
          {servicesQuery.data?.map((service) => (
            <div key={service.id} className="rounded-md border border-surface-border p-3">
              <p className="text-sm font-medium text-ink">{service.name}</p>
              {service.description && <p className="mt-1 text-xs text-ink-muted">{service.description}</p>}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
