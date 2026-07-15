"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, getCsrfToken } from "@/lib/api-client";
import { useInvalidatePortalAuth, usePortalAuth } from "@/lib/portal-auth-context";
import type {
  PortalAppointment,
  PortalDeadline,
  PortalDocumentRequest,
  PortalOnboardingCase,
  PortalProposal,
} from "@/lib/types";

function ProposalCard({ proposal }: { proposal: PortalProposal }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [showReject, setShowReject] = useState(false);
  const [reason, setReason] = useState("");

  const acceptMutation = useMutation({
    mutationFn: () => api.post(`/portal/proposals/${proposal.id}/accept`, { accepted_by_name: name }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal", "proposals"] }),
  });
  const rejectMutation = useMutation({
    mutationFn: () => api.post(`/portal/proposals/${proposal.id}/reject`, { rejection_reason: reason }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portal", "proposals"] }),
  });

  return (
    <div className="rounded-md border border-surface-border p-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium text-ink">{proposal.title}</span>
        <span className="text-xs capitalize text-ink-faint">{proposal.status}</span>
      </div>
      <p className="mt-1 text-ink-muted">{proposal.currency} {proposal.total.toFixed(2)}</p>
      {(proposal.status === "sent" || proposal.status === "viewed") && (
        <div className="mt-3 space-y-2">
          {!showReject ? (
            <>
              <Input placeholder="Your full name" value={name} onChange={(e) => setName(e.target.value)} />
              <div className="flex gap-2">
                <Button onClick={() => acceptMutation.mutate()} disabled={!name.trim() || acceptMutation.isPending}>
                  Accept
                </Button>
                <Button variant="secondary" onClick={() => setShowReject(true)}>
                  Decline
                </Button>
              </div>
            </>
          ) : (
            <>
              <Input placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => rejectMutation.mutate()} disabled={rejectMutation.isPending}>
                  Confirm decline
                </Button>
                <Button variant="secondary" onClick={() => setShowReject(false)}>
                  Back
                </Button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function DocumentRequestCard({ request }: { request: PortalDocumentRequest }) {
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const csrfToken = getCsrfToken();
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api"}/portal/documents/${request.id}/upload`, {
        method: "POST",
        credentials: "include",
        headers: csrfToken ? { "X-CSRF-Token": csrfToken } : undefined,
        body: formData,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message ?? "Upload failed.");
      }
      queryClient.invalidateQueries({ queryKey: ["portal", "documents"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  return (
    <div className="rounded-md border border-surface-border p-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium text-ink">{request.title}</span>
        <span className="text-xs capitalize text-ink-faint">{request.status}</span>
      </div>
      {request.description && <p className="mt-1 text-ink-muted">{request.description}</p>}
      {(request.status === "requested" || request.status === "rejected") && (
        <div className="mt-3 space-y-2">
          {error && <Alert tone="error">{error}</Alert>}
          <input type="file" onChange={handleUpload} disabled={uploading} className="text-sm text-ink-muted" />
        </div>
      )}
    </div>
  );
}

export default function PortalDashboardPage({ params }: { params: Promise<{ tenantSlug: string }> }) {
  const { tenantSlug } = use(params);
  const router = useRouter();
  const { account, isLoading, isError } = usePortalAuth();
  const invalidatePortalAuth = useInvalidatePortalAuth();

  useEffect(() => {
    if (!isLoading && (isError || !account)) {
      router.replace(`/portal/${tenantSlug}/login`);
    }
  }, [isLoading, isError, account, tenantSlug, router]);

  const proposalsQuery = useQuery({ queryKey: ["portal", "proposals"], queryFn: () => api.get<PortalProposal[]>("/portal/proposals"), enabled: !!account });
  const documentsQuery = useQuery({ queryKey: ["portal", "documents"], queryFn: () => api.get<PortalDocumentRequest[]>("/portal/documents"), enabled: !!account });
  const onboardingQuery = useQuery({ queryKey: ["portal", "onboarding-cases"], queryFn: () => api.get<PortalOnboardingCase[]>("/portal/onboarding-cases"), enabled: !!account });
  const deadlinesQuery = useQuery({ queryKey: ["portal", "deadlines"], queryFn: () => api.get<PortalDeadline[]>("/portal/deadlines"), enabled: !!account });
  const appointmentsQuery = useQuery({ queryKey: ["portal", "appointments"], queryFn: () => api.get<PortalAppointment[]>("/portal/appointments"), enabled: !!account });

  const logoutMutation = useMutation({
    mutationFn: () => api.post("/portal/auth/logout"),
    onSuccess: async () => {
      await invalidatePortalAuth();
      router.replace(`/portal/${tenantSlug}/login`);
    },
  });

  if (isLoading || !account) {
    return <div className="flex min-h-screen items-center justify-center text-ink-muted">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Welcome, {account.first_name}</h1>
          <p className="mt-1 text-sm text-ink-muted">{account.tenant_name} client portal</p>
        </div>
        <Button variant="secondary" onClick={() => logoutMutation.mutate()} disabled={logoutMutation.isPending}>
          Sign out
        </Button>
      </div>

      <div className="mt-6 space-y-6">
        <Card>
          <CardHeader title="Proposals" />
          <div className="space-y-2">
            {proposalsQuery.data?.map((p) => <ProposalCard key={p.id} proposal={p} />)}
            {proposalsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No proposals yet.</p>}
          </div>
        </Card>

        <Card>
          <CardHeader title="Document requests" />
          <div className="space-y-2">
            {documentsQuery.data?.map((r) => <DocumentRequestCard key={r.id} request={r} />)}
            {documentsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No document requests yet.</p>}
          </div>
        </Card>

        <Card>
          <CardHeader title="Onboarding" />
          <div className="space-y-3">
            {onboardingQuery.data?.map((c) => (
              <div key={c.id} className="rounded-md border border-surface-border p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-ink">{c.name}</span>
                  <span className="text-xs capitalize text-ink-faint">{c.status.replace("_", " ")}</span>
                </div>
                <ul className="mt-2 space-y-1">
                  {c.steps.map((step, index) => (
                    <li key={index} className="flex justify-between text-xs">
                      <span className={step.status === "completed" ? "text-ink-faint line-through" : "text-ink-muted"}>{step.title}</span>
                      <span className="capitalize text-ink-faint">{step.status}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {onboardingQuery.data?.length === 0 && <p className="text-sm text-ink-muted">Nothing in progress yet.</p>}
          </div>
        </Card>

        <Card>
          <CardHeader title="Deadlines" />
          <div className="space-y-2">
            {deadlinesQuery.data?.map((d) => (
              <div key={d.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
                <span className={d.status === "completed" ? "text-ink-faint line-through" : "text-ink"}>{d.title}</span>
                <span className="text-xs text-ink-faint">Due {d.due_date}</span>
              </div>
            ))}
            {deadlinesQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No upcoming deadlines.</p>}
          </div>
        </Card>

        <Card>
          <CardHeader title="Appointments" />
          <div className="space-y-2">
            {appointmentsQuery.data?.map((a) => (
              <div key={a.id} className="rounded-md border border-surface-border p-3 text-sm">
                <p className="text-ink">{new Date(a.starts_at).toLocaleString([], { timeZone: "UTC" })}</p>
                <p className="text-xs capitalize text-ink-faint">{a.title} — {a.status}</p>
              </div>
            ))}
            {appointmentsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No appointments scheduled.</p>}
          </div>
        </Card>
      </div>
    </div>
  );
}
