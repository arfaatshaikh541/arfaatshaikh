"use client";

import { Alert, Badge, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { PipelineStageOut } from "@/lib/types";

interface StageFormValues {
  name: string;
  is_won: boolean;
  is_lost: boolean;
}

export default function PipelinePage() {
  const { tenantId, membership } = useCurrentTenant();
  const queryClient = useQueryClient();
  const canManage = membership?.role.permissions.some((p) => p.code === "settings.manage") ?? false;
  const [serverError, setServerError] = useState<string | null>(null);

  const stagesQuery = useQuery({
    queryKey: ["pipeline-stages", tenantId],
    queryFn: () => apiFetch<PipelineStageOut[]>("/tenants/me/pipeline-stages"),
    enabled: Boolean(tenantId),
  });

  const { register, handleSubmit, reset, formState } = useForm<StageFormValues>({
    defaultValues: { name: "", is_won: false, is_lost: false },
  });

  const createMutation = useMutation({
    mutationFn: (values: StageFormValues) =>
      apiFetch<PipelineStageOut>("/tenants/me/pipeline-stages", { method: "POST", body: values }),
    onSuccess: () => {
      reset({ name: "", is_won: false, is_lost: false });
      queryClient.invalidateQueries({ queryKey: ["pipeline-stages", tenantId] });
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const reorderMutation = useMutation({
    mutationFn: (stageIds: string[]) =>
      apiFetch<PipelineStageOut[]>("/tenants/me/pipeline-stages/reorder", {
        method: "POST",
        body: { stage_ids: stageIds },
      }),
    onSuccess: (data) => queryClient.setQueryData(["pipeline-stages", tenantId], data),
  });

  const move = (index: number, direction: -1 | 1) => {
    const stages = stagesQuery.data;
    if (!stages) return;
    const target = index + direction;
    if (target < 0 || target >= stages.length) return;
    const ids = stages.map((s) => s.id);
    const a = ids[index];
    const b = ids[target];
    if (a === undefined || b === undefined) return;
    ids[index] = b;
    ids[target] = a;
    reorderMutation.mutate(ids);
  };

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Pipeline stages</h1>
      <p className="mb-6 text-sm text-surface-400">
        The CRM pipeline is built from these tenant-configurable stages - never hardcoded.
      </p>

      {canManage ? (
        <Card className="mb-6">
          <h2 className="mb-4 text-sm font-semibold text-surface-100">Add a stage</h2>
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
            className="flex flex-wrap items-end gap-4"
            noValidate
          >
            <div>
              <Label htmlFor="stage-name">Name</Label>
              <Input id="stage-name" className="w-56" {...register("name", { required: true })} />
              <FormError message={formState.errors.name ? "Name is required" : undefined} />
            </div>
            <label className="flex items-center gap-2 pb-2 text-sm text-surface-300">
              <input type="checkbox" {...register("is_won")} /> Marks lead as Won
            </label>
            <label className="flex items-center gap-2 pb-2 text-sm text-surface-300">
              <input type="checkbox" {...register("is_lost")} /> Marks lead as Lost
            </label>
            <Button type="submit" loading={createMutation.isPending}>
              Add stage
            </Button>
          </form>
        </Card>
      ) : null}

      <Card>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-800 text-surface-500">
              <th className="pb-2 font-medium">Order</th>
              <th className="pb-2 font-medium">Name</th>
              <th className="pb-2 font-medium">Flags</th>
              {canManage ? <th className="pb-2 font-medium">Reorder</th> : null}
            </tr>
          </thead>
          <tbody>
            {stagesQuery.data?.map((stage, index) => (
              <tr key={stage.id} className="border-b border-surface-900">
                <td className="py-2 text-surface-500">{index + 1}</td>
                <td className="py-2 text-surface-200">{stage.name}</td>
                <td className="py-2 space-x-2">
                  {stage.is_won ? <Badge tone="success">won</Badge> : null}
                  {stage.is_lost ? <Badge tone="danger">lost</Badge> : null}
                  {stage.is_system ? <Badge tone="neutral">default</Badge> : null}
                </td>
                {canManage ? (
                  <td className="py-2">
                    <div className="flex gap-1">
                      <Button variant="ghost" onClick={() => move(index, -1)} disabled={index === 0}>
                        Up
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => move(index, 1)}
                        disabled={index === (stagesQuery.data?.length ?? 0) - 1}
                      >
                        Down
                      </Button>
                    </div>
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
