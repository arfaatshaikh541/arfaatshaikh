"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, FormRoot, TextInput } from "@gridkeep/ui";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthShell } from "@/components/AuthShell";
import { apiClient, ApiError } from "@/lib/api-client";

const schema = z.object({
  organisation_name: z.string().min(2, "Enter your organisation's name."),
  full_name: z.string().min(2, "Enter your full name."),
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(12, "Use at least 12 characters."),
});

type FormValues = z.infer<typeof schema>;

export default function OnboardingPage() {
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
      await apiClient.post("/api/tenancy/onboarding", values);
      setDone(true);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    }
  };

  if (done) {
    return (
      <AuthShell title="Check your email" description="We've sent a verification link to confirm your address.">
        <Alert tone="success">
          Almost there — verify your email to activate your workspace, then{" "}
          <Link href="/login" className="underline">
            sign in
          </Link>
          .
        </Alert>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Create your workspace" description="Set up GRIDKEEP for your organisation.">
      <FormRoot onSubmit={handleSubmit(onSubmit)}>
        {serverError ? <Alert tone="error">{serverError}</Alert> : null}
        <TextInput
          label="Organisation name"
          error={errors.organisation_name?.message}
          {...register("organisation_name")}
        />
        <TextInput label="Your full name" error={errors.full_name?.message} {...register("full_name")} />
        <TextInput
          label="Work email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register("email")}
        />
        <TextInput
          label="Password"
          type="password"
          autoComplete="new-password"
          hint="At least 12 characters."
          error={errors.password?.message}
          {...register("password")}
        />
        <Button type="submit" isLoading={isSubmitting} className="w-full">
          Create workspace
        </Button>
        <p className="text-center text-xs text-ink-500">
          Already have an account?{" "}
          <Link href="/login" className="text-ink-700 hover:underline">
            Sign in
          </Link>
        </p>
      </FormRoot>
    </AuthShell>
  );
}
