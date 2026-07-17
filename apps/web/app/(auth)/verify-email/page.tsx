"use client";

import { Banner, Card } from "@gridkeep/ui";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";

type VerifyState = "verifying" | "success" | "error";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [state, setState] = useState<VerifyState>(token ? "verifying" : "error");
  const [message, setMessage] = useState<string>(
    token ? "" : "This verification link is missing its token.",
  );

  useEffect(() => {
    if (!token) return;
    api
      .post("/auth/verify-email", { token })
      .then(() => setState("success"))
      .catch((err) => {
        setState("error");
        setMessage(err instanceof ApiError ? err.message : "Verification failed.");
      });
  }, [token]);

  return (
    <Card className="w-full max-w-sm text-center">
      <h1 className="mb-4 text-xl font-semibold">Email verification</h1>
      {state === "verifying" && <p className="text-sm text-slate-500">Verifying your email...</p>}
      {state === "success" && (
        <>
          <Banner tone="success">Your email has been verified.</Banner>
          <Link href="/login" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">
            Continue to sign in
          </Link>
        </>
      )}
      {state === "error" && (
        <>
          <Banner tone="error">{message}</Banner>
          <Link href="/login" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">
            Back to sign in
          </Link>
        </>
      )}
    </Card>
  );
}

export default function VerifyEmailPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <Suspense fallback={<p className="text-sm text-slate-500">Loading...</p>}>
        <VerifyEmailContent />
      </Suspense>
    </main>
  );
}
