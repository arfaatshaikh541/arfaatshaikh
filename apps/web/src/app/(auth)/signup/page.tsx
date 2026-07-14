"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { signupSchema, type SignupInput, type CurrentUser } from "@leadflow/shared-types";
import { Alert, Button, FormError, Input, Label } from "@leadflow/ui";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError, apiFetch } from "@/lib/api-client";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default function SignupPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const [slugEdited, setSlugEdited] = useState(false);
  const {
    register,
    handleSubmit,
    setValue,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<SignupInput>({ resolver: zodResolver(signupSchema) });

  const onSubmit = async (values: SignupInput) => {
    setServerError(null);
    try {
      await apiFetch<{ user: CurrentUser }>("/auth/signup", {
        method: "POST",
        body: {
          name: values.name,
          slug: values.slug,
          owner_email: values.ownerEmail,
          owner_first_name: values.ownerFirstName,
          owner_last_name: values.ownerLastName,
          owner_password: values.ownerPassword,
        },
        withTenant: false,
      });
      await queryClient.invalidateQueries({ queryKey: ["current-user"] });
      router.push("/onboarding");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setServerError("That workspace URL is already taken. Please choose another.");
      } else if (err instanceof ApiError && err.status === 429) {
        setServerError("Too many signup attempts from this network. Please try again later.");
      } else {
        setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
      }
    }
  };

  return (
    <div className="rounded-lg border border-surface-800 bg-surface-900 p-6">
      <h1 className="mb-1 text-lg font-semibold text-surface-50">Create your workspace</h1>
      <p className="mb-6 text-sm text-surface-400">
        Start capturing and booking leads in minutes. No credit card required.
      </p>
      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="mb-4">
          <Label htmlFor="name">Company name</Label>
          <Input
            id="name"
            autoComplete="organization"
            {...register("name", {
              onChange: (e) => {
                if (!slugEdited) setValue("slug", slugify(e.target.value as string));
              },
            })}
          />
          <FormError message={errors.name?.message} />
        </div>
        <div className="mb-4">
          <Label htmlFor="slug">Workspace URL</Label>
          <div className="flex items-center gap-2">
            <span className="text-sm text-surface-500">leadflow.app/</span>
            <Input
              id="slug"
              {...register("slug", {
                onChange: () => setSlugEdited(getValues("slug") !== slugify(getValues("name") ?? "")),
              })}
            />
          </div>
          <FormError message={errors.slug?.message} />
        </div>
        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="ownerFirstName">First name</Label>
            <Input id="ownerFirstName" autoComplete="given-name" {...register("ownerFirstName")} />
            <FormError message={errors.ownerFirstName?.message} />
          </div>
          <div>
            <Label htmlFor="ownerLastName">Last name</Label>
            <Input id="ownerLastName" autoComplete="family-name" {...register("ownerLastName")} />
            <FormError message={errors.ownerLastName?.message} />
          </div>
        </div>
        <div className="mb-4">
          <Label htmlFor="ownerEmail">Work email</Label>
          <Input id="ownerEmail" type="email" autoComplete="email" {...register("ownerEmail")} />
          <FormError message={errors.ownerEmail?.message} />
        </div>
        <div className="mb-4">
          <Label htmlFor="ownerPassword">Password</Label>
          <Input
            id="ownerPassword"
            type="password"
            autoComplete="new-password"
            {...register("ownerPassword")}
          />
          <FormError message={errors.ownerPassword?.message} />
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
        <Button type="submit" className="w-full" loading={isSubmitting}>
          Create workspace
        </Button>
      </form>
      <p className="mt-6 text-center text-xs text-surface-500">
        Already have an account?{" "}
        <Link href="/login" className="text-accent-500 hover:text-accent-400">
          Sign in
        </Link>
        .
      </p>
    </div>
  );
}
