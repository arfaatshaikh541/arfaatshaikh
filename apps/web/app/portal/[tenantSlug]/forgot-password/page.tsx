"use client";

import { use, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { api } from "@/lib/api-client";

export default function PortalForgotPasswordPage({ params }: { params: Promise<{ tenantSlug: string }> }) {
  const { tenantSlug } = use(params);
  const [email, setEmail] = useState("");

  const requestMutation = useMutation({
    mutationFn: () => api.post("/portal/auth/forgot-password", { tenant_slug: tenantSlug, email }),
  });

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-center text-xl font-semibold text-ink">Reset your password</h1>
        <Card className="mt-6">
          {requestMutation.isSuccess ? (
            <Alert tone="success">If that email has portal access, a reset link is on its way.</Alert>
          ) : (
            <>
              <CardHeader title="Enter your email" />
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  requestMutation.mutate();
                }}
              >
                <div>
                  <Label htmlFor="portal-forgot-email">Email</Label>
                  <Input id="portal-forgot-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
                </div>
                <Button type="submit" className="w-full" disabled={requestMutation.isPending}>
                  {requestMutation.isPending ? "Sending…" : "Send reset link"}
                </Button>
              </form>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
