"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Banner, Button, Card, TextField } from "@gridkeep/ui";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiError, api } from "@/lib/api";

const schema = z.object({
  new_password: z
    .string()
    .min(12, "Use at least 12 characters.")
    .refine(
      (v) => v.toLowerCase() !== v && v.toUpperCase() !== v && /\d/.test(v),
      "Include upper, lower, and numeric characters.",
    ),
});

type FormValues = z.infer<typeof schema>;

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [success, setSuccess] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    if (!token) {
      setFormError("This reset link is missing its token.");
      return;
    }
    setFormError(null);
    try {
      await api.post("/auth/password-reset/confirm", { token, new_password: values.new_password });
      setSuccess(true);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  if (success) {
    return (
      <Card className="w-full max-w-sm text-center">
        <Banner tone="success">Your password has been reset. All previous sessions were signed out.</Banner>
        <Link href="/login" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">
          Continue to sign in
        </Link>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-sm">
      <h1 className="mb-6 text-xl font-semibold">Choose a new password</h1>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          hint="At least 12 characters, with upper, lower, and numeric characters."
          error={errors.new_password?.message}
          {...register("new_password")}
        />
        {formError && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {formError}
          </p>
        )}
        <Button type="submit" isLoading={isSubmitting} className="mt-2 w-full">
          Reset password
        </Button>
      </form>
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <Suspense fallback={<p className="text-sm text-slate-500">Loading...</p>}>
        <ResetPasswordContent />
      </Suspense>
    </main>
  );
}
