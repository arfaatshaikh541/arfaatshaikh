"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, FormRoot } from "@gridkeep/ui";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthShell } from "@/components/AuthShell";
import { apiClient, ApiError } from "@/lib/api-client";

const schema = z.object({
  reason: z
    .string()
    .min(1, "Tell your admin what happened — this is shown to them when they review your request.")
    .max(500),
});
type FormValues = z.infer<typeof schema>;

// Hardening-programme Milestone 2: the self-service MFA-lockout recovery
// path Milestone 24's backup codes don't fully close — a user who has
// lost their authenticator device AND every backup code. Reachable only
// from the login page's MFA-challenge screen, which carries the real
// challenge token here as a query param; this page never accepts an
// arbitrary token typed by hand as proof of anything by itself — the
// backend independently re-validates it against a real, unexpired
// mfa_challenge_tokens row before creating a request.
export default function RecoveryRequestPage() {
  // `useSearchParams()` opts the page out of static rendering and must be
  // wrapped in a Suspense boundary in the App Router, or `next build`
  // fails prerendering with "should be wrapped in a suspense boundary."
  return (
    <Suspense fallback={null}>
      <RecoveryRequestForm />
    </Suspense>
  );
}

function RecoveryRequestForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [submitted, setSubmitted] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      await apiClient.post("/api/auth/recovery/request", {
        mfa_challenge_token: token,
        reason: values.reason,
      });
      setSubmitted(true);
    } catch (err) {
      setServerError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Please sign in again and retry from there.",
      );
    }
  };

  if (!token) {
    return (
      <AuthShell
        title="Account recovery"
        description="This page only works when reached from a sign-in attempt."
      >
        <Link href="/login" className="text-sm text-ink-700 hover:underline">
          Back to sign in
        </Link>
      </AuthShell>
    );
  }

  if (submitted) {
    return (
      <AuthShell
        title="Request sent"
        description="A workspace administrator, other than you, needs to review and approve this before your account is recovered. You'll need to contact them directly — GRIDKEEP does not notify them automatically yet."
      >
        <Link href="/login" className="text-sm text-ink-700 hover:underline">
          Back to sign in
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Request account recovery"
      description="A different administrator in your workspace will need to review and approve this — never yourself, and never automatically. Explain what happened so they can make an informed decision."
    >
      <FormRoot onSubmit={handleSubmit(onSubmit)}>
        {serverError ? <Alert tone="error">{serverError}</Alert> : null}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="reason" className="text-sm font-medium text-ink-700">
            What happened?
          </label>
          <textarea
            id="reason"
            rows={4}
            placeholder="E.g. lost my phone with the authenticator app, and I can't find where I saved my backup codes."
            className="rounded border border-surface-border bg-surface-800 px-3 py-2 text-sm text-ink-900"
            {...register("reason")}
          />
          {errors.reason ? <p className="text-xs text-severity-critical">{errors.reason.message}</p> : null}
        </div>
        <Button type="submit" isLoading={isSubmitting} className="w-full">
          Send recovery request
        </Button>
      </FormRoot>
    </AuthShell>
  );
}
