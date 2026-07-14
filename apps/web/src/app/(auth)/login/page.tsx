"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { loginSchema, type LoginInput, type CurrentUser } from "@leadflow/shared-types";
import { Alert, Button, FormError, Input, Label } from "@leadflow/ui";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError, apiFetch } from "@/lib/api-client";

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (values: LoginInput) => {
    setServerError(null);
    try {
      await apiFetch("/auth/login", { method: "POST", body: values, withTenant: false });
      await queryClient.invalidateQueries({ queryKey: ["current-user"] });
      const user = await apiFetch<CurrentUser>("/auth/me", { withTenant: false });
      router.push(user.is_platform_super_admin ? "/platform" : "/dashboard");
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  return (
    <div className="rounded-lg border border-surface-800 bg-surface-900 p-6">
      <h1 className="mb-6 text-lg font-semibold text-surface-50">Sign in</h1>
      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="mb-4">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" {...register("email")} />
          <FormError message={errors.email?.message} />
        </div>
        <div className="mb-6">
          <div className="mb-1.5 flex items-center justify-between">
            <Label htmlFor="password" className="mb-0">
              Password
            </Label>
            <Link href="/forgot-password" className="text-xs text-accent-500 hover:text-accent-400">
              Forgot password?
            </Link>
          </div>
          <Input id="password" type="password" autoComplete="current-password" {...register("password")} />
          <FormError message={errors.password?.message} />
        </div>
        <Button type="submit" className="w-full" loading={isSubmitting}>
          Sign in
        </Button>
      </form>
      <p className="mt-4 text-center text-xs text-surface-500">
        New here?{" "}
        <Link href="/signup" className="text-accent-500 hover:text-accent-400">
          Create a workspace
        </Link>
        .
      </p>
      <p className="mt-2 text-center text-xs text-surface-500">
        Invited to a team? Use the link from your invitation email to{" "}
        <Link href="/accept-invitation" className="text-accent-500 hover:text-accent-400">
          accept it
        </Link>
        .
      </p>
    </div>
  );
}
