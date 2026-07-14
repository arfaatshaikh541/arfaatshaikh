"use client";

import Link from "next/link";
import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Card, CardHeader } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api-client";

function VerifyEmailInner() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const mutation = useMutation({
    mutationFn: () => api.post("/auth/verify-email", { token }),
  });

  useEffect(() => {
    if (token) {
      mutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <Card>
      <CardHeader title="Verify your email" />
      {!token && <Alert tone="error">This verification link is missing a token.</Alert>}
      {mutation.isPending && <Alert tone="info">Verifying…</Alert>}
      {mutation.isSuccess && (
        <Alert tone="success">
          Your email has been verified. <Link href="/login" className="underline">Sign in</Link>.
        </Alert>
      )}
      {mutation.isError && (
        <Alert tone="error">
          {mutation.error instanceof ApiError ? mutation.error.message : "This link is invalid or has expired."}
        </Alert>
      )}
    </Card>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailInner />
    </Suspense>
  );
}
