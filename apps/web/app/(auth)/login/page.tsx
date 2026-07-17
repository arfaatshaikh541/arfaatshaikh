"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Button, Card, TextField } from "@gridkeep/ui";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiError, api } from "@/lib/api";
import { useState } from "react";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (values: LoginFormValues) => {
    setFormError(null);
    try {
      await api.post("/auth/login", values);
      // The session query cache may already hold a stale (logged-out, or
      // different-user) result - invalidate it so the destination page's
      // useSession() call refetches instead of trusting stale cached data.
      await queryClient.invalidateQueries({ queryKey: ["session"] });
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("Something went wrong. Please try again.");
      }
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <Card className="w-full max-w-sm">
        <h1 className="mb-1 text-xl font-semibold">Sign in to GRIDKEEP</h1>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">Lead Intelligence workspace</p>

        <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            error={errors.email?.message}
            {...register("email")}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            error={errors.password?.message}
            {...register("password")}
          />

          {formError && (
            <p role="alert" className="text-sm text-red-600 dark:text-red-400">
              {formError}
            </p>
          )}

          <Button type="submit" isLoading={isSubmitting} className="mt-2 w-full">
            Sign in
          </Button>
        </form>

        <div className="mt-6 flex flex-col gap-2 text-sm text-slate-500 dark:text-slate-400">
          <Link href="/forgot-password" className="hover:underline">
            Forgot your password?
          </Link>
          <p>
            Don&apos;t have an account?{" "}
            <Link href="/register" className="font-medium text-brand-600 hover:underline">
              Register
            </Link>
          </p>
        </div>
      </Card>
    </main>
  );
}
