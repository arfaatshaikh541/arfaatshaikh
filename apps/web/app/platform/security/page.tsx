"use client";

import { Alert, Button, Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { MfaBackupCodesResponse, MfaConfirmResponse, MfaEnrollResponse } from "@/lib/types";

// Hardening-programme Milestone 4 (Platform-Admin Separation): MFA is
// mandatory for every platform account (core/deps.py:get_platform_context)
// — this page is the only way a platform-only admin (no tenant
// membership) can reach the MFA enrollment flow, since
// `(tenant)/settings/security` lives under a layout that requires one.
// Deliberately not shared with that page: the workspace-security-policy
// and support-access-log cards there are tenant-scoped and meaningless
// here, so this stays a smaller, self-contained MFA-only card rather than
// factoring out a shared component two call sites don't otherwise need.
export default function PlatformSecurityPage() {
  const { me, refetch: refetchAuth } = useAuth();

  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [enrollment, setEnrollment] = useState<MfaEnrollResponse | null>(null);
  const [confirmCode, setConfirmCode] = useState("");
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null);
  const [showRegenerateForm, setShowRegenerateForm] = useState(false);
  const [regenerateCode, setRegenerateCode] = useState("");

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
      const result = await apiClient.post<MfaConfirmResponse>("/api/auth/mfa/confirm", {
        code: confirmCode,
      });
      setEnrollment(null);
      setConfirmCode("");
      setBackupCodes(result.backup_codes);
      setNotice("Multi-factor authentication is now enabled. You can continue to the platform console.");
      refetchAuth();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  const regenerateBackupCodes = async () => {
    setError(null);
    setIsBusy(true);
    try {
      const result = await apiClient.post<MfaBackupCodesResponse>("/api/auth/mfa/backup-codes/regenerate", {
        code: regenerateCode,
      });
      setBackupCodes(result.backup_codes);
      setShowRegenerateForm(false);
      setRegenerateCode("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Security</h1>
        <p className="text-sm text-ink-500">
          Multi-factor authentication for your platform account.
        </p>
      </div>

      {me?.mfa_enrollment_required ? (
        <Alert tone="error">
          Platform accounts must enable multi-factor authentication before using the platform console.
          Enable it below to continue.
        </Alert>
      ) : null}
      {error ? <Alert tone="error">{error}</Alert> : null}
      {notice ? <Alert tone="success">{notice}</Alert> : null}

      {backupCodes ? (
        <Card>
          <CardHeader
            title="Save your backup codes"
            description="Each code can be used once to sign in if you lose access to your authenticator app. They won't be shown again — store them somewhere safe."
          />
          <div className="grid grid-cols-2 gap-2 rounded border border-surface-border bg-surface-800 p-3 sm:grid-cols-5">
            {backupCodes.map((code) => (
              <code key={code} className="text-sm text-ink-900">
                {code}
              </code>
            ))}
          </div>
          <Button className="mt-3 w-fit" onClick={() => setBackupCodes(null)}>
            I&apos;ve saved these codes
          </Button>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Multi-factor authentication"
          description="Required for every platform account — protects your ability to view or modify any tenant's data."
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

          {mfaEnabled && !showRegenerateForm ? (
            <Button className="w-fit" variant="secondary" onClick={() => setShowRegenerateForm(true)}>
              Regenerate backup codes
            </Button>
          ) : null}

          {showRegenerateForm ? (
            <div className="flex flex-col gap-2 rounded border border-surface-border p-3">
              <p className="text-sm text-ink-700">
                This invalidates all of your existing backup codes and issues 10 new ones. Enter your
                current verification code to confirm.
              </p>
              <label htmlFor="regenerate-code" className="text-sm font-medium text-ink-700">
                Verification code
              </label>
              <input
                id="regenerate-code"
                type="text"
                inputMode="numeric"
                value={regenerateCode}
                onChange={(e) => setRegenerateCode(e.target.value)}
                className="h-10 w-40 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
              />
              <div className="flex gap-2">
                <Button variant="secondary" isLoading={isBusy} onClick={regenerateBackupCodes}>
                  Regenerate
                </Button>
                <Button variant="ghost" onClick={() => setShowRegenerateForm(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
