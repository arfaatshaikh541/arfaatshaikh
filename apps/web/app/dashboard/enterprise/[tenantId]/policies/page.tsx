"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type EnterpriseMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface ResidencyConstraint {
  allowed_countries: string[];
  denied_countries: string[];
}

interface OperatorConstraint {
  allowed: string[];
  denied: string[];
}

interface ConfidentialComputingConstraint {
  required: boolean;
}

interface CrossBorderConstraint {
  backup_allowed_countries: string[];
  failover_allowed_countries: string[];
}

interface EncryptionConstraint {
  key_ownership?: string | null;
}

interface PolicyDocument {
  residency: ResidencyConstraint;
  operators: OperatorConstraint;
  confidential_computing: ConfidentialComputingConstraint;
  cross_border: CrossBorderConstraint;
  encryption: EncryptionConstraint;
}

interface SovereigntyPolicy {
  id: string;
  policy_key: string;
  version: number;
  status: string;
  name: string;
  document: PolicyDocument;
  requested_by: string;
  approved_by?: string;
  rolled_back_from_version?: number;
  created_at: string;
}

interface EvaluationCandidate {
  country: string;
  operator_id: string;
  confidential_computing_available: boolean;
  placement_role: string;
  encryption_key_ownership?: string | null;
}

interface EvaluationResult {
  decision: "allow" | "deny";
  reason_codes: string[];
  policy_version: number;
  evaluated_at: string;
}

interface EvaluationRecord {
  id: string;
  sovereignty_policy_id: string;
  policy_version: number;
  decision: string;
  reason_codes: string[];
  is_simulation: boolean;
  evaluated_at: string;
}

// Roles known (from docs/security/permission-matrix.md) to hold the
// server-side policies.* permissions each action requires. This only drives
// which controls are shown -- control-api independently re-checks every
// permission on every request regardless of what this page renders.
const CAN_MANAGE = new Set(["enterprise_owner", "enterprise_admin", "security_administrator"]);
const CAN_SIMULATE = new Set(["enterprise_owner", "enterprise_admin", "security_administrator", "ai_platform_engineer", "compliance_manager"]);

function emptyDocument(): PolicyDocument {
  return {
    residency: { allowed_countries: [], denied_countries: [] },
    operators: { allowed: [], denied: [] },
    confidential_computing: { required: false },
    cross_border: { backup_allowed_countries: [], failover_allowed_countries: [] },
    encryption: { key_ownership: null },
  };
}

function csvToList(value: string): string[] {
  return value
    .split(",")
    .map((v) => v.trim().toUpperCase())
    .filter((v) => v.length > 0);
}

export default function TenantPoliciesPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["tenant-members", tenantId],
    queryFn: () => api.get<EnterpriseMembership[]>(`/api/v1/enterprises/${tenantId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const canManage = CAN_MANAGE.has(myRole);
  const canSimulate = CAN_SIMULATE.has(myRole);

  const policies = useQuery({
    queryKey: ["policies", tenantId],
    queryFn: () => api.get<SovereigntyPolicy[]>(`/api/v1/enterprises/${tenantId}/policies`),
  });

  const evaluations = useQuery({
    queryKey: ["policy-evaluations", tenantId],
    queryFn: () => api.get<EvaluationRecord[]>(`/api/v1/enterprises/${tenantId}/policy-evaluations`),
  });

  const invalidatePolicies = () => {
    queryClient.invalidateQueries({ queryKey: ["policies", tenantId] });
    queryClient.invalidateQueries({ queryKey: ["policy-evaluations", tenantId] });
  };

  if (policies.isError && policies.error instanceof ApiError && policies.error.status === 403) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not have access to this tenant&apos;s sovereignty policies.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 p-8">
      <Link href={`/dashboard/enterprise/${tenantId}`} className="text-sm underline">&larr; Tenant overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Sovereignty policies</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Deterministic, deny-by-default residency and sovereignty constraints, evaluated by the policy-engine
        service. Publishing requires a second, different user to approve (dual control).
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Policies</h2>
        <ul className="flex flex-col gap-3">
          {policies.data?.map((p) => (
            <PolicyCard
              key={p.id}
              tenantId={tenantId}
              policy={p}
              myUserId={user?.user_id}
              canManage={canManage}
              canSimulate={canSimulate}
              onChanged={invalidatePolicies}
            />
          ))}
          {policies.data?.length === 0 && <li className="text-sm text-zinc-500">No policies defined yet.</li>}
        </ul>
      </section>

      {canManage && <CreatePolicyForm tenantId={tenantId} onCreated={invalidatePolicies} />}

      <section className="mt-8">
        <h2 className="mb-3 text-lg font-medium">Evaluation evidence</h2>
        <p className="mb-3 text-xs text-zinc-500">
          Every real (non-simulation) evaluation is retained here, append-only, as compliance evidence.
        </p>
        <ul className="flex flex-col gap-1 text-sm">
          {evaluations.data?.map((e) => (
            <li key={e.id} className="flex items-center justify-between border-b border-zinc-100 py-1 dark:border-zinc-900">
              <span>
                v{e.policy_version} &middot; <span className={e.decision === "allow" ? "text-green-700 dark:text-green-400" : "text-red-600"}>{e.decision}</span>
                {e.reason_codes.length > 0 && <span className="text-zinc-500"> ({e.reason_codes.join(", ")})</span>}
              </span>
              <span className="text-zinc-500">{new Date(e.evaluated_at).toLocaleString()}</span>
            </li>
          ))}
          {evaluations.data?.length === 0 && <li className="text-zinc-500">No evaluations recorded yet.</li>}
          {evaluations.isError && <li className="text-zinc-500">You do not have permission to view evaluation evidence.</li>}
        </ul>
      </section>
    </main>
  );
}

function PolicyCard({
  tenantId,
  policy,
  myUserId,
  canManage,
  canSimulate,
  onChanged,
}: {
  tenantId: string;
  policy: SovereigntyPolicy;
  myUserId: string | undefined;
  canManage: boolean;
  canSimulate: boolean;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [candidate, setCandidate] = useState<EvaluationCandidate>({
    country: "",
    operator_id: "",
    confidential_computing_available: false,
    placement_role: "primary",
    encryption_key_ownership: null,
  });
  const [lastResult, setLastResult] = useState<EvaluationResult | null>(null);
  const [rollbackVersion, setRollbackVersion] = useState("");

  const requestPublish = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/policies/${policy.id}/request-publish`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to request publish.");
    }
  };

  const approvePublish = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/policies/${policy.id}/approve-publish`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to approve publish.");
    }
  };

  const rollback = async () => {
    setError(null);
    const toVersion = parseInt(rollbackVersion, 10);
    if (!toVersion || toVersion <= 0) {
      setError("Enter a valid version number to roll back to.");
      return;
    }
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/policies/by-key/${policy.policy_key}/rollback`, { to_version: toVersion });
      setRollbackVersion("");
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to roll back.");
    }
  };

  const runSimulate = async () => {
    setError(null);
    try {
      const result = await api.post<EvaluationResult>(`/api/v1/enterprises/${tenantId}/policies/${policy.id}/simulate`, { candidate });
      setLastResult(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to simulate.");
    }
  };

  const runEvaluate = async () => {
    setError(null);
    try {
      const result = await api.post<EvaluationResult>(`/api/v1/enterprises/${tenantId}/policies/${policy.id}/evaluate`, { candidate });
      setLastResult(result);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to evaluate.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span className="font-medium">{policy.name} <span className="text-zinc-500">({policy.policy_key})</span></span>
        <span className="text-xs text-zinc-500">v{policy.version} &middot; {policy.status}</span>
      </div>
      {policy.rolled_back_from_version != null && (
        <p className="mt-1 text-xs text-zinc-500">Rolled back from v{policy.rolled_back_from_version}</p>
      )}
      <pre className="mt-2 overflow-x-auto rounded bg-zinc-50 p-2 text-xs text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
        {JSON.stringify(policy.document, null, 2)}
      </pre>

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {canManage && policy.status === "draft" && (
        <button onClick={requestPublish} className="mt-3 rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-white dark:text-zinc-900">
          Request publish
        </button>
      )}

      {canManage && policy.status === "pending_publish" && (
        <div className="mt-3">
          {policy.requested_by === myUserId ? (
            <p className="text-xs text-zinc-500">Awaiting approval from a different user (dual control -- you requested this publish).</p>
          ) : (
            <button onClick={approvePublish} className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-white dark:text-zinc-900">
              Approve publish
            </button>
          )}
        </div>
      )}

      {canManage && (
        <div className="mt-3 flex items-center gap-2">
          <input
            placeholder="Version #"
            value={rollbackVersion}
            onChange={(e) => setRollbackVersion(e.target.value)}
            className="w-24 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
          />
          <button onClick={rollback} className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium dark:border-zinc-700">
            Roll back to version
          </button>
        </div>
      )}

      {canSimulate && (
        <div className="mt-4 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <h4 className="mb-2 text-xs font-medium">Evaluate a candidate</h4>
          <div className="flex flex-wrap gap-2">
            <input placeholder="Country (e.g. AE)" value={candidate.country}
              onChange={(e) => setCandidate({ ...candidate, country: e.target.value.toUpperCase() })}
              className="w-32 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" />
            <input placeholder="Operator ID" value={candidate.operator_id}
              onChange={(e) => setCandidate({ ...candidate, operator_id: e.target.value })}
              className="w-40 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" />
            <select value={candidate.placement_role}
              onChange={(e) => setCandidate({ ...candidate, placement_role: e.target.value })}
              className="rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900">
              <option value="primary">primary</option>
              <option value="backup">backup</option>
              <option value="failover">failover</option>
            </select>
            <label className="flex items-center gap-1 text-xs">
              <input type="checkbox" checked={candidate.confidential_computing_available}
                onChange={(e) => setCandidate({ ...candidate, confidential_computing_available: e.target.checked })} />
              Confidential computing available
            </label>
          </div>
          <div className="mt-2 flex gap-2">
            <button onClick={runSimulate} className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium dark:border-zinc-700">
              Simulate (no evidence)
            </button>
            {policy.status === "published" && (
              <button onClick={runEvaluate} className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-white dark:text-zinc-900">
                Evaluate (records evidence)
              </button>
            )}
          </div>
          {lastResult && (
            <p className="mt-2 text-xs">
              Decision: <span className={lastResult.decision === "allow" ? "font-medium text-green-700 dark:text-green-400" : "font-medium text-red-600"}>{lastResult.decision}</span>
              {lastResult.reason_codes.length > 0 && <span className="text-zinc-500"> -- {lastResult.reason_codes.join(", ")}</span>}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

function CreatePolicyForm({ tenantId, onCreated }: { tenantId: string; onCreated: () => void }) {
  const [policyKey, setPolicyKey] = useState("");
  const [name, setName] = useState("");
  const [allowedCountries, setAllowedCountries] = useState("");
  const [deniedCountries, setDeniedCountries] = useState("");
  const [confidentialRequired, setConfidentialRequired] = useState(false);
  const [keyOwnership, setKeyOwnership] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    const document: PolicyDocument = {
      ...emptyDocument(),
      residency: {
        allowed_countries: csvToList(allowedCountries),
        denied_countries: csvToList(deniedCountries),
      },
      confidential_computing: { required: confidentialRequired },
      encryption: { key_ownership: keyOwnership || null },
    };
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/policies`, { policy_key: policyKey, name, document });
      setPolicyKey("");
      setName("");
      setAllowedCountries("");
      setDeniedCountries("");
      setConfidentialRequired(false);
      setKeyOwnership("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create policy draft.");
    }
  };

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Draft a new policy</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Policy key (e.g. data-residency)" value={policyKey} onChange={(e) => setPolicyKey(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <input placeholder="Allowed countries (comma-separated, e.g. AE,SA)" value={allowedCountries} onChange={(e) => setAllowedCountries(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <input placeholder="Denied countries (comma-separated)" value={deniedCountries} onChange={(e) => setDeniedCountries(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={confidentialRequired} onChange={(e) => setConfidentialRequired(e.target.checked)} />
          Require confidential computing
        </label>
        <select value={keyOwnership} onChange={(e) => setKeyOwnership(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">No encryption key ownership constraint</option>
          <option value="customer_managed">Customer-managed keys required</option>
          <option value="provider_managed">Provider-managed keys required</option>
        </select>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!policyKey || !name}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Create draft
        </button>
      </div>
    </section>
  );
}
