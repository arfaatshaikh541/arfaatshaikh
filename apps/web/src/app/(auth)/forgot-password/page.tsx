"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { forgotPasswordSchema, type ForgotPasswordInput } from "@leadflow/shared-types";
import { Alert, Button, FormError, Input, Label } from "@leadflow/ui";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { apiFetch } from "@/lib/api-client";

export default function ForgotPasswordPage() {
  const [done, setDone] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordInput>({ resolver: zodResolver(forgotPasswordSchema) });

  const onSubmit = async (values: ForgotPasswordInput) => {
    await apiFetch("/auth/forgot-password", { method: "POST", body: values, withTenant: false });
    setDone(true);
  };

  if (done) {
    return (
      <Alert tone="success">
        If that email exists, we&apos;ve sent a password reset link. In local development, check
        Mailhog at <code>http://localhost:8025</code>.
      </Alert>
    );
  }

  return (
    <div className="rounded-lg border border-surface-800 bg-surface-900 p-6">
      <h1 className="mb-2 text-lg font-semibold text-surface-50">Forgot your password?</h1>
      <p className="mb-6 text-sm text-surface-400">
        We&apos;ll email you a link to reset it.
      </p>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="mb-6">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" {...register("email")} />
          <FormError message={errors.email?.message} />
        </div>
        <Button type="submit" className="w-full" loading={isSubmitting}>
          Send reset link
        </Button>
      </form>
    </div>
  );
}
