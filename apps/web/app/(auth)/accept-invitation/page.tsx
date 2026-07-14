"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import { useInvalidateAuth } from "@/lib/auth-context";
import type { CurrentUser } from "@/lib/types";

const schema = z
  .object({
    first_name: z.string().min(1, "First name is required."),
    last_name: z.string().min(1, "Last name is required."),
    password: z.string().min(10, "Password must be at least 10 characters."),
    confirm_password: z.string(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match.",
    path: ["confirm_password"],
  });

type FormValues = z.infer<typeof schema>;

function AcceptInvitationForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const invalidateAuth = useInvalidateAuth();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      api.post<CurrentUser>("/auth/accept-invitation", {
        token,
        password: values.password,
        first_name: values.first_name,
        last_name: values.last_name,
      }),
    onSuccess: async () => {
      await invalidateAuth();
      router.replace("/dashboard");
    },
  });

  if (!token) {
    return <Alert tone="error">This invitation link is missing a token.</Alert>;
  }

  return (
    <Card>
      <CardHeader title="Accept your invitation" description="Create your account to join the team." />
      <form className="space-y-4" onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
        {mutation.isError && (
          <Alert tone="error">
            {mutation.error instanceof ApiError ? mutation.error.message : "Unable to accept this invitation."}
          </Alert>
        )}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="first_name">First name</Label>
            <Input id="first_name" {...register("first_name")} />
            <FieldError>{errors.first_name?.message}</FieldError>
          </div>
          <div>
            <Label htmlFor="last_name">Last name</Label>
            <Input id="last_name" {...register("last_name")} />
            <FieldError>{errors.last_name?.message}</FieldError>
          </div>
        </div>
        <div>
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
          <FieldError>{errors.password?.message}</FieldError>
        </div>
        <div>
          <Label htmlFor="confirm_password">Confirm password</Label>
          <Input id="confirm_password" type="password" autoComplete="new-password" {...register("confirm_password")} />
          <FieldError>{errors.confirm_password?.message}</FieldError>
        </div>
        <Button type="submit" className="w-full" disabled={mutation.isPending}>
          {mutation.isPending ? "Creating account…" : "Accept invitation"}
        </Button>
      </form>
    </Card>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense fallback={null}>
      <AcceptInvitationForm />
    </Suspense>
  );
}
