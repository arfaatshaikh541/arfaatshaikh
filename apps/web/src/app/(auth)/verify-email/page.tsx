"use client";

import { Alert } from "@leadflow/ui";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api-client";

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailContent />
    </Suspense>
  );
}

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"pending" | "success" | "error">("pending");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError("Missing verification token.");
      return;
    }
    apiFetch("/auth/verify-email", { method: "POST", body: { token }, withTenant: false })
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setError(err instanceof ApiError ? err.message : "Something went wrong.");
      });
  }, [token]);

  return (
    <div className="rounded-lg border border-surface-800 bg-surface-900 p-6">
      <h1 className="mb-4 text-lg font-semibold text-surface-50">Email verification</h1>
      {status === "pending" ? <p className="text-sm text-surface-400">Verifying…</p> : null}
      {status === "success" ? (
        <Alert tone="success">
          Your email has been verified.{" "}
          <Link href="/login" className="underline">
            Sign in
          </Link>
          .
        </Alert>
      ) : null}
      {status === "error" ? <Alert tone="error">{error}</Alert> : null}
    </div>
  );
}
