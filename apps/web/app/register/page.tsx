"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { validateWithZod } from "@/lib/validate-form";

const registerSchema = z.object({
  email: z.string().email(),
  password: z.string().min(12, "Password must be at least 12 characters"),
});
type RegisterForm = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const [done, setDone] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<RegisterForm>();

  const onSubmit = async (data: RegisterForm) => {
    setServerError(null);
    const valid = validateWithZod(registerSchema, data, form.setError);
    if (!valid) return;
    try {
      await api.post("/api/v1/auth/register", valid);
      setDone(true);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Registration failed.");
    }
  };

  if (done) {
    return (
      <main className="flex flex-1 items-center justify-center p-8">
        <div className="max-w-sm text-center">
          <h1 className="mb-2 text-2xl font-semibold">Check your email</h1>
          <p className="text-zinc-600 dark:text-zinc-400">
            We sent a verification link to your email address. Verify it, then log in.
          </p>
          <Link className="mt-6 inline-block underline" href="/login">
            Back to login
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="flex flex-1 items-center justify-center p-8">
      <div className="w-full max-w-sm rounded-xl border border-zinc-200 p-8 dark:border-zinc-800">
        <h1 className="mb-6 text-2xl font-semibold">Create your GRIDKEEP account</h1>
        <form noValidate className="flex flex-col gap-4" onSubmit={form.handleSubmit(onSubmit)}>
          <label className="flex flex-col gap-1 text-sm">
            Email
            <input
              type="email"
              className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
              {...form.register("email")}
            />
            {form.formState.errors.email && (
              <span className="text-red-600">{form.formState.errors.email.message}</span>
            )}
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Password
            <input
              type="password"
              className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
              {...form.register("password")}
            />
            {form.formState.errors.password && (
              <span className="text-red-600">{form.formState.errors.password.message}</span>
            )}
          </label>
          {serverError && <p className="text-sm text-red-600">{serverError}</p>}
          <button
            type="submit"
            disabled={form.formState.isSubmitting}
            className="rounded-md bg-zinc-900 px-4 py-2 font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900"
          >
            {form.formState.isSubmitting ? "Creating account..." : "Create account"}
          </button>
        </form>
        <p className="mt-6 text-sm text-zinc-600 dark:text-zinc-400">
          Already have an account?{" "}
          <Link className="font-medium underline" href="/login">
            Log in
          </Link>
        </p>
      </div>
    </main>
  );
}
