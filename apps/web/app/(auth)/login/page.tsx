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
import type { LoginResponse } from "@/lib/types";

const schema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const invalidateAuth = useInvalidateAuth();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      const result = await apiClient.post<LoginResponse>("/api/auth/login", values);
      invalidateAuth();
      if (result.memberships.length > 1 && !result.active_membership_id) {
        router.replace("/select-workspace");
      } else {
        router.replace("/dashboard");
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setServerError(err.message);
      } else {
        setServerError("Something went wrong. Please try again.");
      }
    }
  };

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
