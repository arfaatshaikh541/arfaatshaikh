"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";

export default function PortalResetPasswordPage({ params }: { params: Promise<{ tenantSlug: string }> }) {
  const { tenantSlug } = use(params);
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [newPassword, setNewPassword] = useState("");

  const resetMutation = useMutation({
    mutationFn: () => api.post("/portal/auth/reset-password", { token, new_password: newPassword }),
  });

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Alert tone="error">This reset link is missing a token.</Alert>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-center text-xl font-semibold text-ink">Choose a new password</h1>
        <Card className="mt-6">
          {resetMutation.isSuccess ? (
            <div className="space-y-3">
              <Alert tone="success">Your password has been reset.</Alert>
              <Link href={`/portal/${tenantSlug}/login`} className="focus-ring block text-center text-sm text-accent underline">
                Sign in
              </Link>
            </div>
          ) : (
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                resetMutation.mutate();
              }}
            >
              {resetMutation.isError && (
                <Alert tone="error">{resetMutation.error instanceof ApiError ? resetMutation.error.message : "Unable to reset password."}</Alert>
              )}
              <div>
                <CardHeader title="New password" />
                <Label htmlFor="portal-reset-password">Password</Label>
                <Input id="portal-reset-password" type="password" minLength={10} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
                <p className="mt-1 text-xs text-ink-faint">At least 10 characters, with a mix of letters and numbers or symbols.</p>
              </div>
              <Button type="submit" className="w-full" disabled={resetMutation.isPending || newPassword.length < 10}>
                {resetMutation.isPending ? "Resetting…" : "Reset password"}
              </Button>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}
