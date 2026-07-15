"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, FormRoot, TextInput } from "@gridkeep/ui";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthShell } from "@/components/AuthShell";
import { apiClient, ApiError } from "@/lib/api-client";
import { useInvalidateAuth } from "@/lib/auth-context";

const schema = z.object({
  full_name: z.string().min(2, "Enter your full name."),
  password: z.string().min(12, "Use at least 12 characters."),
});
type FormValues = z.infer<typeof schema>;

export default function AcceptInvitationPage() {
  return (
    <Suspense fallback={null}>
      <AcceptInvitationForm />
    </Suspense>
  );
}

function AcceptInvitationForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
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
      await apiClient.post("/api/auth/accept-invitation", { token, ...values });
      invalidateAuth();
      router.replace("/dashboard");
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "This invitation link is invalid or has expired.");
    }
  };

  if (!token) {
    return (
      <AuthShell title="Invalid invitation">
        <Alert tone="error">This invitation link is missing its token.</Alert>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Join your team on GRIDKEEP" description="Set your name and password to accept the invitation.">
      <FormRoot onSubmit={handleSubmit(onSubmit)}>
        {serverError ? <Alert tone="error">{serverError}</Alert> : null}
        <TextInput label="Full name" error={errors.full_name?.message} {...register("full_name")} />
        <TextInput
          label="Password"
          type="password"
          autoComplete="new-password"
          hint="At least 12 characters."
          error={errors.password?.message}
          {...register("password")}
        />
        <Button type="submit" isLoading={isSubmitting} className="w-full">
          Join workspace
        </Button>
      </FormRoot>
    </AuthShell>
  );
}
