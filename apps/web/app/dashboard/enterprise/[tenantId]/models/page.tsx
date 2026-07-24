"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type EnterpriseMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface ModelLicence {
  id: string;
  key: string;
  name: string;
  allows_commercial_use: boolean;
  allows_redistribution: boolean;
}

interface Model {
  id: string;
  model_key: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
}

interface ModelVersion {
  id: string;
  model_id: string;
  version: number;
  status: string;
  visibility: string;
  licence_id: string;
  checksum_sha256: string;
  permitted_geographies: string[];
  prohibited_geographies: string[];
  supported_languages: string[];
  price_per_unit?: number;
  pricing_unit: string;
  currency: string;
  requested_by: string;
  approved_by?: string;
  retirement_reason?: string;
}

interface ModelAccessGrant {
  id: string;
  model_version_id: string;
  grantee_tenant_id: string;
  price_per_unit_override?: number;
  status: string;
  created_at: string;
}

// Roles known (from docs/security/permission-matrix.md plus the new
// Milestone 4 grants) to hold the server-side models.* permission each
// action requires -- a UX convenience only, re-checked independently by
// control-api on every request.
const CAN_REGISTER = new Set(["enterprise_owner", "enterprise_admin", "security_administrator", "ai_platform_engineer"]);
const CAN_APPROVE = new Set(["enterprise_owner", "enterprise_admin", "security_administrator", "compliance_manager"]);
const CAN_RETIRE = new Set(["enterprise_owner", "enterprise_admin", "security_administrator"]);
// models.publish is a Milestone 1 permission never enforced until Milestone
// 13's AI Model Exchange -- granted only to enterprise_owner/enterprise_admin
// in the seeded permission matrix.
const CAN_PUBLISH = new Set(["enterprise_owner", "enterprise_admin"]);

export default function ModelsPage({ params }: { params: Promise<{ tenantId: string }> }) {
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
  const canRetire = CAN_RETIRE.has(myRole);
  const canPublish = CAN_PUBLISH.has(myRole);

  const models = useQuery({
    queryKey: ["models", tenantId],
    queryFn: () => api.get<Model[]>(`/api/v1/enterprises/${tenantId}/models`),
  });
  const licences = useQuery({
    queryKey: ["model-licences", tenantId],
    queryFn: () => api.get<ModelLicence[]>(`/api/v1/enterprises/${tenantId}/model-licences`),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["models", tenantId] });

  if (models.isError && models.error instanceof ApiError && models.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
        <p>You do not have access to this tenant&apos;s model registry.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
      <Link href={`/dashboard/enterprise/${tenantId}`} className="text-sm underline">&larr; Tenant overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Model registry</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Immutable-once-approved model versions with licence, geography, and safety-evaluation
        metadata. Approval is dual control: a different user must approve than whoever requested it.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Models</h2>
        <ul className="flex flex-col gap-3">
          {models.data?.map((m) => (
            <ModelCard
              key={m.id}
              tenantId={tenantId}
              model={m}
              licences={licences.data}
              myUserId={user?.user_id}
              canApprove={canApprove}
              canRetire={canRetire}
              canPublish={canPublish}
            />
          ))}
          {models.data?.length === 0 && <li className="text-sm text-zinc-500">No models registered yet.</li>}
        </ul>
      </section>

      {canRegister && <CreateModelForm tenantId={tenantId} onCreated={invalidate} />}
    </main>
  );
}

function ModelCard({
  tenantId,
  model,
  licences,
  myUserId,
  canApprove,
  canRetire,
  canPublish,
}: {
  tenantId: string;
  model: Model;
  licences: ModelLicence[] | undefined;
  myUserId: string | undefined;
  canApprove: boolean;
  canRetire: boolean;
  canPublish: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const versions = useQuery({
    queryKey: ["model-versions", model.id],
    queryFn: () => api.get<ModelVersion[]>(`/api/v1/enterprises/${tenantId}/models/${model.id}/versions`),
    enabled: expanded,
  });
  const [error, setError] = useState<string | null>(null);
  const [licenceId, setLicenceId] = useState("");
  const [permitted, setPermitted] = useState("");
  const [prohibited, setProhibited] = useState("");

  const invalidateVersions = () => versions.refetch();

  const createDraft = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/models/${model.id}/versions`, {
        licence_id: licenceId,
        checksum_sha256: "0".repeat(64),
        permitted_geographies: permitted.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean),
        prohibited_geographies: prohibited.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean),
      });
      setLicenceId("");
      setPermitted("");
      setProhibited("");
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to draft version.");
    }
  };

  const requestApproval = async (versionId: string) => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/model-versions/${versionId}/request-approval`, {});
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to request approval.");
    }
  };
  const approve = async (versionId: string) => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/model-versions/${versionId}/approve`, {});
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to approve version.");
    }
  };
  const retire = async (versionId: string) => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/model-versions/${versionId}/retire`, { reason: "retired from dashboard" });
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to retire version.");
    }
  };
  const revoke = async (versionId: string) => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/model-versions/${versionId}/revoke`, { reason: "revoked from dashboard" });
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to revoke version.");
    }
  };
  const [pricePerUnit, setPricePerUnit] = useState<Record<string, string>>({});
  const [pricingUnit, setPricingUnit] = useState<Record<string, string>>({});
  const publish = async (versionId: string) => {
    setError(null);
    try {
      const price = pricePerUnit[versionId];
      await api.post(`/api/v1/enterprises/${tenantId}/model-versions/${versionId}/publish`, {
        price_per_unit: price ? Number(price) : null,
        pricing_unit: pricingUnit[versionId] ?? "",
        currency: "USD",
      });
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to publish version. The licence may forbid commercial use.");
    }
  };
  const unpublish = async (versionId: string) => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/model-versions/${versionId}/unpublish`, {});
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to unpublish version.");
    }
  };
  const [grantsOpenFor, setGrantsOpenFor] = useState<string | null>(null);

  return (
    <li className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
      <button onClick={() => setExpanded(!expanded)} className="flex w-full items-center justify-between text-left">
        <span className="font-medium">{model.name} <span className="text-zinc-500">({model.model_key})</span></span>
        <span className="text-xs text-zinc-500">{model.status} {expanded ? "−" : "+"}</span>
      </button>

      {expanded && (
        <div className="mt-3 flex flex-col gap-2">
          {error && <p className="text-sm text-red-600">{error}</p>}
          <ul className="flex flex-col gap-2">
            {versions.data?.map((v) => (
              <li key={v.id} className="rounded border border-zinc-100 p-2 dark:border-zinc-900">
                <div className="flex items-center justify-between flex-wrap gap-1">
                  <span>v{v.version}</span>
                  <span className="text-xs text-zinc-500">
                    {v.status}
                    {v.status === "approved" && (
                      <> &middot; {v.visibility === "public" ? "public listing" : "private (grant-only)"}</>
                    )}
                  </span>
                </div>
                {v.permitted_geographies?.length > 0 && (
                  <p className="text-xs text-zinc-500">Permitted: {v.permitted_geographies.join(", ")}</p>
                )}
                {v.prohibited_geographies?.length > 0 && (
                  <p className="text-xs text-zinc-500">Prohibited: {v.prohibited_geographies.join(", ")}</p>
                )}
                {v.supported_languages?.length > 0 && (
                  <p className="text-xs text-zinc-500">Languages: {v.supported_languages.join(", ")}</p>
                )}
                {v.visibility === "public" && v.price_per_unit != null && (
                  <p className="text-xs text-zinc-500">
                    Listed at {v.currency} {v.price_per_unit}{v.pricing_unit ? ` / ${v.pricing_unit}` : ""}
                  </p>
                )}
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  {v.status === "draft" && (
                    <button onClick={() => requestApproval(v.id)} className="text-xs underline">Request approval</button>
                  )}
                  {v.status === "pending_approval" && canApprove && v.requested_by !== myUserId && (
                    <button onClick={() => approve(v.id)} className="text-xs underline">Approve</button>
                  )}
                  {v.status === "pending_approval" && v.requested_by === myUserId && (
                    <span className="text-xs text-zinc-500">Awaiting a different approver</span>
                  )}
                  {v.status === "approved" && canRetire && (
                    <>
                      <button onClick={() => retire(v.id)} className="text-xs underline">Retire</button>
                      <button onClick={() => revoke(v.id)} className="text-xs text-red-600 underline">Revoke</button>
                    </>
                  )}
                  {v.status === "approved" && canPublish && v.visibility === "private" && (
                    <button onClick={() => publish(v.id)} className="text-xs underline">Publish to exchange</button>
                  )}
                  {v.status === "approved" && canPublish && v.visibility === "public" && (
                    <button onClick={() => unpublish(v.id)} className="text-xs underline">Unpublish</button>
                  )}
                  {v.status === "approved" && canPublish && (
                    <button
                      onClick={() => setGrantsOpenFor(grantsOpenFor === v.id ? null : v.id)}
                      className="text-xs underline"
                    >
                      {grantsOpenFor === v.id ? "Hide access grants" : "Manage access grants"}
                    </button>
                  )}
                </div>
                {v.status === "approved" && canPublish && v.visibility === "private" && (
                  <div className="mt-1 flex flex-wrap gap-2">
                    <input placeholder="Price per unit (optional)" value={pricePerUnit[v.id] ?? ""}
                      onChange={(e) => setPricePerUnit({ ...pricePerUnit, [v.id]: e.target.value })}
                      className="w-40 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Price per unit (optional)" />
                    <input placeholder="Pricing unit (e.g. per_1k_tokens)" value={pricingUnit[v.id] ?? ""}
                      onChange={(e) => setPricingUnit({ ...pricingUnit, [v.id]: e.target.value })}
                      className="w-48 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Pricing unit (e.g. per_1k_tokens)" />
                  </div>
                )}
                {grantsOpenFor === v.id && <VersionGrantsPanel tenantId={tenantId} versionId={v.id} />}
              </li>
            ))}
            {versions.data?.length === 0 && <li className="text-xs text-zinc-500">No versions yet.</li>}
          </ul>

          <div className="mt-2 flex flex-col gap-2 rounded border border-zinc-100 p-2 dark:border-zinc-900">
            <h4 className="text-xs font-medium">Draft a new version</h4>
            <select aria-label="Licence" value={licenceId} onChange={(e) => setLicenceId(e.target.value)}
              className="rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900">
              <option value="">Select a licence</option>
              {licences?.map((l) => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </select>
            <input placeholder="Permitted geographies (comma-separated, e.g. AE,SA)" value={permitted}
              onChange={(e) => setPermitted(e.target.value)}
              className="rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Permitted geographies (comma-separated, e.g. AE,SA)" />
            <input placeholder="Prohibited geographies (comma-separated)" value={prohibited}
              onChange={(e) => setProhibited(e.target.value)}
              className="rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Prohibited geographies (comma-separated)" />
            <button onClick={createDraft} disabled={!licenceId}
              className="self-start rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
              Create draft version
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

// VersionGrantsPanel lets the owning tenant invite a specific other tenant to
// select a private model version (or override a public one's price for that
// tenant) -- the model exchange's equivalent of Milestone 12's
// capacity_offer_grants panel.
function VersionGrantsPanel({ tenantId, versionId }: { tenantId: string; versionId: string }) {
  const grants = useQuery({
    queryKey: ["model-access-grants", versionId],
    queryFn: () => api.get<ModelAccessGrant[]>(`/api/v1/enterprises/${tenantId}/model-versions/${versionId}/access-grants`),
  });
  const [granteeTenantId, setGranteeTenantId] = useState("");
  const [priceOverride, setPriceOverride] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createGrant = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/model-versions/${versionId}/access-grants`, {
        grantee_tenant_id: granteeTenantId,
        price_per_unit_override: priceOverride ? Number(priceOverride) : null,
      });
      setGranteeTenantId("");
      setPriceOverride("");
      grants.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create access grant.");
    }
  };
  const revokeGrant = async (grantId: string) => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/model-access-grants/${grantId}/revoke`, {});
      grants.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to revoke access grant.");
    }
  };

  return (
    <div className="mt-2 flex flex-col gap-2 rounded border border-zinc-100 p-2 dark:border-zinc-900">
      <h4 className="text-xs font-medium">Access grants</h4>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <ul className="flex flex-col gap-1">
        {grants.data?.map((g) => (
          <li key={g.id} className="flex items-center justify-between text-xs flex-wrap gap-1">
            <span>
              Tenant {g.grantee_tenant_id.slice(0, 8)}&hellip;
              {g.price_per_unit_override != null && <> &middot; override {g.price_per_unit_override}</>}
              {" "}&middot; {g.status}
            </span>
            {g.status === "active" && (
              <button onClick={() => revokeGrant(g.id)} className="text-red-600 underline">Revoke</button>
            )}
          </li>
        ))}
        {grants.data?.length === 0 && <li className="text-xs text-zinc-500">No access grants yet.</li>}
      </ul>
      <div className="flex flex-wrap gap-2">
        <input placeholder="Grantee tenant ID" value={granteeTenantId} onChange={(e) => setGranteeTenantId(e.target.value)}
          className="w-56 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Grantee tenant ID" />
        <input placeholder="Price override (optional)" value={priceOverride} onChange={(e) => setPriceOverride(e.target.value)}
          className="w-44 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Price override (optional)" />
        <button onClick={createGrant} disabled={!granteeTenantId}
          className="rounded-md bg-zinc-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Grant access
        </button>
      </div>
    </div>
  );
}

function CreateModelForm({ tenantId, onCreated }: { tenantId: string; onCreated: () => void }) {
  const [modelKey, setModelKey] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/models`, { model_key: modelKey, name, description });
      setModelKey("");
      setName("");
      setDescription("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to register model.");
    }
  };

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Register a new model</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Model key (e.g. text-embed-v1)" value={modelKey} onChange={(e) => setModelKey(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Model key (e.g. text-embed-v1)" />
        <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Name" />
        <input placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Description" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!modelKey || !name}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Register model
        </button>
      </div>
    </section>
  );
}
