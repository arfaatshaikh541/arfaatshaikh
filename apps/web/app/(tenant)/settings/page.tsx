"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";

interface TenantSettings {
  tenant_id: string;
  timezone: string;
  currency: string;
  branding: Record<string, unknown>;
  business_hours: Record<string, unknown>;
}

const schema = z.object({
  timezone: z.string().min(1),
  currency: z.string().length(3),
});
type FormValues = z.infer<typeof schema>;

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["tenant", "settings"],
    queryFn: () => api.get<TenantSettings>("/tenant/settings"),
  });

  const { register, handleSubmit, reset } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (data) reset({ timezone: data.timezone, currency: data.currency });
  }, [data, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => api.patch<TenantSettings>("/tenant/settings", values),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "settings"] }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Settings</h1>
        <p className="mt-1 text-sm text-ink-muted">Workspace-wide configuration.</p>
      </div>

      <Card>
        <CardHeader title="Regional settings" />
        {isLoading && <p className="text-sm text-ink-muted">Loading…</p>}
        {!isLoading && (
          <form className="max-w-sm space-y-4" onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
            {mutation.isError && (
              <Alert tone="error">
                {mutation.error instanceof ApiError ? mutation.error.message : "Unable to save settings."}
              </Alert>
            )}
            {mutation.isSuccess && <Alert tone="success">Settings saved.</Alert>}
            <div>
              <Label htmlFor="timezone">Timezone</Label>
              <Input id="timezone" {...register("timezone")} />
            </div>
            <div>
              <Label htmlFor="currency">Currency</Label>
              <Input id="currency" maxLength={3} {...register("currency")} />
            </div>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save changes"}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}
