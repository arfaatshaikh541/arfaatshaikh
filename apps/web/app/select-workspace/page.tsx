"use client";

import { Button, Card, CardHeader } from "@gridkeep/ui";
import { useRouter } from "next/navigation";

import { apiClient } from "@/lib/api-client";
import { useAuth, useInvalidateAuth } from "@/lib/auth-context";

export default function SelectWorkspacePage() {
  const { me, isLoading } = useAuth();
  const invalidateAuth = useInvalidateAuth();
  const router = useRouter();

  if (isLoading) return null;
  if (!me) {
    router.replace("/login");
    return null;
  }

  const selectWorkspace = async (membershipId: string) => {
    await apiClient.post("/api/auth/tenant-switch", { membership_id: membershipId });
    invalidateAuth();
    router.replace("/dashboard");
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-4">
      <h1 className="text-lg font-semibold text-ink-900">Select a workspace</h1>
      <div className="flex w-full max-w-sm flex-col gap-3">
        {me.memberships.map((membership) => (
          <Card key={membership.membership_id} className="flex items-center justify-between">
            <CardHeader title={membership.tenant_name} description={`Role: ${membership.role_name.replace(/_/g, " ")}`} />
            <Button size="sm" onClick={() => selectWorkspace(membership.membership_id)}>
              Enter
            </Button>
          </Card>
        ))}
      </div>
    </main>
  );
}
