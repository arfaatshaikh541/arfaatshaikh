"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type EnterpriseMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface ContainerImage {
  id: string;
  registry_host: string;
  repository: string;
  digest: string;
  tag: string;
  status: string;
  created_at: string;
}

interface VulnerabilityPolicy {
  max_allowed_severity: string;
  block_unsigned_images: boolean;
  require_sbom: boolean;
}

interface VulnerabilityException {
  id: string;
  finding_id?: string;
  reason: string;
  status: string;
  expires_at: string;
  requested_by: string;
}

const CAN_REGISTER = new Set(["enterprise_owner", "enterprise_admin", "security_administrator", "ai_platform_engineer"]);
const CAN_APPROVE = new Set(["enterprise_owner", "enterprise_admin", "security_administrator"]);
const CAN_EXCEPTION_APPROVE = new Set(["enterprise_owner", "enterprise_admin", "security_administrator", "compliance_manager"]);

export default function ImagesPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["tenant-members", tenantId],
    queryFn: () => api.get<EnterpriseMembership[]>(`/api/v1/enterprises/${tenantId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const canRegister = CAN_REGISTER.has(myRole);
  const canApprove = CAN_APPROVE.has(myRole);
  const canExceptionApprove = CAN_EXCEPTION_APPROVE.has(myRole);

  const images = useQuery({
    queryKey: ["images", tenantId],
    queryFn: () => api.get<ContainerImage[]>(`/api/v1/enterprises/${tenantId}/images`),
  });
  const policy = useQuery({
    queryKey: ["vulnerability-policy", tenantId],
    queryFn: () => api.get<VulnerabilityPolicy>(`/api/v1/enterprises/${tenantId}/vulnerability-policy`),
  });

  const invalidateImages = () => queryClient.invalidateQueries({ queryKey: ["images", tenantId] });

  if (images.isError && images.error instanceof ApiError && images.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not have access to this tenant&apos;s container image registry.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-8">
      <Link href={`/dashboard/enterprise/${tenantId}`} className="text-sm underline">&larr; Tenant overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Container images &amp; supply chain</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Images are registered by content digest -- never a mutable tag -- against a platform-approved
        registry allowlist, and approval is gated by SBOM presence, signature status, and vulnerability
        scan findings, overridable only through a dual-control exception with an expiry.
      </p>

      {policy.data && (
        <section className="mb-8 rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
          <h2 className="mb-2 text-sm font-medium">Vulnerability policy</h2>
          <p className="text-xs text-zinc-500">
            Max allowed severity: <strong>{policy.data.max_allowed_severity}</strong> &middot; Block
            unsigned images: <strong>{policy.data.block_unsigned_images ? "yes" : "no"}</strong> &middot;
            Require SBOM: <strong>{policy.data.require_sbom ? "yes" : "no"}</strong>
          </p>
        </section>
      )}

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Images</h2>
        <ul className="flex flex-col gap-3">
          {images.data?.map((img) => (
            <ImageCard
              key={img.id}
              tenantId={tenantId}
              image={img}
              canApprove={canApprove}
              canExceptionApprove={canExceptionApprove}
              myUserId={user?.user_id}
              onChanged={invalidateImages}
            />
          ))}
          {images.data?.length === 0 && <li className="text-sm text-zinc-500">No images registered yet.</li>}
        </ul>
      </section>

      {canRegister && <RegisterImageForm tenantId={tenantId} onCreated={invalidateImages} />}
    </main>
  );
}

function ImageCard({
  tenantId,
  image,
  canApprove,
  canExceptionApprove,
  myUserId,
  onChanged,
}: {
  tenantId: string;
  image: ContainerImage;
  canApprove: boolean;
  canExceptionApprove: boolean;
  myUserId: string | undefined;
  onChanged: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scans = useQuery({
    queryKey: ["vulnerability-scans", image.id],
    queryFn: () => api.get<{ id: string; scanner: string }[]>(`/api/v1/enterprises/${tenantId}/images/${image.id}/vulnerability-scans`),
    enabled: expanded,
  });
  const exceptions = useQuery({
    queryKey: ["vulnerability-exceptions", image.id],
    queryFn: () => api.get<VulnerabilityException[]>(`/api/v1/enterprises/${tenantId}/images/${image.id}/vulnerability-exceptions`),
    enabled: expanded,
  });

  const approve = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/images/${image.id}/approve`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Approval blocked by vulnerability policy.");
    }
  };
  const revoke = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/images/${image.id}/revoke`, { reason: "revoked from dashboard" });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to revoke image.");
    }
  };
  const approveException = async (id: string) => {
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/vulnerability-exceptions/${id}/approve`, {});
      exceptions.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to approve exception.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
      <button onClick={() => setExpanded(!expanded)} className="flex w-full items-center justify-between text-left">
        <span className="font-mono text-xs">{image.registry_host}/{image.repository}@{image.digest.slice(0, 19)}&hellip;</span>
        <span className="text-xs text-zinc-500">{image.status} {expanded ? "−" : "+"}</span>
      </button>

      {expanded && (
        <div className="mt-3 flex flex-col gap-2">
          {error && <p className="text-sm text-red-600">{error}</p>}
          {image.status === "pending" || image.status === "blocked" ? (
            canApprove && (
              <button onClick={approve} className="self-start rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-white dark:text-zinc-900">
                {image.status === "blocked" ? "Re-evaluate and approve" : "Approve"}
              </button>
            )
          ) : image.status === "approved" && canApprove ? (
            <button onClick={revoke} className="self-start rounded-md border border-red-300 px-3 py-1.5 text-xs font-medium text-red-600">
              Revoke
            </button>
          ) : null}

          <div>
            <h4 className="text-xs font-medium">Vulnerability scans</h4>
            <ul className="text-xs text-zinc-500">
              {scans.data?.map((s) => <li key={s.id}>{s.scanner}</li>)}
              {scans.data?.length === 0 && <li>No scans ingested yet.</li>}
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-medium">Vulnerability exceptions</h4>
            <ul className="flex flex-col gap-1 text-xs text-zinc-500">
              {exceptions.data?.map((e) => (
                <li key={e.id} className="flex items-center justify-between">
                  <span>{e.reason} ({e.status})</span>
                  {e.status === "pending" && canExceptionApprove && e.requested_by !== myUserId && (
                    <button onClick={() => approveException(e.id)} className="underline">Approve</button>
                  )}
                </li>
              ))}
              {exceptions.data?.length === 0 && <li>No exceptions requested.</li>}
            </ul>
          </div>
        </div>
      )}
    </li>
  );
}

function RegisterImageForm({ tenantId, onCreated }: { tenantId: string; onCreated: () => void }) {
  const [registryHost, setRegistryHost] = useState("");
  const [repository, setRepository] = useState("");
  const [digest, setDigest] = useState("");
  const [tag, setTag] = useState("");
  const [error, setError] = useState<string | null>(null);

  const register = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/images`, { registry_host: registryHost, repository, digest, tag });
      setRegistryHost("");
      setRepository("");
      setDigest("");
      setTag("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to register image.");
    }
  };

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Register an image</h3>
      <p className="mb-2 text-xs text-zinc-500">
        The registry host must already be on the platform-approved allowlist. Digest must be a full
        <code className="mx-1 rounded bg-zinc-100 px-1 dark:bg-zinc-800">sha256:...</code> value -- never a bare tag.
      </p>
      <div className="flex flex-col gap-2">
        <input placeholder="Registry host (e.g. registry.example.com)" value={registryHost} onChange={(e) => setRegistryHost(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Registry host (e.g. registry.example.com)" />
        <input placeholder="Repository (e.g. acme/inference-api)" value={repository} onChange={(e) => setRepository(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Repository (e.g. acme/inference-api)" />
        <input placeholder="Digest (sha256:...)" value={digest} onChange={(e) => setDigest(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Digest (sha256:...)" />
        <input placeholder="Tag (informational only)" value={tag} onChange={(e) => setTag(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Tag (informational only)" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={register} disabled={!registryHost || !repository || !digest}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Register image
        </button>
      </div>
    </section>
  );
}
