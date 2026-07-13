"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { resetPasswordSchema, type ResetPasswordInput } from "@leadflow/shared-types";
import { Alert, Button, FormError, Input, Label } from "@leadflow/ui";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError, apiFetch } from "@/lib/api-client";

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
  const [done, setDone] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordInput>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { token },
  });

  const onSubmit = async (values: ResetPasswordInput) => {
    setServerError(null);
    try {
      await apiFetch("/auth/reset-password", {
        method: "POST",
        body: { token: values.token, new_password: values.newPassword },
        withTenant: false,
      });
      setDone(true);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  if (done) {
    return (
      <Alert tone="success">
        Your password has been reset.{" "}
        <Link href="/login" className="underline">
          Sign in
        </Link>
        .
      </Alert>
    );
  }

  return (
    <div className="rounded-lg border border-surface-800 bg-surface-900 p-6">
      <h1 className="mb-6 text-lg font-semibold text-surface-50">Reset your password</h1>
      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <input type="hidden" {...register("token")} />
        <div className="mb-4">
          <Label htmlFor="newPassword">New password</Label>
          <Input id="newPassword" type="password" autoComplete="new-password" {...register("newPassword")} />
          <FormError message={errors.newPassword?.message} />
        </div>
        <div className="mb-6">
          <Label htmlFor="confirmPassword">Confirm new password</Label>
          <Input
            id="confirmPassword"
            type="password"
            autoComplete="new-password"
            {...register("confirmPassword")}
          />
          <FormError message={errors.confirmPassword?.message} />
        </div>
        <Button type="submit" className="w-full" loading={isSubmitting} disabled={!token}>
          Reset password
        </Button>
        {!token ? (
          <p className="mt-2 text-xs text-red-400">Missing or invalid reset link.</p>
        ) : null}
      </form>
    </div>
  );
}
