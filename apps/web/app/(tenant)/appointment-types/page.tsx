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
import type { AppointmentTypeItem } from "@/lib/types";

const schema = z.object({
  name: z.string().min(1, "Name is required."),
  description: z.string().optional(),
  duration_minutes: z.coerce.number().int().min(1).max(480),
});
type FormValues = z.infer<typeof schema>;

export default function AppointmentTypesPage() {
  const queryClient = useQueryClient();
  const typesQuery = useQuery({ queryKey: ["tenant", "appointment-types"], queryFn: () => api.get<AppointmentTypeItem[]>("/tenant/appointment-types") });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { duration_minutes: 30 } });

  const createMutation = useMutation({
    mutationFn: (values: FormValues) =>
      api.post("/tenant/appointment-types", { name: values.name, description: values.description ?? "", duration_minutes: values.duration_minutes }),
    onSuccess: () => {
      reset({ name: "", description: "", duration_minutes: 30 });
      queryClient.invalidateQueries({ queryKey: ["tenant", "appointment-types"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Appointment types</h1>
        <p className="mt-1 text-sm text-ink-muted">The consultation/callback types offered for booking, each with its own duration.</p>
      </div>

      <Card>
        <CardHeader title="Add an appointment type" />
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
          <div className="w-32">
            <Label htmlFor="duration_minutes">Duration (min)</Label>
            <Input id="duration_minutes" type="number" {...register("duration_minutes")} />
            <FieldError>{errors.duration_minutes?.message}</FieldError>
          </div>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Adding…" : "Add type"}
          </Button>
        </form>
        {createMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to add appointment type."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Current appointment types" />
        <div className="space-y-2">
          {typesQuery.data?.map((type) => (
            <div key={type.id} className="rounded-md border border-surface-border p-3">
              <p className="text-sm font-medium text-ink">
                {type.name} <span className="text-xs text-ink-faint">({type.duration_minutes} min)</span>
              </p>
              {type.description && <p className="mt-1 text-xs text-ink-muted">{type.description}</p>}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
