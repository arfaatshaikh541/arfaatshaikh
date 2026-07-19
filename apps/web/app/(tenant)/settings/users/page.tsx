"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, Card, CardHeader, FormRoot, StatusBadge, TextInput } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { MembershipRead, PendingAccountRecoveryRequestRead, RoleRead } from "@/lib/types";

const schema = z.object({
  email: z.string().email("Enter a valid email address."),
  role_name: z.string().min(1, "Choose a role."),
});
type FormValues = z.infer<typeof schema>;

function PendingRecoveryRequests() {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [decidingRequestId, setDecidingRequestId] = useState<string | null>(null);
  const [stepUpRequestId, setStepUpRequestId] = useState<string | null>(null);
  const [stepUpCode, setStepUpCode] = useState("");
  const [denyReasonByRequest, setDenyReasonByRequest] = useState<Record<string, string>>({});

  const pendingQuery = useQuery({
    queryKey: ["account-recovery-pending"],
    queryFn: () => apiClient.get<PendingAccountRecoveryRequestRead[]>("/api/auth/recovery/pending"),
  });

  const approve = async (requestId: string) => {
    setActionError(null);
    setDecidingRequestId(requestId);
    try {
      await apiClient.post(`/api/auth/recovery/${requestId}/approve`);
      queryClient.invalidateQueries({ queryKey: ["account-recovery-pending"] });
    } catch (err) {
      // Mirrors the Automation page's step-up flow: an approving admin who
      // has MFA enabled must recently re-prove it before this disruptive
      // action (disabling someone else's MFA) is allowed to proceed.
      if (err instanceof ApiError && err.details.step_up_required) {
        setStepUpRequestId(requestId);
      } else {
        setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
      }
    } finally {
      setDecidingRequestId(null);
    }
  };

  const submitStepUpThenApprove = async () => {
    if (!stepUpRequestId) return;
    setActionError(null);
    setDecidingRequestId(stepUpRequestId);
    try {
      await apiClient.post("/api/auth/step-up", { code: stepUpCode });
      await apiClient.post(`/api/auth/recovery/${stepUpRequestId}/approve`);
      queryClient.invalidateQueries({ queryKey: ["account-recovery-pending"] });
      setStepUpRequestId(null);
      setStepUpCode("");
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setDecidingRequestId(null);
    }
  };

  const deny = async (requestId: string) => {
    setActionError(null);
    setDecidingRequestId(requestId);
    try {
      await apiClient.post(`/api/auth/recovery/${requestId}/deny`, {
        reason: denyReasonByRequest[requestId]?.trim() || "Could not verify identity.",
      });
      queryClient.invalidateQueries({ queryKey: ["account-recovery-pending"] });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setDecidingRequestId(null);
    }
  };

  if (!pendingQuery.data || pendingQuery.data.length === 0) return null;

  return (
    <Card>
      <CardHeader
        title="Pending account recovery requests"
        description="A teammate locked out of MFA is asking a different administrator to vouch for their identity. Approving disables MFA on their account — they'll re-enroll after signing back in."
      />
      {actionError ? <Alert tone="error">{actionError}</Alert> : null}
      <div className="flex flex-col gap-4">
        {pendingQuery.data.map((req) => (
          <div key={req.id} className="rounded border border-surface-border p-3">
            <p className="text-sm font-medium text-ink-900">
              {req.user_full_name} <span className="text-ink-500">({req.user_email})</span>
            </p>
            <p className="mt-1 text-sm text-ink-700">&ldquo;{req.reason}&rdquo;</p>
            {stepUpRequestId === req.id ? (
              <div className="mt-3 flex flex-col gap-2 rounded border border-surface-border bg-surface-900 p-3">
                <p className="text-xs text-ink-500">
                  Enter your own current authenticator code to confirm this approval.
                </p>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    inputMode="numeric"
                    placeholder="6-digit code"
                    value={stepUpCode}
                    onChange={(e) => setStepUpCode(e.target.value)}
                    className="h-9 w-40 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
                  />
                  <Button size="sm" isLoading={decidingRequestId === req.id} onClick={submitStepUpThenApprove}>
                    Verify and approve
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setStepUpRequestId(null)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button size="sm" isLoading={decidingRequestId === req.id} onClick={() => approve(req.id)}>
                  Approve — disable their MFA
                </Button>
                <input
                  type="text"
                  placeholder="Reason for denying (optional)"
                  value={denyReasonByRequest[req.id] ?? ""}
                  onChange={(e) =>
                    setDenyReasonByRequest((prev) => ({ ...prev, [req.id]: e.target.value }))
                  }
                  className="h-9 flex-1 min-w-[12rem] rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
                />
                <Button
                  size="sm"
                  variant="ghost"
                  isLoading={decidingRequestId === req.id}
                  onClick={() => deny(req.id)}
                >
                  Deny
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function UsersSettingsPage() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const canManage = hasPermission("users.manage");
  const [serverError, setServerError] = useState<string | null>(null);
  const [inviteSent, setInviteSent] = useState(false);

  const membersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => apiClient.get<MembershipRead[]>("/api/users"),
    enabled: canManage,
  });

  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => apiClient.get<RoleRead[]>("/api/roles"),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  if (!canManage) {
    return <Alert tone="info">You don&apos;t have permission to manage workspace members.</Alert>;
  }

  const onInvite = async (values: FormValues) => {
    setServerError(null);
    setInviteSent(false);
    try {
      await apiClient.post("/api/users/invitations", values);
      setInviteSent(true);
      reset();
      queryClient.invalidateQueries({ queryKey: ["users"] });
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Users</h1>
        <p className="text-sm text-ink-500">Invite teammates and manage their access to this workspace.</p>
      </div>

      <PendingRecoveryRequests />

      <Card>
        <CardHeader title="Invite a teammate" />
        <FormRoot onSubmit={handleSubmit(onInvite)} className="max-w-md">
          {serverError ? <Alert tone="error">{serverError}</Alert> : null}
          {inviteSent ? <Alert tone="success">Invitation sent.</Alert> : null}
          <TextInput label="Email address" type="email" error={errors.email?.message} {...register("email")} />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="role_name" className="text-sm font-medium text-ink-700">
              Role
            </label>
            <select
              id="role_name"
              className="h-10 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
              {...register("role_name")}
            >
              <option value="">Select a role</option>
              {rolesQuery.data
                ?.filter((r) => !r.is_platform_role)
                .map((role) => (
                  <option key={role.id} value={role.name}>
                    {role.name.replace(/_/g, " ")}
                  </option>
                ))}
            </select>
            {errors.role_name ? <p className="text-xs text-severity-critical">{errors.role_name.message}</p> : null}
          </div>
          <Button type="submit" isLoading={isSubmitting}>
            Send invitation
          </Button>
        </FormRoot>
      </Card>

      <Card>
        <CardHeader title="Members" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-border text-ink-500">
                <th className="py-2 pr-4 font-medium">Name</th>
                <th className="py-2 pr-4 font-medium">Email</th>
                <th className="py-2 pr-4 font-medium">Role</th>
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {membersQuery.data?.map((member) => (
                <tr key={member.id} className="border-b border-surface-border/50">
                  <td className="py-2 pr-4 text-ink-900">{member.full_name}</td>
                  <td className="py-2 pr-4 text-ink-500">{member.email}</td>
                  <td className="py-2 pr-4 text-ink-700">{member.role_name.replace(/_/g, " ")}</td>
                  <td className="py-2">
                    <StatusBadge label={member.status} tone={member.status === "active" ? "positive" : "neutral"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
