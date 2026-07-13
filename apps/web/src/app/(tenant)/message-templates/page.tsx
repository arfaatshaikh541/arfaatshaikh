"use client";

import { Alert, Badge, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { MessageTemplateOut } from "@/lib/types";

const TEMPLATE_KEYS = [
  "acknowledgement",
  "assignment_alert",
  "appointment_confirmation",
  "appointment_reminder",
  "follow_up",
];

interface EditFormValues {
  subject: string;
  body: string;
}

function TemplateEditor({
  template,
  canManage,
}: {
  template: MessageTemplateOut;
  canManage: boolean;
}) {
  const { tenantId } = useCurrentTenant();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const { register, handleSubmit, reset } = useForm<EditFormValues>({
    defaultValues: { subject: template.subject, body: template.body },
  });

  const updateMutation = useMutation({
    mutationFn: (values: EditFormValues) =>
      apiFetch<MessageTemplateOut>(`/tenants/me/message-templates/${template.id}`, {
        method: "PATCH",
        body: values,
      }),
    onSuccess: () => {
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["message-templates", tenantId] });
    },
  });

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-surface-100">{template.key}</h3>
          <Badge tone={template.is_active ? "success" : "neutral"} className="mt-1">
            {template.is_active ? "active" : "inactive"}
          </Badge>
        </div>
        {canManage ? (
          <Button variant="ghost" onClick={() => setEditing((v) => !v)}>
            {editing ? "Cancel" : "Edit"}
          </Button>
        ) : null}
      </div>
      {editing ? (
        <form
          onSubmit={handleSubmit((values) => updateMutation.mutate(values))}
          className="space-y-3"
          noValidate
        >
          <div>
            <Label htmlFor={`subject-${template.id}`}>Subject</Label>
            <Input id={`subject-${template.id}`} {...register("subject", { required: true })} />
          </div>
          <div>
            <Label htmlFor={`body-${template.id}`}>Body</Label>
            <textarea
              id={`body-${template.id}`}
              rows={5}
              className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
              {...register("body", { required: true })}
            />
            <p className="mt-1 text-xs text-surface-500">
              Use <code>{"{{first_name}}"}</code>, <code>{"{{tenant_name}}"}</code>,{" "}
              <code>{"{{lead_name}}"}</code> etc. Unknown variables render blank - there is no
              code execution in template rendering.
            </p>
          </div>
          <Button type="submit" loading={updateMutation.isPending}>
            Save
          </Button>
        </form>
      ) : (
        <div className="space-y-1 text-sm">
          <p className="text-surface-200">{template.subject}</p>
          <p className="whitespace-pre-wrap text-surface-400">{template.body}</p>
        </div>
      )}
    </Card>
  );
}

export default function MessageTemplatesPage() {
  const { tenantId, membership } = useCurrentTenant();
  const queryClient = useQueryClient();
  const canManage = membership?.role.permissions.some((p) => p.code === "templates.manage") ?? false;
  const [serverError, setServerError] = useState<string | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["message-templates", tenantId],
    queryFn: () => apiFetch<MessageTemplateOut[]>("/tenants/me/message-templates"),
    enabled: Boolean(tenantId) && canManage,
  });

  const { register, handleSubmit, reset, formState } = useForm<{
    key: string;
    subject: string;
    body: string;
  }>({
    defaultValues: { key: TEMPLATE_KEYS[0], subject: "", body: "" },
  });

  const createMutation = useMutation({
    mutationFn: (values: { key: string; subject: string; body: string }) =>
      apiFetch<MessageTemplateOut>("/tenants/me/message-templates", { method: "POST", body: values }),
    onSuccess: () => {
      reset();
      queryClient.invalidateQueries({ queryKey: ["message-templates", tenantId] });
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  if (!canManage) {
    return (
      <Alert tone="info">
        You don&apos;t have permission to manage message templates. Ask an Owner or Administrator.
      </Alert>
    );
  }

  const existingKeys = new Set((templatesQuery.data ?? []).map((t) => t.key));
  const missingKeys = TEMPLATE_KEYS.filter((k) => !existingKeys.has(k));

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Message templates</h1>
      <p className="mb-6 text-sm text-surface-400">
        Automated acknowledgement, assignment-alert and follow-up emails are rendered from these
        templates. A key without a customized template falls back to a built-in default.
      </p>

      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}

      {missingKeys.length > 0 ? (
        <Card className="mb-6">
          <h2 className="mb-4 text-sm font-semibold text-surface-100">Create a custom template</h2>
          <form
            onSubmit={handleSubmit((values) => {
              setServerError(null);
              createMutation.mutate(values);
            })}
            className="space-y-3"
            noValidate
          >
            <div>
              <Label htmlFor="template-key">Key</Label>
              <select
                id="template-key"
                className="w-64 rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                {...register("key")}
              >
                {missingKeys.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="template-subject">Subject</Label>
              <Input id="template-subject" {...register("subject", { required: true })} />
              <FormError message={formState.errors.subject ? "Subject is required" : undefined} />
            </div>
            <div>
              <Label htmlFor="template-body">Body</Label>
              <textarea
                id="template-body"
                rows={4}
                className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                {...register("body", { required: true })}
              />
            </div>
            <Button type="submit" loading={createMutation.isPending}>
              Create template
            </Button>
          </form>
        </Card>
      ) : null}

      <div className="space-y-4">
        {templatesQuery.data?.map((template) => (
          <TemplateEditor key={template.id} template={template} canManage={canManage} />
        ))}
        {templatesQuery.data && templatesQuery.data.length === 0 ? (
          <p className="text-sm text-surface-500">
            No custom templates yet - built-in defaults are used for every message key.
          </p>
        ) : null}
      </div>
    </div>
  );
}
