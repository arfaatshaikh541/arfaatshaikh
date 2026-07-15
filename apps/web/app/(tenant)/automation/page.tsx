"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, Card, CardHeader, FormRoot, StatusBadge, TextInput } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { ActionRunRead, AutomationSettingRead, PlaybookRead } from "@/lib/types";

const AUTOMATION_MODES = [
  { value: "observe", label: "Observe", description: "Never acts automatically — findings stay visible for manual remediation only." },
  { value: "guided", label: "Guided", description: "Every playbook match creates a pending action a human must approve." },
  { value: "balanced", label: "Balanced", description: "Safe, reversible actions run automatically; disruptive ones wait for approval." },
  { value: "autopilot", label: "Autopilot", description: "Most actions run automatically; only the most severe wait for approval." },
  { value: "lockdown", label: "Lockdown", description: "Every action runs automatically, including the most disruptive — for active-incident response." },
];

const STATUS_TONE: Record<string, "positive" | "warning" | "neutral"> = {
  pending_approval: "warning",
  approved: "neutral",
  rejected: "neutral",
  running: "warning",
  succeeded: "positive",
  failed: "warning",
};

const playbookSchema = z.object({
  name: z.string().min(2, "Give this playbook a name."),
  description: z.string().optional(),
  rule_key: z.string().min(2, "Enter the rule this playbook responds to."),
  action_key: z.string().min(2, "Enter the action to take."),
});
type PlaybookFormValues = z.infer<typeof playbookSchema>;

export default function AutomationPage() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const canManageAutomation = hasPermission("automations.manage");
  const canViewPlaybooks = hasPermission("playbooks.view");
  const canManagePlaybooks = hasPermission("playbooks.manage");
  const canViewActions = hasPermission("actions.view");
  const canApprove = hasPermission("actions.approve_disruptive");

  const [modeError, setModeError] = useState<string | null>(null);
  const [isUpdatingMode, setIsUpdatingMode] = useState(false);
  const [playbookError, setPlaybookError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [decidingRunId, setDecidingRunId] = useState<string | null>(null);

  const settingsQuery = useQuery({
    queryKey: ["automation", "settings"],
    queryFn: () => apiClient.get<AutomationSettingRead>("/api/automation/settings"),
    enabled: canManageAutomation,
  });

  const playbooksQuery = useQuery({
    queryKey: ["playbooks"],
    queryFn: () => apiClient.get<PlaybookRead[]>("/api/playbooks"),
    enabled: canViewPlaybooks,
  });

  const actionRunsQuery = useQuery({
    queryKey: ["actions"],
    queryFn: () => apiClient.get<ActionRunRead[]>("/api/actions"),
    enabled: canViewActions,
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PlaybookFormValues>({ resolver: zodResolver(playbookSchema) });

  const setMode = async (mode: string) => {
    setModeError(null);
    setIsUpdatingMode(true);
    try {
      await apiClient.patch("/api/automation/settings", { mode });
      queryClient.invalidateQueries({ queryKey: ["automation", "settings"] });
    } catch (err) {
      setModeError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsUpdatingMode(false);
    }
  };

  const onCreatePlaybook = async (values: PlaybookFormValues) => {
    setPlaybookError(null);
    try {
      await apiClient.post("/api/playbooks", values);
      reset();
      queryClient.invalidateQueries({ queryKey: ["playbooks"] });
    } catch (err) {
      setPlaybookError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  const togglePlaybook = async (playbook: PlaybookRead) => {
    setPlaybookError(null);
    try {
      await apiClient.patch(`/api/playbooks/${playbook.id}`, { is_enabled: !playbook.is_enabled });
      queryClient.invalidateQueries({ queryKey: ["playbooks"] });
    } catch (err) {
      setPlaybookError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  const deletePlaybook = async (playbookId: string) => {
    setPlaybookError(null);
    try {
      await apiClient.delete(`/api/playbooks/${playbookId}`);
      queryClient.invalidateQueries({ queryKey: ["playbooks"] });
    } catch (err) {
      setPlaybookError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  const decideActionRun = async (runId: string, decision: "approve" | "reject") => {
    setActionError(null);
    setDecidingRunId(runId);
    try {
      if (decision === "approve") {
        await apiClient.post(`/api/actions/${runId}/approve`);
      } else {
        await apiClient.post(`/api/actions/${runId}/reject`, { reason: "Rejected from the Automation page." });
      }
      queryClient.invalidateQueries({ queryKey: ["actions"] });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setDecidingRunId(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Automation</h1>
        <p className="text-sm text-ink-500">
          Cyber Autopilot: let GRIDKEEP take safe, reversible remediation actions automatically, and
          decide how much autonomy it has.
        </p>
      </div>

      {canManageAutomation ? (
        <Card>
          <CardHeader title="Automation mode" />
          {modeError ? <Alert tone="error">{modeError}</Alert> : null}
          <div className="flex flex-col gap-2">
            {AUTOMATION_MODES.map((option) => (
              <label
                key={option.value}
                className={[
                  "flex cursor-pointer items-start gap-3 rounded-md border p-3",
                  settingsQuery.data?.mode === option.value
                    ? "border-accent bg-surface-800"
                    : "border-surface-border",
                ].join(" ")}
              >
                <input
                  type="radio"
                  name="automation-mode"
                  className="mt-1"
                  checked={settingsQuery.data?.mode === option.value}
                  disabled={isUpdatingMode}
                  onChange={() => setMode(option.value)}
                />
                <div>
                  <p className="text-sm font-medium text-ink-900">{option.label}</p>
                  <p className="text-sm text-ink-500">{option.description}</p>
                </div>
              </label>
            ))}
          </div>
        </Card>
      ) : null}

      {canViewPlaybooks ? (
        <Card>
          <CardHeader
            title="Playbooks"
            description="Maps a finding's rule to an action to take when that rule fires."
          />
          {canManagePlaybooks ? (
            <FormRoot onSubmit={handleSubmit(onCreatePlaybook)} className="mb-6 max-w-xl">
              {playbookError ? <Alert tone="error">{playbookError}</Alert> : null}
              <TextInput label="Name" error={errors.name?.message} {...register("name")} />
              <TextInput
                label="Rule key"
                placeholder="e.g. backup_job_failed"
                error={errors.rule_key?.message}
                {...register("rule_key")}
              />
              <TextInput
                label="Action key"
                placeholder="e.g. trigger_restore_test"
                error={errors.action_key?.message}
                {...register("action_key")}
              />
              <Button type="submit" size="sm" isLoading={isSubmitting}>
                Add playbook
              </Button>
            </FormRoot>
          ) : null}

          {playbooksQuery.data && playbooksQuery.data.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-surface-border text-ink-500">
                    <th className="py-2 pr-4 font-medium">Name</th>
                    <th className="py-2 pr-4 font-medium">Rule</th>
                    <th className="py-2 pr-4 font-medium">Action</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {playbooksQuery.data.map((playbook) => (
                    <tr key={playbook.id} className="border-b border-surface-border/50">
                      <td className="py-2 pr-4 text-ink-900">{playbook.name}</td>
                      <td className="py-2 pr-4 text-ink-500">{playbook.rule_key}</td>
                      <td className="py-2 pr-4 text-ink-500">{playbook.action_key}</td>
                      <td className="py-2 pr-4">
                        <StatusBadge
                          label={playbook.is_enabled ? "Enabled" : "Disabled"}
                          tone={playbook.is_enabled ? "positive" : "neutral"}
                        />
                      </td>
                      <td className="py-2 text-right">
                        {canManagePlaybooks ? (
                          <div className="flex justify-end gap-2">
                            <Button size="sm" variant="ghost" onClick={() => togglePlaybook(playbook)}>
                              {playbook.is_enabled ? "Disable" : "Enable"}
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => deletePlaybook(playbook.id)}>
                              Delete
                            </Button>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-ink-500">No playbooks configured yet.</p>
          )}
        </Card>
      ) : null}

      {canViewActions ? (
        <Card>
          <CardHeader title="Action runs" />
          {actionError ? <Alert tone="error">{actionError}</Alert> : null}
          {actionRunsQuery.data && actionRunsQuery.data.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-surface-border text-ink-500">
                    <th className="py-2 pr-4 font-medium">Action</th>
                    <th className="py-2 pr-4 font-medium">Asset</th>
                    <th className="py-2 pr-4 font-medium">Trigger</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 pr-4 font-medium">Result</th>
                    <th className="py-2 pr-4 font-medium">Requested</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {actionRunsQuery.data.map((run) => (
                    <tr key={run.id} className="border-b border-surface-border/50">
                      <td className="py-2 pr-4 text-ink-900">{run.action_key}</td>
                      <td className="py-2 pr-4 text-ink-500">{run.asset_display_name}</td>
                      <td className="py-2 pr-4 text-ink-500">{run.trigger}</td>
                      <td className="py-2 pr-4">
                        <StatusBadge label={run.status.replace(/_/g, " ")} tone={STATUS_TONE[run.status] ?? "neutral"} />
                      </td>
                      <td className="py-2 pr-4 text-ink-500">{run.result_message ?? ""}</td>
                      <td className="py-2 pr-4 text-ink-500">{new Date(run.requested_at).toLocaleString()}</td>
                      <td className="py-2 text-right">
                        {canApprove && run.status === "pending_approval" ? (
                          <div className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              isLoading={decidingRunId === run.id}
                              onClick={() => decideActionRun(run.id, "approve")}
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              isLoading={decidingRunId === run.id}
                              onClick={() => decideActionRun(run.id, "reject")}
                            >
                              Reject
                            </Button>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-ink-500">No action runs yet.</p>
          )}
        </Card>
      ) : null}
    </div>
  );
}
