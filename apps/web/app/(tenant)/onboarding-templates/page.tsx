"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { OnboardingStepType, OnboardingTemplateItem } from "@/lib/types";

interface StepInput {
  step_type: OnboardingStepType;
  title: string;
  description: string;
  due_in_days: string;
}

function emptyStep(): StepInput {
  return { step_type: "task", title: "", description: "", due_in_days: "" };
}

export default function OnboardingTemplatesPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [steps, setSteps] = useState<StepInput[]>([emptyStep()]);

  const templatesQuery = useQuery({ queryKey: ["tenant", "onboarding-templates"], queryFn: () => api.get<OnboardingTemplateItem[]>("/tenant/onboarding-templates") });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post("/tenant/onboarding-templates", {
        name, description,
        steps: steps
          .filter((s) => s.title.trim())
          .map((s) => ({
            step_type: s.step_type, title: s.title, description: s.description,
            due_in_days: s.step_type === "task" && s.due_in_days ? Number(s.due_in_days) : null,
          })),
      }),
    onSuccess: () => {
      setName("");
      setDescription("");
      setSteps([emptyStep()]);
      queryClient.invalidateQueries({ queryKey: ["tenant", "onboarding-templates"] });
    },
  });

  function updateStep(index: number, patch: Partial<StepInput>) {
    setSteps((current) => current.map((step, i) => (i === index ? { ...step, ...patch } : step)));
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Onboarding templates</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Reusable checklists — each step becomes a real task or document request the moment a case starts from this template.
        </p>
      </div>

      <Card>
        <CardHeader title="Add a template" />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="tpl-name">Name</Label>
              <Input id="tpl-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="tpl-description">Description</Label>
              <Input id="tpl-description" value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
          </div>

          <div>
            <Label>Steps</Label>
            <div className="space-y-2">
              {steps.map((step, index) => (
                <div key={index} className="flex flex-wrap items-end gap-2">
                  <div className="w-44">
                    <select
                      className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                      value={step.step_type}
                      onChange={(e) => updateStep(index, { step_type: e.target.value as OnboardingStepType })}
                    >
                      <option value="task">Task</option>
                      <option value="document_request">Document request</option>
                    </select>
                  </div>
                  <div className="min-w-[200px] flex-1">
                    <Input placeholder="Title" value={step.title} onChange={(e) => updateStep(index, { title: e.target.value })} />
                  </div>
                  <div className="min-w-[160px] flex-1">
                    <Input placeholder="Description (optional)" value={step.description} onChange={(e) => updateStep(index, { description: e.target.value })} />
                  </div>
                  {step.step_type === "task" && (
                    <div className="w-32">
                      <Input
                        type="number" min={0} max={365} placeholder="Due in days"
                        value={step.due_in_days} onChange={(e) => updateStep(index, { due_in_days: e.target.value })}
                      />
                    </div>
                  )}
                  <Button
                    type="button" variant="secondary"
                    onClick={() => setSteps((current) => current.filter((_, i) => i !== index))}
                    disabled={steps.length === 1}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
            <Button type="button" variant="secondary" className="mt-2" onClick={() => setSteps((current) => [...current, emptyStep()])}>
              Add step
            </Button>
          </div>

          <Button type="submit" disabled={createMutation.isPending || !name}>
            {createMutation.isPending ? "Adding…" : "Add template"}
          </Button>
        </form>
        {createMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to add template."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Templates" />
        <div className="space-y-3">
          {templatesQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No templates yet.</p>}
          {templatesQuery.data?.map((template) => (
            <div key={template.id} className="rounded-md border border-surface-border p-3 text-sm">
              <p className="font-medium text-ink">{template.name}</p>
              {template.description && <p className="text-xs text-ink-faint">{template.description}</p>}
              <ul className="mt-2 space-y-1">
                {template.steps.map((step) => (
                  <li key={step.id} className="text-xs text-ink-muted">
                    {step.step_type === "task" ? "Task" : "Document"}: {step.title}
                    {step.due_in_days != null && ` (due ${step.due_in_days}d after start)`}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
