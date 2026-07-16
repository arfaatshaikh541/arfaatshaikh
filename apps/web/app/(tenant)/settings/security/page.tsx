"use client";

import { Alert, Button, Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { MfaEnrollResponse, TenantSecurityProfileRead } from "@/lib/types";

export default function SecuritySettingsPage() {
  const { me, hasPermission, refetch: refetchAuth } = useAuth();
  const canManageSettings = hasPermission("settings.manage");
  const queryClient = useQueryClient();

  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [enrollment, setEnrollment] = useState<MfaEnrollResponse | null>(null);
  const [confirmCode, setConfirmCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [showDisableForm, setShowDisableForm] = useState(false);

  const profileQuery = useQuery({
    queryKey: ["tenancy", "security-profile"],
    queryFn: () => apiClient.get<TenantSecurityProfileRead>("/api/tenancy/security-profile"),
    enabled: canManageSettings,
  });

  const mfaEnabled = me?.user.mfa_enabled ?? false;

  const startEnrollment = async () => {
    setError(null);
    setIsBusy(true);
    try {
      const result = await apiClient.post<MfaEnrollResponse>("/api/auth/mfa/enroll");
      setEnrollment(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  const confirmEnrollment = async () => {
    setError(null);
    setIsBusy(true);
    try {
      await apiClient.post("/api/auth/mfa/confirm", { code: confirmCode });
      setEnrollment(null);
      setConfirmCode("");
      setNotice("Multi-factor authentication is now enabled.");
      refetchAuth();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  const disableMfa = async () => {
    setError(null);
    setIsBusy(true);
    try {
      await apiClient.post("/api/auth/mfa/disable", { code: disableCode });
      setShowDisableForm(false);
      setDisableCode("");
      setNotice("Multi-factor authentication has been disabled.");
      refetchAuth();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  const toggleProfileField = async (field: keyof TenantSecurityProfileRead, value: boolean) => {
    setError(null);
    try {
      await apiClient.patch("/api/tenancy/security-profile", { [field]: value });
      queryClient.invalidateQueries({ queryKey: ["tenancy", "security-profile"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  const profile = profileQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Security</h1>
        <p className="text-sm text-ink-500">
          Multi-factor authentication for your own account, and this workspace&apos;s security policy.
        </p>
      </div>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {notice ? <Alert tone="success">{notice}</Alert> : null}

      <Card>
        <CardHeader
          title="Multi-factor authentication"
          description="Protect your account with a time-based one-time code from an authenticator app."
        />
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <StatusBadge label={mfaEnabled ? "Enabled" : "Disabled"} tone={mfaEnabled ? "positive" : "neutral"} />
          </div>

          {!mfaEnabled && !enrollment ? (
            <Button className="w-fit" isLoading={isBusy} onClick={startEnrollment}>
              Enable MFA
            </Button>
          ) : null}

          {enrollment ? (
            <div className="flex flex-col gap-2 rounded border border-surface-border p-3">
              <p className="text-sm text-ink-700">
                Add this account to your authenticator app, either by entering the secret manually or
                using the provisioning link below, then enter the 6-digit code it generates.
              </p>
              <code className="rounded bg-surface-800 px-2 py-1 text-sm text-ink-900">
                {enrollment.secret}
              </code>
              <code className="break-all rounded bg-surface-800 px-2 py-1 text-xs text-ink-500">
                {enrollment.provisioning_uri}
              </code>
              <label htmlFor="confirm-code" className="text-sm font-medium text-ink-700">
                Verification code
              </label>
              <input
                id="confirm-code"
                type="text"
                inputMode="numeric"
                value={confirmCode}
                onChange={(e) => setConfirmCode(e.target.value)}
                className="h-10 w-40 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
              />
              <Button className="w-fit" isLoading={isBusy} onClick={confirmEnrollment}>
                Confirm
              </Button>
            </div>
          ) : null}

          {mfaEnabled && !showDisableForm ? (
            <Button
              className="w-fit"
              variant="secondary"
              onClick={() => setShowDisableForm(true)}
            >
              Disable MFA
            </Button>
          ) : null}

          {showDisableForm ? (
            <div className="flex flex-col gap-2 rounded border border-surface-border p-3">
              <label htmlFor="disable-code" className="text-sm font-medium text-ink-700">
                Enter your current verification code to disable MFA
              </label>
              <input
                id="disable-code"
                type="text"
                inputMode="numeric"
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value)}
                className="h-10 w-40 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
              />
              <div className="flex gap-2">
                <Button variant="secondary" isLoading={isBusy} onClick={disableMfa}>
                  Confirm disable
                </Button>
                <Button variant="ghost" onClick={() => setShowDisableForm(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </Card>

      {canManageSettings ? (
        <Card>
          <CardHeader
            title="Workspace security policy"
            description="These settings apply to the whole workspace, not just your own account."
          />
          {profile ? (
            <div className="flex flex-col gap-3">
              <label className="flex items-center gap-2 text-sm text-ink-700">
                <input
                  type="checkbox"
                  checked={profile.require_mfa_for_admins}
                  onChange={(e) => toggleProfileField("require_mfa_for_admins", e.target.checked)}
                />
                Require MFA for administrators
              </label>
              <label className="flex items-center gap-2 text-sm text-ink-700">
                <input
                  type="checkbox"
                  checked={profile.require_step_up_for_disruptive_actions}
                  onChange={(e) =>
                    toggleProfileField("require_step_up_for_disruptive_actions", e.target.checked)
                  }
                />
                Require step-up verification for disruptive action approval
              </label>
            </div>
          ) : (
            <p className="text-sm text-ink-500">Loading…</p>
          )}
        </Card>
      ) : null}
    </div>
  );
}
