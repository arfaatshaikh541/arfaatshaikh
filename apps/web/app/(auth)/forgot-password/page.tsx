"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Button, FormRoot, TextInput } from "@gridkeep/ui";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthShell } from "@/components/AuthShell";
import { apiClient } from "@/lib/api-client";

const schema = z.object({ email: z.string().email("Enter a valid email address.") });
type FormValues = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    await apiClient.post("/api/auth/forgot-password", values);
    setSent(true);
  };

  if (sent) {
    return (
      <AuthShell title="Check your email" description="If an account exists for that address, we've sent a reset link.">
        <Link href="/login" className="text-sm text-ink-700 hover:underline">
          Back to sign in
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Reset your password" description="We'll email you a link to choose a new one.">
      <FormRoot onSubmit={handleSubmit(onSubmit)}>
        <TextInput
          label="Email address"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register("email")}
        />
        <Button type="submit" isLoading={isSubmitting} className="w-full">
          Send reset link
        </Button>
      </FormRoot>
    </AuthShell>
  );
}
