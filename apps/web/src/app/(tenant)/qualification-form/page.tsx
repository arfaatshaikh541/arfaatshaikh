"use client";

import { Alert, Badge, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { QualificationFormOut } from "@/lib/types";

const FIELD_TYPES = [
  ["short_text", "Short text"],
  ["long_text", "Long text"],
  ["email", "Email"],
  ["phone", "Phone"],
  ["number", "Number"],
  ["currency", "Currency"],
  ["date", "Date"],
  ["single_select", "Single select"],
  ["multi_select", "Multi select"],
  ["checkbox", "Checkbox"],
  ["yes_no", "Yes / No"],
] as const;

const SELECT_TYPES = new Set(["single_select", "multi_select"]);

interface QuestionFormValues {
  label: string;
  field_type: string;
  is_required: boolean;
  help_text: string;
  options: string;
}

export default function QualificationFormPage() {
  const { tenantId, membership } = useCurrentTenant();
  const queryClient = useQueryClient();
  const canManage = membership?.role.permissions.some((p) => p.code === "settings.manage") ?? false;
  const [serverError, setServerError] = useState<string | null>(null);

  const formQuery = useQuery({
    queryKey: ["qualification-form", tenantId],
    queryFn: () => apiFetch<QualificationFormOut>("/tenants/me/qualification-form"),
    enabled: Boolean(tenantId),
  });

  const { register, handleSubmit, reset, watch, formState } = useForm<QuestionFormValues>({
    defaultValues: { label: "", field_type: "short_text", is_required: false, help_text: "", options: "" },
  });
  const fieldType = watch("field_type");

  const addMutation = useMutation({
    mutationFn: (values: QuestionFormValues) =>
      apiFetch("/tenants/me/qualification-form/questions", {
        method: "POST",
        body: {
          label: values.label,
          field_type: values.field_type,
          is_required: values.is_required,
          help_text: values.help_text || null,
          options: SELECT_TYPES.has(values.field_type)
            ? values.options
                .split(",")
                .map((o) => o.trim())
                .filter(Boolean)
            : null,
        },
      }),
    onSuccess: () => {
      reset({ label: "", field_type: "short_text", is_required: false, help_text: "", options: "" });
      queryClient.invalidateQueries({ queryKey: ["qualification-form", tenantId] });
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const deactivateMutation = useMutation({
    mutationFn: (questionId: string) =>
      apiFetch(`/tenants/me/qualification-form/questions/${questionId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["qualification-form", tenantId] }),
  });

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Qualification form</h1>
      <p className="mb-6 text-sm text-surface-400">
        Questions asked on the public enquiry form. Deactivating a question preserves every answer
        already collected for it.
      </p>

      {canManage ? (
        <Card className="mb-6">
          <h2 className="mb-4 text-sm font-semibold text-surface-100">Add a question</h2>
          {serverError ? (
            <Alert tone="error" className="mb-4">
              {serverError}
            </Alert>
          ) : null}
          <form
            onSubmit={handleSubmit((values) => {
              setServerError(null);
              addMutation.mutate(values);
            })}
            className="space-y-3"
            noValidate
          >
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="q-label">Question label</Label>
                <Input id="q-label" {...register("label", { required: true })} />
                <FormError message={formState.errors.label ? "Label is required" : undefined} />
              </div>
              <div>
                <Label htmlFor="q-type">Field type</Label>
                <select
                  id="q-type"
                  className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
                  {...register("field_type")}
                >
                  {FIELD_TYPES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {SELECT_TYPES.has(fieldType) ? (
              <div>
                <Label htmlFor="q-options">Options (comma-separated)</Label>
                <Input id="q-options" placeholder="Mainland, Free Zone, Offshore" {...register("options")} />
              </div>
            ) : null}
            <div>
              <Label htmlFor="q-help">Help text (optional)</Label>
              <Input id="q-help" {...register("help_text")} />
            </div>
            <label className="flex items-center gap-2 text-sm text-surface-300">
              <input type="checkbox" {...register("is_required")} /> Required
            </label>
            <Button type="submit" loading={addMutation.isPending}>
              Add question
            </Button>
          </form>
        </Card>
      ) : null}

      <Card>
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Questions</h2>
        <div className="space-y-3">
          {formQuery.data?.questions.map((question, index) => (
            <div
              key={question.id}
              className="flex items-center justify-between rounded-md border border-surface-800 px-3 py-2"
            >
              <div>
                <p className="text-sm text-surface-100">
                  {index + 1}. {question.field_definition.label}
                  {question.is_required ? <span className="ml-1 text-accent-500">*</span> : null}
                </p>
                <p className="text-xs text-surface-500">
                  {question.field_definition.field_type}
                  {!question.is_active ? " · inactive" : ""}
                  {question.field_definition.options.length > 0
                    ? ` · options: ${question.field_definition.options.map((o) => o.label).join(", ")}`
                    : ""}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {!question.is_active ? <Badge tone="neutral">inactive</Badge> : null}
                {canManage && question.is_active ? (
                  <Button variant="ghost" onClick={() => deactivateMutation.mutate(question.id)}>
                    Deactivate
                  </Button>
                ) : null}
              </div>
            </div>
          ))}
          {formQuery.data && formQuery.data.questions.length === 0 ? (
            <p className="text-sm text-surface-500">No questions yet.</p>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
