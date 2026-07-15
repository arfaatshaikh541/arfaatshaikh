"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { LeadSummary, OnboardingCaseItem, OnboardingCaseStatus, OnboardingTemplateItem, Page } from "@/lib/types";

const STATUS_TONE: Record<OnboardingCaseStatus, string> = {
  not_started: "text-ink-faint",
  in_progress: "text-accent",
  completed: "text-emerald-400",
  cancelled: "text-red-400",
};

export default function OnboardingCasesPage() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const leadIdFilter = searchParams.get("leadId") ?? "";

  const [leadId, setLeadId] = useState(leadIdFilter);
  const [templateId, setTemplateId] = useState("");

  const casesQuery = useQuery({
    queryKey: ["tenant", "onboarding-cases", leadIdFilter],
    queryFn: () => api.get<OnboardingCaseItem[]>(`/tenant/onboarding-cases${leadIdFilter ? `?lead_id=${leadIdFilter}` : ""}`),
  });
  const leadsQuery = useQuery({
    queryKey: ["tenant", "leads", "picker"],
    queryFn: () => api.get<Page<LeadSummary>>("/tenant/leads?page_size=200").then((r) => r.items),
  });
  const templatesQuery = useQuery({ queryKey: ["tenant", "onboarding-templates"], queryFn: () => api.get<OnboardingTemplateItem[]>("/tenant/onboarding-templates") });

  const startMutation = useMutation({
    mutationFn: () => api.post<OnboardingCaseItem>("/tenant/onboarding-cases", { lead_id: leadId, template_id: templateId || null }),
    onSuccess: () => {
      setTemplateId("");
      queryClient.invalidateQueries({ queryKey: ["tenant", "onboarding-cases"] });
    },
  });

  const leads = leadsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Onboarding</h1>
        <p className="mt-1 text-sm text-ink-muted">
          {leadIdFilter ? "Onboarding cases for this lead." : "Track a client's onboarding checklist from start to finish."}
        </p>
      </div>

      <Card>
        <CardHeader title="Start a case" />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            startMutation.mutate();
          }}
        >
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="case-lead">Lead</Label>
              <select
                id="case-lead"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={leadId}
                onChange={(e) => setLeadId(e.target.value)}
                required
              >
                <option value="">Select a lead…</option>
                {leads.map((lead) => (
                  <option key={lead.id} value={lead.id}>
                    {lead.first_name} {lead.last_name} ({lead.reference_number})
                  </option>
                ))}
              </select>
            </div>
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="case-template">Template</Label>
              <select
                id="case-template"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                <option value="">No template — blank case</option>
                {templatesQuery.data?.map((template) => (
                  <option key={template.id} value={template.id}>{template.name}</option>
                ))}
              </select>
            </div>
          </div>
          <Button type="submit" disabled={startMutation.isPending || !leadId}>
            {startMutation.isPending ? "Starting…" : "Start onboarding"}
          </Button>
        </form>
        {startMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{startMutation.error instanceof ApiError ? startMutation.error.message : "Unable to start case."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Cases" />
        <div className="space-y-2">
          {casesQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No onboarding cases yet.</p>}
          {casesQuery.data?.map((onboardingCase) => (
            <Link
              key={onboardingCase.id}
              href={`/onboarding-cases/${onboardingCase.id}`}
              className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm hover:border-ink-muted"
            >
              <div>
                <p className="font-medium text-ink">{onboardingCase.name}</p>
                <p className="text-xs text-ink-faint">
                  {onboardingCase.steps.filter((s) => s.status !== "pending").length} / {onboardingCase.steps.length} steps complete
                </p>
              </div>
              <span className={`text-xs font-medium capitalize ${STATUS_TONE[onboardingCase.status]}`}>{onboardingCase.status.replace("_", " ")}</span>
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}
