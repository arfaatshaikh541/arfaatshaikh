"use client";

import { use, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import { useInvalidatePortalAuth } from "@/lib/portal-auth-context";
import type { CurrentPortalAccount } from "@/lib/types";

export default function PortalAcceptInvitationPage({ params }: { params: Promise<{ tenantSlug: string }> }) {
  const { tenantSlug } = use(params);
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const router = useRouter();
  const invalidatePortalAuth = useInvalidatePortalAuth();
  const [password, setPassword] = useState("");

  const acceptMutation = useMutation({
    mutationFn: () => api.post<CurrentPortalAccount>("/portal/auth/accept-invitation", { token, password }),
    onSuccess: async () => {
      await invalidatePortalAuth();
      router.replace(`/portal/${tenantSlug}/dashboard`);
    },
  });

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Alert tone="error">This invitation link is missing a token.</Alert>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-center text-xl font-semibold text-ink">Set up your account</h1>
        <Card className="mt-6">
          <CardHeader title="Choose a password" />
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              acceptMutation.mutate();
            }}
          >
            {acceptMutation.isError && (
              <Alert tone="error">{acceptMutation.error instanceof ApiError ? acceptMutation.error.message : "Unable to set up your account."}</Alert>
            )}
            <div>
              <Label htmlFor="portal-new-password">Password</Label>
              <Input id="portal-new-password" type="password" minLength={10} value={password} onChange={(e) => setPassword(e.target.value)} required />
              <p className="mt-1 text-xs text-ink-faint">At least 10 characters, with a mix of letters and numbers or symbols.</p>
            </div>
            <Button type="submit" className="w-full" disabled={acceptMutation.isPending || password.length < 10}>
              {acceptMutation.isPending ? "Setting up…" : "Set password and sign in"}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
