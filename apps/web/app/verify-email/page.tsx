"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";

function VerifyEmailInner() {
  const params = useSearchParams();
  const token = params.get("token");
  // A missing token is a fact derivable from props at render time, not an
  // external event to synchronize via an effect -- so it is handled directly
  // in the initializer rather than by calling setState from inside useEffect.
  const [status, setStatus] = useState<"pending" | "success" | "error">(token ? "pending" : "error");
  const [message, setMessage] = useState<string>(token ? "" : "No verification token was provided.");

  useEffect(() => {
    if (!token) return;
    api
      .post("/api/v1/auth/verify-email", { token })
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof ApiError ? err.message : "Verification failed.");
      });
  }, [token]);

  return (
    <main id="main-content" className="flex flex-1 items-center justify-center p-4 sm:p-8">
      <div className="max-w-sm text-center">
        {status === "pending" && <p>Verifying your email address...</p>}
        {status === "success" && (
          <>
            <h1 className="mb-2 text-2xl font-semibold">Email verified</h1>
            <p className="text-zinc-600 dark:text-zinc-400">You can now log in.</p>
          </>
        )}
        {status === "error" && (
          <>
            <h1 className="mb-2 text-2xl font-semibold">Verification failed</h1>
            <p className="text-zinc-600 dark:text-zinc-400">{message}</p>
          </>
        )}
        <Link className="mt-6 inline-block underline" href="/login">
          Back to login
        </Link>
      </div>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<main id="main-content" className="flex flex-1 items-center justify-center p-4 sm:p-8">Loading...</main>}>
      <VerifyEmailInner />
    </Suspense>
  );
}
