"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, type EnterpriseMembership, type OperatorMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useEffect } from "react";

export default function DashboardPage() {
  const { user, loading, refresh } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  const enterpriseMemberships = useQuery({
    queryKey: ["my-enterprise-memberships"],
    queryFn: () => api.get<EnterpriseMembership[]>("/api/v1/me/enterprise-memberships"),
    enabled: !!user,
  });

  const operatorMemberships = useQuery({
    queryKey: ["my-operator-memberships"],
    queryFn: () => api.get<OperatorMembership[]>("/api/v1/me/operator-memberships"),
    enabled: !!user,
  });

  const logout = async () => {
    await api.post("/api/v1/auth/logout");
    await refresh();
    router.push("/login");
  };

  if (loading || !user) return null;

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
      <div className="mb-8 flex items-center justify-between flex-wrap gap-1">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <button onClick={logout} className="text-sm underline">
          Log out
        </button>
      </div>

      <section className="mb-10">
        <div className="mb-3 flex items-center justify-between flex-wrap gap-1">
          <h2 className="text-lg font-medium">Enterprise tenants</h2>
          <Link href="/onboarding" className="text-sm underline">
            + New tenant
          </Link>
        </div>
        {enterpriseMemberships.data?.length ? (
          <ul className="flex flex-col gap-2">
            {enterpriseMemberships.data.map((m) => (
              <li key={m.id}>
                <Link
                  href={`/dashboard/enterprise/${m.enterprise_tenant_id}`}
                  className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 hover:bg-zinc-100 dark:border-zinc-800 dark:hover:bg-zinc-900"
                >
                  <span>{m.enterprise_tenant_id}</span>
                  <span className="text-sm text-zinc-500">{m.role_name}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zinc-500">
            You are not a member of any enterprise tenant yet.
          </p>
        )}
      </section>

      <section className="mb-10">
        <div className="mb-3 flex items-center justify-between flex-wrap gap-1">
          <h2 className="text-lg font-medium">Operator accounts</h2>
          <Link href="/onboarding/operator" className="text-sm underline">
            + New operator
          </Link>
        </div>
        {operatorMemberships.data?.length ? (
          <ul className="flex flex-col gap-2">
            {operatorMemberships.data.map((m) => (
              <li key={m.id}>
                <Link
                  href={`/dashboard/operator/${m.operator_id}`}
                  className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 hover:bg-zinc-100 dark:border-zinc-800 dark:hover:bg-zinc-900"
                >
                  <span>{m.operator_id}</span>
                  <span className="text-sm text-zinc-500">{m.role_name}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-zinc-500">You are not a member of any operator account yet.</p>
        )}
      </section>

      {(user.platform_roles?.length ?? 0) > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-medium">Platform administration</h2>
          <Link
            href="/dashboard/platform"
            className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-3 hover:bg-zinc-100 dark:border-zinc-800 dark:hover:bg-zinc-900"
          >
            <span>Platform portal</span>
            <span className="text-sm text-zinc-500">{user.platform_roles.join(", ")}</span>
          </Link>
        </section>
      )}
    </main>
  );
}
