"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Banner, Button, Card, TextField } from "@gridkeep/ui";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api } from "@/lib/api";
import { useState } from "react";

const schema = z.object({
  email: z.string().email("Enter a valid email address."),
});

type FormValues = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    // The API returns 202 regardless of whether the account exists, so
    // there is nothing to branch on here - this deliberately can't leak
    // account existence to the UI either.
    await api.post("/auth/password-reset/request", values);
    setSubmitted(true);
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <Card className="w-full max-w-sm">
        <h1 className="mb-1 text-xl font-semibold">Reset your password</h1>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
          We&apos;ll email you a link to reset it.
        </p>

        {submitted ? (
          <Banner tone="info">
            If an account exists for that email, a reset link has been sent.
          </Banner>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
            <TextField
              label="Email"
              type="email"
              autoComplete="email"
              error={errors.email?.message}
              {...register("email")}
            />
            <Button type="submit" isLoading={isSubmitting} className="mt-2 w-full">
              Send reset link
            </Button>
          </form>
        )}

        <p className="mt-6 text-sm text-slate-500 dark:text-slate-400">
          <Link href="/login" className="font-medium text-brand-600 hover:underline">
            Back to sign in
          </Link>
        </p>
      </Card>
    </main>
  );
}
