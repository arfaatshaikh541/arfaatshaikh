"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, FormRoot, TextInput } from "@gridkeep/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthShell } from "@/components/AuthShell";
import { apiClient, ApiError } from "@/lib/api-client";
import { useInvalidateAuth } from "@/lib/auth-context";
import type { LoginResponse, MfaRequiredResponse } from "@/lib/types";

const schema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

type FormValues = z.infer<typeof schema>;

const mfaSchema = z.object({
  code: z.string().min(6, "Enter the 6-digit code.").max(6),
});

type MfaFormValues = z.infer<typeof mfaSchema>;

export default function LoginPage() {
  const router = useRouter();
  const invalidateAuth = useInvalidateAuth();
  const [serverError, setServerError] = useState<string | null>(null);
  const [mfaChallengeToken, setMfaChallengeToken] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const {
    register: registerMfa,
    handleSubmit: handleMfaSubmit,
    formState: { errors: mfaErrors, isSubmitting: isMfaSubmitting },
  } = useForm<MfaFormValues>({ resolver: zodResolver(mfaSchema) });

  const finishLogin = (result: LoginResponse) => {
    invalidateAuth();
    if (result.user.is_platform_user) {
      router.replace("/platform");
    } else if (result.mfa_enrollment_required) {
      router.replace("/settings/security");
    } else if (result.memberships.length > 1 && !result.active_membership_id) {
      router.replace("/select-workspace");
    } else {
      router.replace("/dashboard");
    }
  };

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      const result = await apiClient.post<LoginResponse | MfaRequiredResponse>(
        "/api/auth/login",
        values,
      );
      if ("mfa_required" in result) {
        setMfaChallengeToken(result.mfa_challenge_token);
      } else {
        finishLogin(result);
      }
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    }
  };

  const onSubmitMfa = async (values: MfaFormValues) => {
    setServerError(null);
    try {
      const result = await apiClient.post<LoginResponse>("/api/auth/mfa/verify-login", {
        mfa_challenge_token: mfaChallengeToken,
        code: values.code,
      });
      finishLogin(result);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    }
  };

  if (mfaChallengeToken) {
    return (
      <AuthShell
        title="Enter your verification code"
        description="Open your authenticator app and enter the 6-digit code for GRIDKEEP."
      >
        <FormRoot onSubmit={handleMfaSubmit(onSubmitMfa)}>
          {serverError ? <Alert tone="error">{serverError}</Alert> : null}
          <TextInput
            label="Verification code"
            inputMode="numeric"
            autoComplete="one-time-code"
            error={mfaErrors.code?.message}
            {...registerMfa("code")}
          />
          <Button type="submit" isLoading={isMfaSubmitting} className="w-full">
            Verify
          </Button>
        </FormRoot>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Sign in" description="Access your organisation's security command centre.">
      <FormRoot onSubmit={handleSubmit(onSubmit)}>
        {serverError ? <Alert tone="error">{serverError}</Alert> : null}
        <TextInput
          label="Email address"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register("email")}
        />
        <TextInput
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register("password")}
        />
        <Button type="submit" isLoading={isSubmitting} className="w-full">
          Sign in
        </Button>
        <div className="flex justify-between text-xs text-ink-500">
          <Link href="/forgot-password" className="hover:text-ink-700">
            Forgot password?
          </Link>
          <Link href="/onboarding" className="hover:text-ink-700">
            Create a workspace
          </Link>
        </div>
      </FormRoot>
    </AuthShell>
  );
}
