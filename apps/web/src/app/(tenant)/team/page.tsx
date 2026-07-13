"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { inviteMemberSchema, type InviteMemberInput, type RoleSummary } from "@leadflow/shared-types";
import { Alert, Badge, Button, Card, FormError, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError, apiFetch } from "@/lib/api-client";
import { useCurrentTenant } from "@/hooks/useCurrentTenant";

interface MemberOut {
  id: string;
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: RoleSummary;
  status: string;
}

interface InvitationOut {
  id: string;
  email: string;
  role_id: string;
  status: string;
  expires_at: string;
}

export default function TeamPage() {
  const { tenantId, membership } = useCurrentTenant();
  const queryClient = useQueryClient();
  const canManageUsers = membership?.role.permissions.some((p) => p.code === "users.manage") ?? false;
  const [serverError, setServerError] = useState<string | null>(null);

  const membersQuery = useQuery({
    queryKey: ["members", tenantId],
    queryFn: () => apiFetch<MemberOut[]>("/tenants/me/members"),
    enabled: Boolean(tenantId) && canManageUsers,
  });
  const invitationsQuery = useQuery({
    queryKey: ["invitations", tenantId],
    queryFn: () => apiFetch<InvitationOut[]>("/tenants/me/invitations"),
    enabled: Boolean(tenantId) && canManageUsers,
  });
  const rolesQuery = useQuery({
    queryKey: ["roles", tenantId],
    queryFn: () => apiFetch<{ id: string; name: string; slug: string }[]>("/tenants/me/roles"),
    enabled: Boolean(tenantId) && canManageUsers,
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<InviteMemberInput>({ resolver: zodResolver(inviteMemberSchema) });

  const inviteMutation = useMutation({
    mutationFn: (values: InviteMemberInput) =>
      apiFetch("/tenants/me/invitations", {
        method: "POST",
        body: { email: values.email, role_id: values.roleId },
      }),
    onSuccess: () => {
      reset({ email: "", roleId: "" });
      queryClient.invalidateQueries({ queryKey: ["invitations", tenantId] });
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const revokeMutation = useMutation({
    mutationFn: (invitationId: string) =>
      apiFetch(`/tenants/me/invitations/${invitationId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["invitations", tenantId] }),
  });

  const suspendMutation = useMutation({
    mutationFn: (membershipId: string) =>
      apiFetch(`/tenants/me/members/${membershipId}/suspend`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members", tenantId] }),
  });

  const reactivateMutation = useMutation({
    mutationFn: (membershipId: string) =>
      apiFetch(`/tenants/me/members/${membershipId}/reactivate`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members", tenantId] }),
  });

  if (!canManageUsers) {
    return (
      <Alert tone="info">
        You don&apos;t have permission to manage team members. Ask an Owner or Administrator.
      </Alert>
    );
  }

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Team</h1>
      <p className="mb-6 text-sm text-surface-400">Members, roles and pending invitations.</p>

      <Card className="mb-6">
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Invite a team member</h2>
        {serverError ? (
          <Alert tone="error" className="mb-4">
            {serverError}
          </Alert>
        ) : null}
        <form
          onSubmit={handleSubmit((values) => {
            setServerError(null);
            inviteMutation.mutate(values);
          })}
          className="flex flex-wrap items-end gap-3"
          noValidate
        >
          <div>
            <Label htmlFor="invite-email">Email</Label>
            <Input id="invite-email" type="email" className="w-64" {...register("email")} />
            <FormError message={errors.email?.message} />
          </div>
          <div>
            <Label htmlFor="invite-role">Role</Label>
            <select
              id="invite-role"
              className="rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
              {...register("roleId")}
            >
              <option value="">Select a role…</option>
              {rolesQuery.data?.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.name}
                </option>
              ))}
            </select>
            <FormError message={errors.roleId?.message} />
          </div>
          <Button type="submit" loading={isSubmitting || inviteMutation.isPending}>
            Send invitation
          </Button>
        </form>
      </Card>

      <Card className="mb-6">
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Members</h2>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-800 text-surface-500">
              <th className="pb-2 font-medium">Name</th>
              <th className="pb-2 font-medium">Email</th>
              <th className="pb-2 font-medium">Role</th>
              <th className="pb-2 font-medium">Status</th>
              <th className="pb-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {membersQuery.data?.map((member) => (
              <tr key={member.id} className="border-b border-surface-900">
                <td className="py-2 text-surface-200">
                  {member.first_name} {member.last_name}
                </td>
                <td className="py-2 text-surface-400">{member.email}</td>
                <td className="py-2 text-surface-400">{member.role.name}</td>
                <td className="py-2">
                  <Badge tone={member.status === "active" ? "success" : "warning"}>
                    {member.status}
                  </Badge>
                </td>
                <td className="py-2">
                  {member.status === "active" ? (
                    <Button variant="ghost" onClick={() => suspendMutation.mutate(member.id)}>
                      Suspend
                    </Button>
                  ) : (
                    <Button variant="ghost" onClick={() => reactivateMutation.mutate(member.id)}>
                      Reactivate
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card>
        <h2 className="mb-4 text-sm font-semibold text-surface-100">Pending invitations</h2>
        {invitationsQuery.data?.filter((i) => i.status === "pending").length === 0 ? (
          <p className="text-sm text-surface-500">No pending invitations.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-800 text-surface-500">
                <th className="pb-2 font-medium">Email</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Expires</th>
                <th className="pb-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {invitationsQuery.data
                ?.filter((i) => i.status === "pending")
                .map((invitation) => (
                  <tr key={invitation.id} className="border-b border-surface-900">
                    <td className="py-2 text-surface-200">{invitation.email}</td>
                    <td className="py-2">
                      <Badge tone="accent">{invitation.status}</Badge>
                    </td>
                    <td className="py-2 text-surface-400">
                      {new Date(invitation.expires_at).toLocaleDateString()}
                    </td>
                    <td className="py-2">
                      <Button variant="ghost" onClick={() => revokeMutation.mutate(invitation.id)}>
                        Revoke
                      </Button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
