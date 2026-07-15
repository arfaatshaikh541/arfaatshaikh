"use client";

import { use } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api-client";
import type { OnboardingCaseItem, OnboardingCaseStatus } from "@/lib/types";

const STATUS_TONE: Record<OnboardingCaseStatus, string> = {
  not_started: "text-ink-faint",
  in_progress: "text-accent",
  completed: "text-emerald-400",
  cancelled: "text-red-400",
};

export default function OnboardingCaseDetailPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const queryClient = useQueryClient();

  const caseQuery = useQuery({ queryKey: ["onboarding-case", caseId], queryFn: () => api.get<OnboardingCaseItem>(`/tenant/onboarding-cases/${caseId}`) });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["onboarding-case", caseId] });

  const cancelMutation = useMutation({
    mutationFn: () => api.post(`/tenant/onboarding-cases/${caseId}/cancel`),
    onSuccess: invalidate,
  });
  const completeStepMutation = useMutation({
    mutationFn: (stepId: string) => api.post(`/tenant/onboarding-cases/${caseId}/steps/${stepId}/complete`),
    onSuccess: invalidate,
  });

  const onboardingCase = caseQuery.data;
  if (caseQuery.isLoading || !onboardingCase) return <p className="text-sm text-ink-muted">Loading…</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">{onboardingCase.name}</h1>
          <p className={`mt-1 text-sm font-medium capitalize ${STATUS_TONE[onboardingCase.status]}`}>{onboardingCase.status.replace("_", " ")}</p>
        </div>
        {onboardingCase.status === "in_progress" && (
          <Button variant="secondary" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}>
            {cancelMutation.isPending ? "Cancelling…" : "Cancel case"}
          </Button>
        )}
      </div>

      {cancelMutation.isError && <Alert tone="error">{cancelMutation.error instanceof ApiError ? cancelMutation.error.message : "Unable to cancel case."}</Alert>}

      <Card>
        <CardHeader title="Checklist" />
        <div className="space-y-2">
          {onboardingCase.steps.map((step) => (
            <div key={step.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
              <div>
                <p className={step.status === "completed" ? "text-ink-faint line-through" : "text-ink"}>{step.title}</p>
                <p className="text-xs text-ink-faint">
                  {step.step_type === "task" ? "Task" : "Document request"}
                  {step.task_id && (
                    <>
                      {" · "}
                      <Link href={`/leads/${onboardingCase.lead_id}`} className="underline">
                        view task on lead
                      </Link>
                    </>
                  )}
                  {step.document_request_id && (
                    <>
                      {" · "}
                      <Link href={`/document-requests/${step.document_request_id}`} className="underline">
                        view document request
                      </Link>
                    </>
                  )}
                </p>
              </div>
              {step.status === "pending" && !step.task_id && !step.document_request_id && (
                <Button variant="secondary" onClick={() => completeStepMutation.mutate(step.id)} disabled={completeStepMutation.isPending}>
                  Mark complete
                </Button>
              )}
              {step.status !== "pending" && <span className="text-xs capitalize text-ink-faint">{step.status}</span>}
            </div>
          ))}
          {onboardingCase.steps.length === 0 && <p className="text-sm text-ink-muted">This case has no steps.</p>}
        </div>
      </Card>
    </div>
  );
}
