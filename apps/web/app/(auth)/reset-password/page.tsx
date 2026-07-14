"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";

const schema = z
  .object({
    new_password: z.string().min(10, "Password must be at least 10 characters."),
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match.",
    path: ["confirm_password"],
  });

type FormValues = z.infer<typeof schema>;

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const mutation = useMutation({
    mutationFn: (values: FormValues) => api.post("/auth/reset-password", { token, new_password: values.new_password }),
  });

  if (!token) {
    return <Alert tone="error">This reset link is missing a token. Request a new one.</Alert>;
  }

  return (
    <Card>
      <CardHeader title="Set a new password" />
      {mutation.isSuccess ? (
        <Alert tone="success">
          Your password has been reset. <Link href="/login" className="underline">Sign in</Link>.
        </Alert>
      ) : (
        <form className="space-y-4" onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate>
          {mutation.isError && (
            <Alert tone="error">
              {mutation.error instanceof ApiError ? mutation.error.message : "Unable to reset password."}
            </Alert>
          )}
          <div>
            <Label htmlFor="new_password">New password</Label>
            <Input id="new_password" type="password" autoComplete="new-password" {...register("new_password")} />
            <FieldError>{errors.new_password?.message}</FieldError>
          </div>
          <div>
            <Label htmlFor="confirm_password">Confirm password</Label>
            <Input id="confirm_password" type="password" autoComplete="new-password" {...register("confirm_password")} />
            <FieldError>{errors.confirm_password?.message}</FieldError>
          </div>
          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? "Resetting…" : "Reset password"}
          </Button>
        </form>
      )}
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
