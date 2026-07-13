"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { tenantSettingsSchema, type TenantSettingsInput } from "@leadflow/shared-types";
import { Alert, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError, apiFetch } from "@/lib/api-client";
import { useCurrentTenant } from "@/hooks/useCurrentTenant";

interface TenantOut {
  id: string;
  slug: string;
  public_key: string;
  name: string;
}

interface TenantSettingsOut {
  logo_url: string | null;
  brand_primary_color: string;
  brand_secondary_color: string;
  contact_email: string | null;
  contact_phone: string | null;
  business_hours: Record<string, unknown>;
  locale: string;
  data_retention_days: number;
  privacy_text: string | null;
}

export default function SettingsPage() {
  const { tenantId, membership } = useCurrentTenant();
  const queryClient = useQueryClient();
  const canManageSettings = membership?.role.permissions.some((p) => p.code === "settings.manage") ?? false;
  const [serverError, setServerError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const settingsQuery = useQuery({
    queryKey: ["tenant-settings", tenantId],
    queryFn: () => apiFetch<TenantSettingsOut>("/tenants/me/settings"),
    enabled: Boolean(tenantId),
  });
  const tenantQuery = useQuery({
    queryKey: ["tenant", tenantId],
    queryFn: () => apiFetch<TenantOut>("/tenants/me"),
    enabled: Boolean(tenantId),
  });
  const publicFormUrl =
    typeof window !== "undefined" && tenantQuery.data
      ? `${window.location.origin}/enquire/${tenantQuery.data.public_key}`
      : "";

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<TenantSettingsInput>({ resolver: zodResolver(tenantSettingsSchema) });

  useEffect(() => {
    if (!settingsQuery.data) return;
    reset({
      logoUrl: settingsQuery.data.logo_url ?? "",
      brandPrimaryColor: settingsQuery.data.brand_primary_color,
      brandSecondaryColor: settingsQuery.data.brand_secondary_color,
      contactEmail: settingsQuery.data.contact_email ?? "",
      contactPhone: settingsQuery.data.contact_phone ?? "",
      locale: settingsQuery.data.locale,
      dataRetentionDays: settingsQuery.data.data_retention_days,
      privacyText: settingsQuery.data.privacy_text ?? "",
    });
  }, [reset, settingsQuery.data]);

  const mutation = useMutation({
    mutationFn: (values: TenantSettingsInput) =>
      apiFetch<TenantSettingsOut>("/tenants/me/settings", {
        method: "PATCH",
        body: {
          logo_url: values.logoUrl || null,
          brand_primary_color: values.brandPrimaryColor,
          brand_secondary_color: values.brandSecondaryColor,
          contact_email: values.contactEmail || null,
          contact_phone: values.contactPhone || null,
          locale: values.locale,
          data_retention_days: values.dataRetentionDays,
          privacy_text: values.privacyText || null,
        },
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["tenant-settings", tenantId], data);
      setSavedAt(Date.now());
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const onSubmit = (values: TenantSettingsInput) => {
    setServerError(null);
    mutation.mutate(values);
  };

  if (settingsQuery.isLoading) {
    return <p className="text-sm text-surface-400">Loading…</p>;
  }

  return (
    <div className="max-w-2xl">
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Workspace settings</h1>
      <p className="mb-6 text-sm text-surface-400">
        Business identity, branding and contact details for this workspace.
      </p>

      {!canManageSettings ? (
        <Alert tone="info" className="mb-4">
          You have read-only access to settings. Ask an Owner or Administrator to make changes.
        </Alert>
      ) : null}
      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}
      {savedAt ? (
        <Alert tone="success" className="mb-4">
          Settings saved.
        </Alert>
      ) : null}

      <Card className="mb-6">
        <h2 className="mb-2 text-sm font-semibold text-surface-100">Public enquiry form</h2>
        <p className="mb-3 text-sm text-surface-400">
          Share this link, or embed it on your website, so visitors can submit enquiries directly
          into your pipeline.
        </p>
        <div className="flex gap-2">
          <Input readOnly value={publicFormUrl} className="flex-1 font-mono text-xs" />
          {publicFormUrl ? (
            <a href={publicFormUrl} target="_blank" rel="noreferrer">
              <Button variant="secondary">Open</Button>
            </a>
          ) : null}
        </div>
      </Card>

      <Card>
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <fieldset disabled={!canManageSettings} className="space-y-4 disabled:opacity-70">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="brandPrimaryColor">Brand primary color</Label>
                <Input id="brandPrimaryColor" {...register("brandPrimaryColor")} />
                <FormError message={errors.brandPrimaryColor?.message} />
              </div>
              <div>
                <Label htmlFor="brandSecondaryColor">Brand secondary color</Label>
                <Input id="brandSecondaryColor" {...register("brandSecondaryColor")} />
                <FormError message={errors.brandSecondaryColor?.message} />
              </div>
            </div>
            <div>
              <Label htmlFor="logoUrl">Logo URL</Label>
              <Input id="logoUrl" placeholder="https://…" {...register("logoUrl")} />
              <FormError message={errors.logoUrl?.message} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="contactEmail">Contact email</Label>
                <Input id="contactEmail" type="email" {...register("contactEmail")} />
                <FormError message={errors.contactEmail?.message} />
              </div>
              <div>
                <Label htmlFor="contactPhone">Contact phone</Label>
                <Input id="contactPhone" {...register("contactPhone")} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="locale">Locale</Label>
                <Input id="locale" {...register("locale")} />
                <FormError message={errors.locale?.message} />
              </div>
              <div>
                <Label htmlFor="dataRetentionDays">Data retention (days)</Label>
                <Input
                  id="dataRetentionDays"
                  type="number"
                  {...register("dataRetentionDays", { valueAsNumber: true })}
                />
                <FormError message={errors.dataRetentionDays?.message} />
              </div>
            </div>
            <div>
              <Label htmlFor="privacyText">Privacy notice text</Label>
              <textarea
                id="privacyText"
                rows={4}
                className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50 placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-accent-500"
                {...register("privacyText")}
              />
            </div>
            {canManageSettings ? (
              <Button type="submit" loading={isSubmitting || mutation.isPending}>
                Save changes
              </Button>
            ) : null}
          </fieldset>
        </form>
      </Card>
    </div>
  );
}
