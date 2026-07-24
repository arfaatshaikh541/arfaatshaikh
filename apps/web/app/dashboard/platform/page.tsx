"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface TenantSummary {
  id: string;
  legal_name: string;
  display_name: string;
  country: string;
  status: string;
  created_at: string;
}

interface OperatorSummary {
  id: string;
  legal_name: string;
  display_name: string;
  country: string;
  status: string;
  trust_level: string;
  created_at: string;
}

interface SupportAccessGrant {
  id: string;
  user_id: string;
  scope_type: string;
  scope_id: string;
  reason: string;
  requested_by: string;
  approved_by?: string;
  approved_at?: string;
  revoked_at?: string;
  expires_at: string;
  created_at: string;
}

interface AuditEvent {
  seq: number;
  occurred_at: string;
  action: string;
  actor_user_id?: string;
}

interface Jurisdiction {
  id: string;
  country_code: string;
  name: string;
}

interface Region {
  id: string;
  key: string;
  name: string;
  jurisdiction_id: string;
  status: string;
}

interface ModelProvider {
  id: string;
  key: string;
  name: string;
  website: string;
  status: string;
}

const ENTERPRISE_PLANS = ["enterprise_starter", "enterprise_growth", "enterprise_sovereign"];
const OPERATOR_PLANS = ["operator_standard", "operator_premium"];

export default function PlatformPortalPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const tenants = useQuery({
    queryKey: ["platform-tenants"],
    queryFn: () => api.get<TenantSummary[]>("/api/v1/platform/enterprises"),
  });
  const operatorsList = useQuery({
    queryKey: ["platform-operators"],
    queryFn: () => api.get<OperatorSummary[]>("/api/v1/platform/operators"),
  });
  const supportGrants = useQuery({
    queryKey: ["platform-support-grants"],
    queryFn: () => api.get<SupportAccessGrant[]>("/api/v1/platform/support-access-grants"),
  });
  const platformAudit = useQuery({
    queryKey: ["platform-audit"],
    queryFn: () => api.get<AuditEvent[]>("/api/v1/platform/audit"),
  });
  const jurisdictions = useQuery({
    queryKey: ["platform-jurisdictions"],
    queryFn: () => api.get<Jurisdiction[]>("/api/v1/jurisdictions"),
  });
  const regions = useQuery({
    queryKey: ["platform-regions"],
    queryFn: () => api.get<Region[]>("/api/v1/regions"),
  });
  const modelProviders = useQuery({
    queryKey: ["platform-model-providers"],
    queryFn: () => api.get<ModelProvider[]>("/api/v1/model-providers"),
  });

  const invalidateTenants = () => queryClient.invalidateQueries({ queryKey: ["platform-tenants"] });
  const invalidateOperators = () => queryClient.invalidateQueries({ queryKey: ["platform-operators"] });
  const invalidateSupportGrants = () => queryClient.invalidateQueries({ queryKey: ["platform-support-grants"] });
  const invalidateJurisdictions = () => queryClient.invalidateQueries({ queryKey: ["platform-jurisdictions"] });
  const invalidateRegions = () => queryClient.invalidateQueries({ queryKey: ["platform-regions"] });
  const invalidateModelProviders = () => queryClient.invalidateQueries({ queryKey: ["platform-model-providers"] });

  if ((user?.platform_roles?.length ?? 0) === 0) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not hold a platform administration role.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-8">
      <Link href="/dashboard" className="text-sm underline">&larr; Dashboard</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Platform administration</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Platform-wide governance: every action below is independently re-checked server-side
        against your platform role assignment on every request, regardless of what this page
        shows.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Enterprise tenants</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {tenants.data?.map((t) => (
            <TenantRow key={t.id} tenant={t} onChanged={invalidateTenants} />
          ))}
          {tenants.isError && <li className="text-zinc-500">You do not have permission to manage tenants.</li>}
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Operators</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {operatorsList.data?.map((o) => (
            <OperatorRow key={o.id} operator={o} onChanged={invalidateOperators} />
          ))}
          {operatorsList.isError && <li className="text-zinc-500">You do not have permission to manage operators.</li>}
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Support access grants</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {supportGrants.data?.map((g) => (
            <SupportGrantRow key={g.id} grant={g} onChanged={invalidateSupportGrants} />
          ))}
          {supportGrants.data?.length === 0 && <li className="text-zinc-500">No support access grants yet.</li>}
          {supportGrants.isError && <li className="text-zinc-500">You do not have permission to view support access grants.</li>}
        </ul>
        <CreateSupportGrantForm onCreated={invalidateSupportGrants} />
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Region &amp; jurisdiction taxonomy</h2>
        <div className="mb-3 flex flex-col gap-2 text-sm">
          <p className="font-medium">Jurisdictions</p>
          <ul className="flex flex-wrap gap-2">
            {jurisdictions.data?.map((j) => (
              <li key={j.id} className="rounded border border-zinc-200 px-2 py-1 text-xs dark:border-zinc-800">
                {j.name} ({j.country_code})
              </li>
            ))}
          </ul>
        </div>
        <CreateJurisdictionForm onCreated={invalidateJurisdictions} />
        <div className="mt-4 mb-3 flex flex-col gap-2 text-sm">
          <p className="font-medium">Regions</p>
          <ul className="flex flex-wrap gap-2">
            {regions.data?.map((r) => (
              <li key={r.id} className="rounded border border-zinc-200 px-2 py-1 text-xs dark:border-zinc-800">
                {r.name} ({r.key}) &middot; {r.status}
              </li>
            ))}
          </ul>
        </div>
        <CreateRegionForm jurisdictions={jurisdictions.data} onCreated={invalidateRegions} />
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">AI model providers</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {modelProviders.data?.map((p) => (
            <ModelProviderRow key={p.id} provider={p} onChanged={invalidateModelProviders} />
          ))}
        </ul>
        <CreateModelProviderForm onCreated={invalidateModelProviders} />
      </section>

      <section>
        <h2 className="mb-3 text-lg font-medium">Platform audit log</h2>
        <ul className="flex flex-col gap-1 text-sm">
          {platformAudit.data?.map((e) => (
            <li key={e.seq} className="flex justify-between border-b border-zinc-100 py-1 dark:border-zinc-900">
              <span>{e.action}</span>
              <span className="text-zinc-500">{new Date(e.occurred_at).toLocaleString()}</span>
            </li>
          ))}
          {platformAudit.isError && <li className="text-zinc-500">You do not have permission to view the platform audit log.</li>}
        </ul>
      </section>
    </main>
  );
}

function TenantRow({ tenant, onChanged }: { tenant: TenantSummary; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [planKey, setPlanKey] = useState("");

  const setStatus = async (status: string) => {
    setError(null);
    try {
      await api.patch(`/api/v1/platform/enterprises/${tenant.id}/status`, { status });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update tenant status.");
    }
  };
  const assignPlan = async () => {
    setError(null);
    try {
      await api.patch(`/api/v1/platform/enterprises/${tenant.id}/subscription`, { plan_key: planKey });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to assign plan.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span>{tenant.display_name} <span className="text-zinc-500">({tenant.country})</span></span>
        <span className="text-zinc-500">{tenant.status}</span>
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        {["active", "suspended", "offboarding", "terminated"].map((s) => (
          <button key={s} onClick={() => setStatus(s)} disabled={tenant.status === s} className="underline disabled:opacity-40">
            {s}
          </button>
        ))}
        <select aria-label="Subscription plan" value={planKey} onChange={(e) => setPlanKey(e.target.value)}
          className="rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Assign plan&hellip;</option>
          {ENTERPRISE_PLANS.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <button onClick={assignPlan} disabled={!planKey} className="underline disabled:opacity-40">Assign</button>
      </div>
    </li>
  );
}

function OperatorRow({ operator, onChanged }: { operator: OperatorSummary; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [planKey, setPlanKey] = useState("");

  const setStatus = async (status: string) => {
    setError(null);
    try {
      await api.patch(`/api/v1/platform/operators/${operator.id}/status`, { status });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update operator status.");
    }
  };
  const setTrustLevel = async (trustLevel: string) => {
    setError(null);
    try {
      await api.patch(`/api/v1/platform/operators/${operator.id}/trust-level`, { trust_level: trustLevel });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update trust level.");
    }
  };
  const assignPlan = async () => {
    setError(null);
    try {
      await api.patch(`/api/v1/platform/operators/${operator.id}/subscription`, { plan_key: planKey });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to assign plan.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span>{operator.display_name} <span className="text-zinc-500">({operator.country})</span></span>
        <span className="text-zinc-500">{operator.status} &middot; {operator.trust_level}</span>
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        {["pending_application", "under_review", "approved", "active", "suspended", "offboarding", "terminated"].map((s) => (
          <button key={s} onClick={() => setStatus(s)} disabled={operator.status === s} className="underline disabled:opacity-40">
            {s}
          </button>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        {["unverified", "verified", "revoked"].map((tl) => (
          <button key={tl} onClick={() => setTrustLevel(tl)} disabled={operator.trust_level === tl} className="underline disabled:opacity-40">
            {tl}
          </button>
        ))}
        <select aria-label="Operator plan" value={planKey} onChange={(e) => setPlanKey(e.target.value)}
          className="rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Assign plan&hellip;</option>
          {OPERATOR_PLANS.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <button onClick={assignPlan} disabled={!planKey} className="underline disabled:opacity-40">Assign</button>
      </div>
    </li>
  );
}

function SupportGrantRow({ grant, onChanged }: { grant: SupportAccessGrant; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const isActive = grant.approved_by && !grant.revoked_at;
  const isPending = !grant.approved_by && !grant.revoked_at;

  const approve = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/platform/support-access-grants/${grant.id}/approve`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to approve grant.");
    }
  };
  const revoke = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/platform/support-access-grants/${grant.id}/revoke`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to revoke grant.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span>{grant.scope_type} {grant.scope_id.slice(0, 8)}&hellip; &middot; {grant.reason}</span>
        <span className="text-zinc-500">
          {grant.revoked_at ? "revoked" : grant.approved_by ? "active" : "pending"}
        </span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">Expires {new Date(grant.expires_at).toLocaleString()}</p>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      <div className="mt-2 flex gap-3 text-xs">
        {isPending && <button onClick={approve} className="underline">Approve (dual control)</button>}
        {isActive && <button onClick={revoke} className="text-red-600 underline">Revoke</button>}
      </div>
    </li>
  );
}

function CreateSupportGrantForm({ onCreated }: { onCreated: () => void }) {
  const [scopeType, setScopeType] = useState("enterprise");
  const [scopeId, setScopeId] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post("/api/v1/platform/support-access-grants", { scope_type: scopeType, scope_id: scopeId, reason });
      setScopeId("");
      setReason("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to request support access.");
    }
  };

  return (
    <div className="mt-3 flex flex-col gap-2 rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
      <label className="flex flex-col gap-1">
        Scope
        <select aria-label="Support-grant scope type" value={scopeType} onChange={(e) => setScopeType(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900">
          <option value="enterprise">Enterprise tenant</option>
          <option value="operator">Operator</option>
        </select>
      </label>
      <label className="flex flex-col gap-1">
        Scope ID
        <input value={scopeId} onChange={(e) => setScopeId(e.target.value)} placeholder="tenant or operator ID"
          className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" aria-label="tenant or operator ID" />
      </label>
      <label className="flex flex-col gap-1">
        Reason
        <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why support access is needed"
          className="rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900" aria-label="Why support access is needed" />
      </label>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <button onClick={create} disabled={!scopeId || !reason}
        className="self-start rounded-md bg-zinc-900 px-4 py-2 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
        Request support access
      </button>
    </div>
  );
}

function CreateJurisdictionForm({ onCreated }: { onCreated: () => void }) {
  const [countryCode, setCountryCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post("/api/v1/jurisdictions", { country_code: countryCode.toUpperCase(), name });
      setCountryCode("");
      setName("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create jurisdiction.");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <input value={countryCode} onChange={(e) => setCountryCode(e.target.value)} placeholder="Country code (e.g. AE)" aria-label="Country code"
        className="w-40 rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900" />
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Jurisdiction name" aria-label="Jurisdiction name"
        className="w-48 rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900" />
      {error && <p className="text-red-600">{error}</p>}
      <button onClick={create} disabled={!countryCode || !name}
        className="rounded-md bg-zinc-900 px-3 py-1 font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
        Create jurisdiction
      </button>
    </div>
  );
}

function CreateRegionForm({ jurisdictions, onCreated }: { jurisdictions: Jurisdiction[] | undefined; onCreated: () => void }) {
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [jurisdictionId, setJurisdictionId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post("/api/v1/regions", { key, name, jurisdiction_id: jurisdictionId });
      setKey("");
      setName("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create region.");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="Region key (e.g. eu-central-1)" aria-label="Region key"
        className="w-48 rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900" />
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Region name" aria-label="Region name"
        className="w-40 rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900" />
      <select aria-label="Jurisdiction" value={jurisdictionId} onChange={(e) => setJurisdictionId(e.target.value)}
        className="rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900">
        <option value="">Select jurisdiction</option>
        {jurisdictions?.map((j) => (
          <option key={j.id} value={j.id}>{j.name}</option>
        ))}
      </select>
      {error && <p className="text-red-600">{error}</p>}
      <button onClick={create} disabled={!key || !name || !jurisdictionId}
        className="rounded-md bg-zinc-900 px-3 py-1 font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
        Create region
      </button>
    </div>
  );
}

function ModelProviderRow({ provider, onChanged }: { provider: ModelProvider; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);

  const suspend = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/model-providers/${provider.id}/suspend`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to suspend provider.");
    }
  };
  const reactivate = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/model-providers/${provider.id}/reactivate`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to reactivate provider.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span>{provider.name} <span className="text-zinc-500">({provider.key})</span></span>
        <span className="text-zinc-500">{provider.status}</span>
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      <div className="mt-2 flex gap-3 text-xs">
        {provider.status === "active" && <button onClick={suspend} className="text-red-600 underline">Suspend</button>}
        {provider.status === "suspended" && <button onClick={reactivate} className="underline">Reactivate</button>}
      </div>
    </li>
  );
}

function CreateModelProviderForm({ onCreated }: { onCreated: () => void }) {
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [website, setWebsite] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post("/api/v1/model-providers", { key, name, website });
      setKey("");
      setName("");
      setWebsite("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to onboard provider.");
    }
  };

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
      <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="Provider key (e.g. acme-ai)" aria-label="Provider key"
        className="w-40 rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900" />
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Provider name" aria-label="Provider name"
        className="w-40 rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900" />
      <input value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="Website (optional)" aria-label="Provider website"
        className="w-48 rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900" />
      {error && <p className="text-red-600">{error}</p>}
      <button onClick={create} disabled={!key || !name}
        className="rounded-md bg-zinc-900 px-3 py-1 font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
        Onboard provider
      </button>
    </div>
  );
}
