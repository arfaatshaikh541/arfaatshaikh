"use client";

import Link from "next/link";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";

interface QualificationForm {
  id: string;
  name: string;
  service_id: string | null;
  is_active: boolean;
}

const schema = z.object({ name: z.string().min(1, "Form name is required.") });
type FormValues = z.infer<typeof schema>;

export default function QualificationFormsPage() {
  const queryClient = useQueryClient();
  const formsQuery = useQuery({
    queryKey: ["tenant", "qualification-forms"],
    queryFn: () => api.get<QualificationForm[]>("/tenant/qualification-forms"),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const createMutation = useMutation({
    mutationFn: (values: FormValues) => api.post("/tenant/qualification-forms", { name: values.name, service_id: null }),
    onSuccess: () => {
      reset();
      queryClient.invalidateQueries({ queryKey: ["tenant", "qualification-forms"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Qualification forms</h1>
        <p className="mt-1 text-sm text-ink-muted">
          The questions shown on your public enquiry form. A form without a specific service is used as the default.
        </p>
      </div>

      <Card>
        <CardHeader title="Create a form" />
        <form className="flex items-end gap-3" onSubmit={handleSubmit((values) => createMutation.mutate(values))} noValidate>
          <div className="min-w-[260px]">
            <Label htmlFor="name">Name</Label>
            <Input id="name" {...register("name")} />
            <FieldError>{errors.name?.message}</FieldError>
          </div>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Creating…" : "Create form"}
          </Button>
        </form>
        {createMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to create form."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Forms" />
        <div className="space-y-2">
          {formsQuery.data?.map((form) => (
            <Link
              key={form.id}
              href={`/qualification-forms/${form.id}`}
              className="block rounded-md border border-surface-border p-3 text-sm text-ink hover:border-accent/50"
            >
              {form.name} {!form.service_id && <span className="text-xs text-ink-faint">(default)</span>}
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}
