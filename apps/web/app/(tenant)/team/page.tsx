"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Banner, Button, Card, TextField } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiError, api } from "@/lib/api";
import type { Invitation, Role } from "@/lib/types";
import { useState } from "react";

const inviteSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  role_id: z.string().min(1, "Choose a role."),
});

type InviteFormValues = z.infer<typeof inviteSchema>;

export default function TeamPage() {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const rolesQuery = useQuery<Role[]>({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/tenants/roles"),
  });
  const invitationsQuery = useQuery<Invitation[]>({
    queryKey: ["invitations"],
    queryFn: () => api.get<Invitation[]>("/tenants/invitations"),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<InviteFormValues>({ resolver: zodResolver(inviteSchema) });

  const onSubmit = async (values: InviteFormValues) => {
    setFormError(null);
    setSuccessMessage(null);
    try {
      await api.post("/tenants/invitations", values);
      setSuccessMessage(`Invitation sent to ${values.email}.`);
      reset();
      queryClient.invalidateQueries({ queryKey: ["invitations"] });
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not send the invitation.");
    }
  };

  const canManageUsers = !rolesQuery.isError;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Team</h1>

      {canManageUsers ? (
        <Card>
          <h2 className="mb-4 text-lg font-medium">Invite a teammate</h2>
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4 sm:flex-row sm:items-end">
            <div className="flex-1">
              <TextField label="Email" type="email" error={errors.email?.message} {...register("email")} />
            </div>
            <div className="flex-1">
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">Role</label>
              <select
                {...register("role_id")}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                defaultValue=""
              >
                <option value="" disabled>
                  Select a role
                </option>
                {rolesQuery.data?.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
              </select>
              {errors.role_id && <p className="mt-1 text-xs text-red-600">{errors.role_id.message}</p>}
            </div>
            <Button type="submit" isLoading={isSubmitting}>
              Send invite
            </Button>
          </form>
          {successMessage && (
            <div className="mt-4">
              <Banner tone="success">{successMessage}</Banner>
            </div>
          )}
          {formError && (
            <div className="mt-4">
              <Banner tone="error">{formError}</Banner>
            </div>
          )}
        </Card>
      ) : (
        <Banner tone="info">You don&apos;t have permission to manage team members.</Banner>
      )}

      <Card>
        <h2 className="mb-4 text-lg font-medium">Pending invitations</h2>
        {invitationsQuery.data && invitationsQuery.data.length > 0 ? (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {invitationsQuery.data.map((invitation) => (
              <li key={invitation.id} className="flex items-center justify-between py-2 text-sm">
                <span>{invitation.email}</span>
                <span className="capitalize text-slate-500 dark:text-slate-400">{invitation.status}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">No invitations yet.</p>
        )}
      </Card>
    </div>
  );
}
