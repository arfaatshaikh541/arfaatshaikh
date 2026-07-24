"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { validateWithZod } from "@/lib/validate-form";

interface Operator {
  id: string;
}

const schema = z.object({
  legal_name: z.string().min(2, "Required"),
  display_name: z.string().optional(),
  country: z.string().length(2, "Use a 2-letter country code, e.g. AE"),
});
type FormValues = z.infer<typeof schema>;

export default function OperatorOnboardingPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<FormValues>();

  const onSubmit = async (data: FormValues) => {
    setServerError(null);
    const valid = validateWithZod(schema, data, form.setError);
    if (!valid) return;
    try {
      const operator = await api.post<Operator>("/api/v1/operators", valid);
      router.push(`/dashboard/operator/${operator.id}`);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Failed to submit operator application.");
    }
  };

  return (
    <main id="main-content" className="flex flex-1 items-center justify-center p-4 sm:p-8">
      <div className="w-full max-w-md rounded-xl border border-zinc-200 p-8 dark:border-zinc-800">
        <h1 className="mb-2 text-2xl font-semibold">Apply as a telecom operator</h1>
        <p className="mb-6 text-sm text-zinc-600 dark:text-zinc-400">
          Your application starts in &ldquo;pending application&rdquo; status until a GRIDKEEP
          platform administrator reviews and approves it.
        </p>
        <form noValidate className="flex flex-col gap-4" onSubmit={form.handleSubmit(onSubmit)}>
          <label className="flex flex-col gap-1 text-sm">
            Legal name
            <input
              className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
              {...form.register("legal_name")}
            />
            {form.formState.errors.legal_name && (
              <span className="text-red-600">{form.formState.errors.legal_name.message}</span>
            )}
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Display name (optional)
            <input
              className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
              {...form.register("display_name")}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Country (ISO 3166-1 alpha-2)
            <input
              className="rounded-md border border-zinc-300 px-3 py-2 uppercase dark:border-zinc-700 dark:bg-zinc-900"
              maxLength={2}
              {...form.register("country")}
            />
            {form.formState.errors.country && (
              <span className="text-red-600">{form.formState.errors.country.message}</span>
            )}
          </label>
          {serverError && <p className="text-sm text-red-600">{serverError}</p>}
          <button
            type="submit"
            disabled={form.formState.isSubmitting}
            className="rounded-md bg-zinc-900 px-4 py-2 font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900"
          >
            Submit application
          </button>
        </form>
      </div>
    </main>
  );
}
