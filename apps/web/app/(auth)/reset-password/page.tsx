"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, FormRoot, TextInput } from "@gridkeep/ui";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthShell } from "@/components/AuthShell";
import { apiClient, ApiError } from "@/lib/api-client";

const schema = z.object({ new_password: z.string().min(12, "Use at least 12 characters.") });
type FormValues = z.infer<typeof schema>;

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [serverError, setServerError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      await apiClient.post("/api/auth/reset-password", { token, new_password: values.new_password });
      setDone(true);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "This reset link is invalid or has expired.");
    }
  };

  if (!token) {
    return (
      <AuthShell title="Invalid link">
        <Alert tone="error">This password reset link is missing its token.</Alert>
      </AuthShell>
    );
  }

  if (done) {
    return (
      <AuthShell title="Password updated">
        <Alert tone="success">Your password has been changed.</Alert>
        <Link href="/login" className="mt-4 block text-sm text-ink-700 hover:underline">
          Continue to sign in
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Choose a new password">
      <FormRoot onSubmit={handleSubmit(onSubmit)}>
        {serverError ? <Alert tone="error">{serverError}</Alert> : null}
        <TextInput
          label="New password"
          type="password"
          autoComplete="new-password"
          hint="At least 12 characters."
          error={errors.new_password?.message}
          {...register("new_password")}
        />
        <Button type="submit" isLoading={isSubmitting} className="w-full">
          Update password
        </Button>
      </FormRoot>
    </AuthShell>
  );
}
