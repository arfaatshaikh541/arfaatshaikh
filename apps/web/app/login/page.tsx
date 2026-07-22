"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { validateWithZod } from "@/lib/validate-form";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1, "Password is required"),
});
type LoginForm = z.infer<typeof loginSchema>;

const mfaSchema = z.object({
  code: z.string().length(6, "Enter the 6-digit code"),
});
type MfaForm = z.infer<typeof mfaSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [mfaChallenge, setMfaChallenge] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const loginForm = useForm<LoginForm>();
  const mfaForm = useForm<MfaForm>();

  const onLogin = async (data: LoginForm) => {
    setServerError(null);
    const valid = validateWithZod(loginSchema, data, loginForm.setError);
    if (!valid) return;
    try {
      const result = await api.post<{ mfa_required: boolean; mfa_challenge?: string }>(
        "/api/v1/auth/login",
        valid
      );
      if (result.mfa_required && result.mfa_challenge) {
        setMfaChallenge(result.mfa_challenge);
        return;
      }
      await refresh();
      router.push("/dashboard");
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Login failed.");
    }
  };

  const onMfaVerify = async (data: MfaForm) => {
    if (!mfaChallenge) return;
    setServerError(null);
    const valid = validateWithZod(mfaSchema, data, mfaForm.setError);
    if (!valid) return;
    try {
      await api.post("/api/v1/auth/mfa/verify", { mfa_challenge: mfaChallenge, code: valid.code });
      await refresh();
      router.push("/dashboard");
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "MFA verification failed.");
    }
  };

  return (
    <main className="flex flex-1 items-center justify-center p-8">
      <div className="w-full max-w-sm rounded-xl border border-zinc-200 p-8 dark:border-zinc-800">
        <h1 className="mb-6 text-2xl font-semibold">Log in to GRIDKEEP</h1>

        {!mfaChallenge ? (
          <form noValidate className="flex flex-col gap-4" onSubmit={loginForm.handleSubmit(onLogin)}>
            <label className="flex flex-col gap-1 text-sm">
              Email
              <input
                type="email"
                className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                {...loginForm.register("email")}
              />
              {loginForm.formState.errors.email && (
                <span className="text-red-600">{loginForm.formState.errors.email.message}</span>
              )}
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Password
              <input
                type="password"
                className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
                {...loginForm.register("password")}
              />
              {loginForm.formState.errors.password && (
                <span className="text-red-600">{loginForm.formState.errors.password.message}</span>
              )}
            </label>
            {serverError && <p className="text-sm text-red-600">{serverError}</p>}
            <button
              type="submit"
              disabled={loginForm.formState.isSubmitting}
              className="rounded-md bg-zinc-900 px-4 py-2 font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900"
            >
              {loginForm.formState.isSubmitting ? "Logging in..." : "Log in"}
            </button>
          </form>
        ) : (
          <form noValidate className="flex flex-col gap-4" onSubmit={mfaForm.handleSubmit(onMfaVerify)}>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Enter the 6-digit code from your authenticator app.
            </p>
            <label className="flex flex-col gap-1 text-sm">
              MFA code
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                className="rounded-md border border-zinc-300 px-3 py-2 tracking-widest dark:border-zinc-700 dark:bg-zinc-900"
                {...mfaForm.register("code")}
              />
              {mfaForm.formState.errors.code && (
                <span className="text-red-600">{mfaForm.formState.errors.code.message}</span>
              )}
            </label>
            {serverError && <p className="text-sm text-red-600">{serverError}</p>}
            <button
              type="submit"
              disabled={mfaForm.formState.isSubmitting}
              className="rounded-md bg-zinc-900 px-4 py-2 font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900"
            >
              Verify
            </button>
          </form>
        )}

        <p className="mt-6 text-sm text-zinc-600 dark:text-zinc-400">
          No account?{" "}
          <Link className="font-medium underline" href="/register">
            Register
          </Link>
        </p>
      </div>
    </main>
  );
}
