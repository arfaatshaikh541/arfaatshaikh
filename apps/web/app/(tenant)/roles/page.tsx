"use client";

import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";

interface Role {
  id: string;
  name: string;
  is_system: boolean;
  permission_codes: string[];
}

const createRoleSchema = z.object({ name: z.string().min(1, "Role name is required.") });
type CreateRoleForm = z.infer<typeof createRoleSchema>;

export default function RolesPage() {
  const queryClient = useQueryClient();
  const rolesQuery = useQuery({ queryKey: ["tenant", "roles"], queryFn: () => api.get<Role[]>("/tenant/roles") });
  const catalogQuery = useQuery({
    queryKey: ["tenant", "permission-catalog"],
    queryFn: () => api.get<Record<string, string>>("/tenant/roles/permission-catalog"),
  });
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateRoleForm>({ resolver: zodResolver(createRoleSchema) });

  const createMutation = useMutation({
    mutationFn: (values: CreateRoleForm) =>
      api.post("/tenant/roles", { name: values.name, permission_codes: selectedPermissions }),
    onSuccess: () => {
      reset();
      setSelectedPermissions([]);
      queryClient.invalidateQueries({ queryKey: ["tenant", "roles"] });
    },
  });

  const togglePermission = (code: string) => {
    setSelectedPermissions((prev) => (prev.includes(code) ? prev.filter((p) => p !== code) : [...prev, code]));
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Roles</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Default roles are managed by the platform and cannot be edited. Create custom roles for this workspace
          below.
        </p>
      </div>

      <Card>
        <CardHeader title="Existing roles" />
        <div className="space-y-3">
          {rolesQuery.data?.map((role) => (
            <div key={role.id} className="rounded-md border border-surface-border p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-ink">{role.name}</span>
                {role.is_system && (
                  <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-ink-faint">System</span>
                )}
              </div>
              <p className="mt-1 text-xs text-ink-muted">{role.permission_codes.length} permissions</p>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Create a custom role" />
        <form className="space-y-4" onSubmit={handleSubmit((values) => createMutation.mutate(values))} noValidate>
          {createMutation.isError && (
            <Alert tone="error">
              {createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to create role."}
            </Alert>
          )}
          <div>
            <Label htmlFor="name">Role name</Label>
            <Input id="name" {...register("name")} />
            <FieldError>{errors.name?.message}</FieldError>
          </div>
          <div>
            <Label>Permissions</Label>
            <div className="grid max-h-64 grid-cols-1 gap-1.5 overflow-y-auto rounded-md border border-surface-border p-3 sm:grid-cols-2">
              {catalogQuery.data &&
                Object.entries(catalogQuery.data).map(([code, description]) => (
                  <label key={code} className="flex items-start gap-2 text-sm text-ink-muted">
                    <input
                      type="checkbox"
                      className="mt-0.5"
                      checked={selectedPermissions.includes(code)}
                      onChange={() => togglePermission(code)}
                    />
                    <span>
                      <span className="text-ink">{code}</span> — {description}
                    </span>
                  </label>
                ))}
            </div>
          </div>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Creating…" : "Create role"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
