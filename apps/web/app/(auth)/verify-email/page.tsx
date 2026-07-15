"use client";

import { Alert } from "@gridkeep/ui";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AuthShell } from "@/components/AuthShell";
import { apiClient, ApiError } from "@/lib/api-client";

type Status = "verifying" | "success" | "error";

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailContent />
    </Suspense>
  );
}

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = useState<Status>("verifying");
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("This verification link is missing its token.");
      return;
    }
    apiClient
      .post("/api/auth/verify-email", { token })
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof ApiError ? err.message : "This verification link is invalid or has expired.");
      });
  }, [token]);

  return (
    <AuthShell title="Verify your email">
      {status === "verifying" ? <p className="text-sm text-ink-500">Verifying…</p> : null}
      {status === "success" ? (
        <>
          <Alert tone="success">Your email address has been verified.</Alert>
          <Link href="/login" className="mt-4 block text-sm text-ink-700 hover:underline">
            Continue to sign in
          </Link>
        </>
      ) : null}
      {status === "error" ? <Alert tone="error">{message}</Alert> : null}
    </AuthShell>
  );
}
