"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Banner, Button, Card, TextField } from "@gridkeep/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiError, api } from "@/lib/api";
import { useSession } from "@/lib/session";

const schema = z.object({
  name: z.string().min(1, "Workspace name is required.").max(200),
});

type FormValues = z.infer<typeof schema>;

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: session, isLoading, isError } = useSession();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (!isLoading && (isError || !session)) {
      router.replace("/login");
    }
  }, [isLoading, isError, session, router]);

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      await api.post("/tenants", { name: values.name });
      await queryClient.invalidateQueries({ queryKey: ["session"] });
      router.push("/dashboard");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not create your workspace.");
    }
  };

  if (isLoading || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <p className="text-sm text-slate-500">Loading...</p>
      </div>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <Card className="w-full max-w-md">
        <h1 className="mb-1 text-xl font-semibold">Create your workspace</h1>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
          This is where your team will run campaigns, review leads, and manage exports. You can invite
          teammates once it&apos;s created.
        </p>

        {session.memberships.length > 0 && (
          <div className="mb-6">
            <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-200">
              Or switch to a workspace you already belong to:
            </p>
            <ul className="flex flex-col gap-2">
              {session.memberships.map((m) => (
                <li key={m.tenant_id}>
                  <button
                    type="button"
                    onClick={async () => {
                      await api.post("/tenants/switch", { tenant_id: m.tenant_id });
                      await queryClient.invalidateQueries({ queryKey: ["session"] });
                      router.push("/dashboard");
                    }}
                    className="w-full rounded-md border border-slate-200 px-3 py-2 text-left text-sm hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
                  >
                    {m.tenant_name} <span className="text-slate-400">({m.role_name})</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          <TextField label="Workspace name" error={errors.name?.message} {...register("name")} />
          {formError && <Banner tone="error">{formError}</Banner>}
          <Button type="submit" isLoading={isSubmitting} className="w-full">
            Create workspace
          </Button>
        </form>
      </Card>
    </main>
  );
}
