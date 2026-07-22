"use client";

import { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

function AcceptInvitationInner() {
  const params = useSearchParams();
  const router = useRouter();
  const { user, loading } = useAuth();
  const token = params.get("token");
  const [status, setStatus] = useState<"idle" | "working" | "error">("idle");
  const [message, setMessage] = useState<string>("");

  const accept = async () => {
    if (!token) return;
    setStatus("working");
    try {
      // An invitation token does not indicate whether it is scoped to an
      // enterprise or an operator, so we try the enterprise endpoint first
      // and fall back to the operator endpoint on a validation failure.
      try {
        await api.post<{ enterprise_tenant_id: string }>("/api/v1/invitations/accept", { token });
      } catch (err) {
        if (err instanceof ApiError && err.status === 400) {
          await api.post<{ operator_id: string }>("/api/v1/operator-invitations/accept", { token });
        } else {
          throw err;
        }
      }
      router.push("/dashboard");
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof ApiError ? err.message : "Failed to accept invitation.");
    }
  };

  if (loading) return <main className="flex flex-1 items-center justify-center p-8">Loading...</main>;

  if (!token) {
    return (
      <main className="flex flex-1 items-center justify-center p-8 text-center">
        <p>No invitation token was provided.</p>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="flex flex-1 items-center justify-center p-8 text-center">
        <div className="max-w-sm">
          <h1 className="mb-2 text-2xl font-semibold">Log in to accept your invitation</h1>
          <p className="mb-6 text-zinc-600 dark:text-zinc-400">
            Log in or register with the email address that received this invitation, then return to
            this link.
          </p>
          <div className="flex justify-center gap-4">
            <Link className="rounded-full bg-zinc-900 px-5 py-2 font-medium text-white dark:bg-white dark:text-zinc-900" href="/login">
              Log in
            </Link>
            <Link className="rounded-full border border-zinc-300 px-5 py-2 font-medium dark:border-zinc-700" href="/register">
              Register
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex flex-1 items-center justify-center p-8 text-center">
      <div className="max-w-sm">
        <h1 className="mb-4 text-2xl font-semibold">Accept invitation</h1>
        {status === "error" && <p className="mb-4 text-red-600">{message}</p>}
        <button
          onClick={accept}
          disabled={status === "working"}
          className="rounded-full bg-zinc-900 px-6 py-3 font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900"
        >
          {status === "working" ? "Accepting..." : "Accept invitation"}
        </button>
      </div>
    </main>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense fallback={<main className="flex flex-1 items-center justify-center p-8">Loading...</main>}>
      <AcceptInvitationInner />
    </Suspense>
  );
}
