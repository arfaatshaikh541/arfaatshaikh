"use client";

import { Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { apiClient, ApiError } from "@/lib/api-client";
import type { PublicTrustPassportRead } from "@/lib/types";

const STATUS_TONE: Record<string, "positive" | "warning" | "neutral"> = {
  Strong: "positive",
  "In Progress": "warning",
  Building: "neutral",
};

export default function PublicTrustPassportPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;

  const passportQuery = useQuery({
    queryKey: ["public-trust-passport", slug],
    queryFn: () => apiClient.get<PublicTrustPassportRead>(`/api/public/trust-passport/${slug}`),
    enabled: Boolean(slug),
    retry: false,
  });

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-6 py-16">
      <div className="flex items-center gap-2 text-sm font-semibold text-ink-900">
        <span className="h-2.5 w-2.5 rounded-full bg-accent" aria-hidden="true" />
        GRIDKEEP Trust Passport
      </div>

      {passportQuery.isLoading ? <p className="text-sm text-ink-500">Loading…</p> : null}

      {passportQuery.isError ? (
        <Card>
          <CardHeader title="Not found" />
          <p className="text-sm text-ink-500">
            {passportQuery.error instanceof ApiError
              ? passportQuery.error.message
              : "This trust passport doesn't exist or is no longer published."}
          </p>
        </Card>
      ) : null}

      {passportQuery.data ? (
        <>
          <Card>
            <h1 className="text-2xl font-semibold text-ink-900">{passportQuery.data.headline}</h1>
            {passportQuery.data.description ? (
              <p className="mt-2 text-sm text-ink-500">{passportQuery.data.description}</p>
            ) : null}
          </Card>

          {passportQuery.data.compliance_frameworks ? (
            <Card>
              <CardHeader title="Compliance" />
              <div className="flex flex-col gap-2">
                {passportQuery.data.compliance_frameworks.map((framework) => (
                  <div
                    key={framework.name}
                    className="flex items-center justify-between border-b border-surface-border/50 pb-2"
                  >
                    <span className="text-sm text-ink-900">{framework.name}</span>
                    <StatusBadge
                      label={framework.status_label}
                      tone={STATUS_TONE[framework.status_label] ?? "neutral"}
                    />
                  </div>
                ))}
              </div>
            </Card>
          ) : null}

          <p className="text-xs text-ink-500">
            Generated {new Date(passportQuery.data.generated_at).toLocaleString()} · Powered by GRIDKEEP
            Cyber OS
          </p>
        </>
      ) : null}
    </main>
  );
}
