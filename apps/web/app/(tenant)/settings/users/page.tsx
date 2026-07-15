"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, Card, CardHeader, FormRoot, StatusBadge, TextInput } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { MembershipRead, RoleRead } from "@/lib/types";

const schema = z.object({
  email: z.string().email("Enter a valid email address."),
  role_name: z.string().min(1, "Choose a role."),
});
type FormValues = z.infer<typeof schema>;

export default function UsersSettingsPage() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const canManage = hasPermission("users.manage");
  const [serverError, setServerError] = useState<string | null>(null);
  const [inviteSent, setInviteSent] = useState(false);

  const membersQuery = useQuery({
    queryKey: ["users"],
    queryFn: () => apiClient.get<MembershipRead[]>("/api/users"),
    enabled: canManage,
  });

  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => apiClient.get<RoleRead[]>("/api/roles"),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  if (!canManage) {
    return <Alert tone="info">You don&apos;t have permission to manage workspace members.</Alert>;
  }

  const onInvite = async (values: FormValues) => {
    setServerError(null);
    setInviteSent(false);
    try {
      await apiClient.post("/api/users/invitations", values);
      setInviteSent(true);
      reset();
      queryClient.invalidateQueries({ queryKey: ["users"] });
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Users</h1>
        <p className="text-sm text-ink-500">Invite teammates and manage their access to this workspace.</p>
      </div>

      <Card>
        <CardHeader title="Invite a teammate" />
        <FormRoot onSubmit={handleSubmit(onInvite)} className="max-w-md">
          {serverError ? <Alert tone="error">{serverError}</Alert> : null}
          {inviteSent ? <Alert tone="success">Invitation sent.</Alert> : null}
          <TextInput label="Email address" type="email" error={errors.email?.message} {...register("email")} />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="role_name" className="text-sm font-medium text-ink-700">
              Role
            </label>
            <select
              id="role_name"
              className="h-10 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
              {...register("role_name")}
            >
              <option value="">Select a role</option>
              {rolesQuery.data
                ?.filter((r) => !r.is_platform_role)
                .map((role) => (
                  <option key={role.id} value={role.name}>
                    {role.name.replace(/_/g, " ")}
                  </option>
                ))}
            </select>
            {errors.role_name ? <p className="text-xs text-severity-critical">{errors.role_name.message}</p> : null}
          </div>
          <Button type="submit" isLoading={isSubmitting}>
            Send invitation
          </Button>
        </FormRoot>
      </Card>

      <Card>
        <CardHeader title="Members" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-border text-ink-500">
                <th className="py-2 pr-4 font-medium">Name</th>
                <th className="py-2 pr-4 font-medium">Email</th>
                <th className="py-2 pr-4 font-medium">Role</th>
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {membersQuery.data?.map((member) => (
                <tr key={member.id} className="border-b border-surface-border/50">
                  <td className="py-2 pr-4 text-ink-900">{member.full_name}</td>
                  <td className="py-2 pr-4 text-ink-500">{member.email}</td>
                  <td className="py-2 pr-4 text-ink-700">{member.role_name.replace(/_/g, " ")}</td>
                  <td className="py-2">
                    <StatusBadge label={member.status} tone={member.status === "active" ? "positive" : "neutral"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
