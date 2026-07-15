"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import { useInvalidatePortalAuth } from "@/lib/portal-auth-context";
import type { CurrentPortalAccount } from "@/lib/types";

export default function PortalLoginPage({ params }: { params: Promise<{ tenantSlug: string }> }) {
  const { tenantSlug } = use(params);
  const router = useRouter();
  const invalidatePortalAuth = useInvalidatePortalAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const loginMutation = useMutation({
    mutationFn: () => api.post<CurrentPortalAccount>("/portal/auth/login", { tenant_slug: tenantSlug, email, password }),
    onSuccess: async () => {
      await invalidatePortalAuth();
      router.replace(`/portal/${tenantSlug}/dashboard`);
    },
  });

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-center text-xl font-semibold text-ink">Client Portal</h1>
        <Card className="mt-6">
          <CardHeader title="Sign in" />
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              loginMutation.mutate();
            }}
          >
            {loginMutation.isError && (
              <Alert tone="error">{loginMutation.error instanceof ApiError ? loginMutation.error.message : "Unable to sign in."}</Alert>
            )}
            <div>
              <Label htmlFor="portal-email">Email</Label>
              <Input id="portal-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <Label htmlFor="portal-password">Password</Label>
              <Input id="portal-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <Button type="submit" className="w-full" disabled={loginMutation.isPending}>
              {loginMutation.isPending ? "Signing in…" : "Sign in"}
            </Button>
            <p className="text-center text-sm text-ink-muted">
              <Link href={`/portal/${tenantSlug}/forgot-password`} className="underline">
                Forgot your password?
              </Link>
            </p>
          </form>
        </Card>
      </div>
    </div>
  );
}
