"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { acceptInvitationSchema, type AcceptInvitationInput } from "@leadflow/shared-types";
import { Alert, Button, FormError, Input, Label } from "@leadflow/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError, apiFetch } from "@/lib/api-client";

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
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AcceptInvitationInput>({
    resolver: zodResolver(acceptInvitationSchema),
    defaultValues: { token },
  });

  const onSubmit = async (values: AcceptInvitationInput) => {
    setServerError(null);
    try {
      await apiFetch("/invitations/accept", {
        method: "POST",
        body: {
          token: values.token,
          first_name: values.firstName,
          last_name: values.lastName,
          password: values.password,
        },
        withTenant: false,
      });
      await queryClient.invalidateQueries({ queryKey: ["current-user"] });
      router.push("/dashboard");
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  return (
    <div className="rounded-lg border border-surface-800 bg-surface-900 p-6">
      <h1 className="mb-6 text-lg font-semibold text-surface-50">Accept your invitation</h1>
      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <input type="hidden" {...register("token")} />
        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="firstName">First name</Label>
            <Input id="firstName" autoComplete="given-name" {...register("firstName")} />
            <FormError message={errors.firstName?.message} />
          </div>
          <div>
            <Label htmlFor="lastName">Last name</Label>
            <Input id="lastName" autoComplete="family-name" {...register("lastName")} />
            <FormError message={errors.lastName?.message} />
          </div>
        </div>
        <div className="mb-4">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
          <FormError message={errors.password?.message} />
        </div>
        <div className="mb-6">
          <Label htmlFor="confirmPassword">Confirm password</Label>
          <Input
            id="confirmPassword"
            type="password"
            autoComplete="new-password"
            {...register("confirmPassword")}
          />
          <FormError message={errors.confirmPassword?.message} />
        </div>
        <Button type="submit" className="w-full" loading={isSubmitting} disabled={!token}>
          Create account
        </Button>
        {!token ? (
          <p className="mt-2 text-xs text-red-400">Missing or invalid invitation link.</p>
        ) : null}
      </form>
    </div>
  );
}
