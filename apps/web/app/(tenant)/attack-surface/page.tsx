"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, Card, CardHeader, FormRoot, StatusBadge, TextInput } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { DomainRead, VerifyDomainResult } from "@/lib/types";

const schema = z.object({
  domain: z.string().min(3, "Enter a domain.").max(255),
});
type FormValues = z.infer<typeof schema>;

export default function AttackSurfacePage() {
  const { hasPermission } = useAuth();
  const canView = hasPermission("assets.view");
  const canManage = hasPermission("assets.manage");
  const queryClient = useQueryClient();

  const [serverError, setServerError] = useState<string | null>(null);
  const [busyDomainId, setBusyDomainId] = useState<string | null>(null);
  const [verifyMessages, setVerifyMessages] = useState<Record<string, string>>({});
  const [methodByDomain, setMethodByDomain] = useState<Record<string, "http_file" | "dns_txt">>({});

  const domainsQuery = useQuery({
    queryKey: ["attack-surface", "domains"],
    queryFn: () => apiClient.get<DomainRead[]>("/api/attack-surface/domains"),
    enabled: canView,
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  if (!canView) {
    return <p className="text-sm text-ink-500">Not visible to your role.</p>;
  }

  const domains = domainsQuery.data ?? [];

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["attack-surface", "domains"] });

  const onAddDomain = async (values: FormValues) => {
    setServerError(null);
    try {
      await apiClient.post("/api/attack-surface/domains", values);
      reset();
      refresh();
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  const verifyDomain = async (domainId: string) => {
    setServerError(null);
    setBusyDomainId(domainId);
    try {
      const method = methodByDomain[domainId] ?? "http_file";
      const result = await apiClient.post<VerifyDomainResult>(
        `/api/attack-surface/domains/${domainId}/verify`,
        undefined,
        { method },
      );
      setVerifyMessages((prev) => ({ ...prev, [domainId]: result.message }));
      refresh();
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusyDomainId(null);
    }
  };

  const removeDomain = async (domainId: string) => {
    setServerError(null);
    setBusyDomainId(domainId);
    try {
      await apiClient.delete(`/api/attack-surface/domains/${domainId}`);
      refresh();
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusyDomainId(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Attack Surface</h1>
        <p className="text-sm text-ink-500">
          Domains you claim as part of your organisation&apos;s perimeter. Ownership is verified with a
          real check — publish a file at the address shown below and GRIDKEEP fetches it over HTTPS to
          confirm you control the domain.
        </p>
      </div>

      {serverError ? <Alert tone="error">{serverError}</Alert> : null}

      {canManage ? (
        <Card>
          <CardHeader title="Add a domain" />
          <FormRoot onSubmit={handleSubmit(onAddDomain)} className="max-w-md">
            <TextInput
              label="Domain"
              placeholder="example.com"
              error={errors.domain?.message}
              {...register("domain")}
            />
            <Button type="submit" isLoading={isSubmitting}>
              Add domain
            </Button>
          </FormRoot>
        </Card>
      ) : null}

      <Card>
        <CardHeader title={`Domains (${domains.length})`} />
        {domains.length > 0 ? (
          <div className="flex flex-col gap-4">
            {domains.map((domain) => (
              <div key={domain.id} className="rounded border border-surface-border p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium text-ink-900">{domain.domain}</span>
                    <StatusBadge
                      label={domain.is_verified ? "Verified" : "Unverified"}
                      tone={domain.is_verified ? "positive" : "neutral"}
                    />
                  </div>
                  {canManage ? (
                    <div className="flex gap-2">
                      {!domain.is_verified ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          isLoading={busyDomainId === domain.id}
                          onClick={() => verifyDomain(domain.id)}
                        >
                          Verify now
                        </Button>
                      ) : null}
                      <Button
                        size="sm"
                        variant="ghost"
                        isLoading={busyDomainId === domain.id}
                        onClick={() => removeDomain(domain.id)}
                      >
                        Remove
                      </Button>
                    </div>
                  ) : null}
                </div>

                {!domain.is_verified ? (
                  <div className="mt-3 flex flex-col gap-2 text-sm text-ink-500">
                    <div className="flex gap-4">
                      <label className="flex items-center gap-1.5">
                        <input
                          type="radio"
                          name={`method-${domain.id}`}
                          checked={(methodByDomain[domain.id] ?? "http_file") === "http_file"}
                          onChange={() =>
                            setMethodByDomain((prev) => ({ ...prev, [domain.id]: "http_file" }))
                          }
                        />
                        HTTP file
                      </label>
                      <label className="flex items-center gap-1.5">
                        <input
                          type="radio"
                          name={`method-${domain.id}`}
                          checked={(methodByDomain[domain.id] ?? "http_file") === "dns_txt"}
                          onChange={() =>
                            setMethodByDomain((prev) => ({ ...prev, [domain.id]: "dns_txt" }))
                          }
                        />
                        DNS TXT record
                      </label>
                    </div>
                    {(methodByDomain[domain.id] ?? "http_file") === "http_file" ? (
                      <p>
                        Publish a file at{" "}
                        <code className="rounded bg-surface-800 px-1.5 py-0.5 text-ink-700">
                          {domain.verification_file_url}
                        </code>{" "}
                        containing:
                      </p>
                    ) : (
                      <p>
                        Add a DNS TXT record at{" "}
                        <code className="rounded bg-surface-800 px-1.5 py-0.5 text-ink-700">
                          {domain.dns_txt_record_name}
                        </code>{" "}
                        containing:
                      </p>
                    )}
                    <code className="w-fit rounded bg-surface-800 px-1.5 py-0.5 text-ink-700">
                      {domain.verification_token}
                    </code>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-ink-500">
                    Verified {domain.verified_at ? new Date(domain.verified_at).toLocaleString() : ""} via{" "}
                    {domain.verification_method}.
                  </p>
                )}

                {verifyMessages[domain.id] ? (
                  <p className="mt-2 text-sm text-ink-500">{verifyMessages[domain.id]}</p>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-500">No domains added yet.</p>
        )}
      </Card>
    </div>
  );
}
