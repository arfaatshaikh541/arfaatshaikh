"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";

interface Member {
  membership_id: string;
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role_name: string;
  status: string;
}

interface Role {
  id: string;
  name: string;
  is_system: boolean;
  permission_codes: string[];
}

const inviteSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  role_id: z.string().min(1, "Select a role."),
});
type InviteForm = z.infer<typeof inviteSchema>;

export default function UsersPage() {
  const queryClient = useQueryClient();
  const membersQuery = useQuery({ queryKey: ["tenant", "users"], queryFn: () => api.get<Member[]>("/tenant/users") });
  const rolesQuery = useQuery({ queryKey: ["tenant", "roles"], queryFn: () => api.get<Role[]>("/tenant/roles") });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<InviteForm>({ resolver: zodResolver(inviteSchema) });

  const inviteMutation = useMutation({
    mutationFn: (values: InviteForm) => api.post("/tenant/users/invitations", values),
    onSuccess: () => {
      reset();
      queryClient.invalidateQueries({ queryKey: ["tenant", "users"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Users</h1>
        <p className="mt-1 text-sm text-ink-muted">Manage who has access to this workspace.</p>
      </div>

      <Card>
        <CardHeader title="Invite a user" />
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={handleSubmit((values) => inviteMutation.mutate(values))}
          noValidate
        >
          <div className="min-w-[220px] flex-1">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" {...register("email")} />
            <FieldError>{errors.email?.message}</FieldError>
          </div>
          <div className="min-w-[180px]">
            <Label htmlFor="role_id">Role</Label>
            <select
              id="role_id"
              className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
              {...register("role_id")}
            >
              <option value="">Select a role</option>
              {rolesQuery.data?.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.name}
                </option>
              ))}
            </select>
            <FieldError>{errors.role_id?.message}</FieldError>
          </div>
          <Button type="submit" disabled={inviteMutation.isPending}>
            {inviteMutation.isPending ? "Sending…" : "Send invitation"}
          </Button>
        </form>
        {inviteMutation.isSuccess && (
          <div className="mt-3">
            <Alert tone="success">Invitation sent.</Alert>
          </div>
        )}
        {inviteMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">
              {inviteMutation.error instanceof ApiError ? inviteMutation.error.message : "Unable to send invitation."}
            </Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Team members" />
        {membersQuery.isLoading && <p className="text-sm text-ink-muted">Loading…</p>}
        {membersQuery.data && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-border text-ink-faint">
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Email</th>
                <th className="pb-2 font-medium">Role</th>
                <th className="pb-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {membersQuery.data.map((member) => (
                <tr key={member.membership_id} className="border-b border-surface-border/60 text-ink">
                  <td className="py-2">
                    {member.first_name} {member.last_name}
                  </td>
                  <td className="py-2 text-ink-muted">{member.email}</td>
                  <td className="py-2">{member.role_name}</td>
                  <td className="py-2 capitalize text-ink-muted">{member.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
