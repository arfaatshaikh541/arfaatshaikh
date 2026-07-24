"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";

interface MarketplaceModelVersion {
  id: string;
  model_id: string;
  enterprise_tenant_id: string;
  version: number;
  visibility: string;
  permitted_geographies: string[];
  prohibited_geographies: string[];
  supported_languages: string[];
  price_per_unit?: number;
  pricing_unit: string;
  currency: string;
  published_at?: string;
}

interface Capability {
  id: string;
  capability_key: string;
  description: string;
}

interface Benchmark {
  id: string;
  benchmark_name: string;
  metric_name: string;
  metric_value: number;
}

interface SafetyEvaluation {
  id: string;
  evaluator: string;
  result: string;
}

interface DeploymentProfile {
  id: string;
  profile_key: string;
  name: string;
}

interface ModelAccessGrant {
  id: string;
  model_version_id: string;
  price_per_unit_override?: number;
  status: string;
}

export default function ModelMarketplacePage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);

  const versions = useQuery({
    queryKey: ["model-marketplace-versions", tenantId],
    queryFn: () => api.get<MarketplaceModelVersion[]>(`/api/v1/enterprises/${tenantId}/model-marketplace/versions`),
  });
  const receivedGrants = useQuery({
    queryKey: ["model-access-grants-received", tenantId],
    queryFn: () => api.get<ModelAccessGrant[]>(`/api/v1/enterprises/${tenantId}/model-access-grants/received`),
  });

  if (versions.isError && versions.error instanceof ApiError && versions.error.status === 403) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not have access to this tenant&apos;s model exchange.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 p-8">
      <Link href={`/dashboard/enterprise/${tenantId}`} className="text-sm underline">&larr; Tenant overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">AI model exchange</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Approved model versions other enterprise tenants have published publicly, or privately granted
        this tenant access to. Pricing shown already reflects any per-tenant grant override -- never a
        base price your workloads would not actually be charged.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Available model versions</h2>
        <ul className="flex flex-col gap-3">
          {versions.data?.map((v) => (
            <MarketplaceVersionCard key={v.id} tenantId={tenantId} version={v} />
          ))}
          {versions.data?.length === 0 && (
            <li className="text-sm text-zinc-500">No public or granted model versions available yet.</li>
          )}
        </ul>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-medium">My access grants</h2>
        <ul className="flex flex-col gap-2">
          {receivedGrants.data?.map((g) => (
            <li key={g.id} className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
              Version {g.model_version_id.slice(0, 8)}&hellip;
              {g.price_per_unit_override != null && <> &middot; your price {g.price_per_unit_override}</>}
              {" "}&middot; {g.status}
            </li>
          ))}
          {receivedGrants.data?.length === 0 && <li className="text-sm text-zinc-500">No access grants received.</li>}
        </ul>
      </section>
    </main>
  );
}

function MarketplaceVersionCard({ tenantId, version }: { tenantId: string; version: MarketplaceModelVersion }) {
  const [expanded, setExpanded] = useState(false);
  const capabilities = useQuery({
    queryKey: ["marketplace-capabilities", version.id],
    queryFn: () => api.get<Capability[]>(`/api/v1/enterprises/${tenantId}/model-marketplace/versions/${version.id}/capabilities`),
    enabled: expanded,
  });
  const benchmarks = useQuery({
    queryKey: ["marketplace-benchmarks", version.id],
    queryFn: () => api.get<Benchmark[]>(`/api/v1/enterprises/${tenantId}/model-marketplace/versions/${version.id}/benchmarks`),
    enabled: expanded,
  });
  const safetyEvaluations = useQuery({
    queryKey: ["marketplace-safety-evaluations", version.id],
    queryFn: () => api.get<SafetyEvaluation[]>(`/api/v1/enterprises/${tenantId}/model-marketplace/versions/${version.id}/safety-evaluations`),
    enabled: expanded,
  });
  const deploymentProfiles = useQuery({
    queryKey: ["marketplace-deployment-profiles", version.id],
    queryFn: () => api.get<DeploymentProfile[]>(`/api/v1/enterprises/${tenantId}/model-marketplace/versions/${version.id}/deployment-profiles`),
    enabled: expanded,
  });

  return (
    <li className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
      <button onClick={() => setExpanded(!expanded)} className="flex w-full items-center justify-between text-left">
        <span className="font-medium">
          Version {version.id.slice(0, 8)}&hellip; <span className="text-zinc-500">(v{version.version})</span>
        </span>
        <span className="text-xs text-zinc-500">
          {version.visibility === "public" ? "public" : "private grant"} {expanded ? "−" : "+"}
        </span>
      </button>
      {version.price_per_unit != null && (
        <p className="mt-1 text-xs text-zinc-500">
          {version.currency} {version.price_per_unit}{version.pricing_unit ? ` / ${version.pricing_unit}` : ""}
        </p>
      )}
      {version.permitted_geographies?.length > 0 && (
        <p className="text-xs text-zinc-500">Permitted: {version.permitted_geographies.join(", ")}</p>
      )}
      {version.supported_languages?.length > 0 && (
        <p className="text-xs text-zinc-500">Languages: {version.supported_languages.join(", ")}</p>
      )}

      {expanded && (
        <div className="mt-3 flex flex-col gap-2 text-xs text-zinc-600 dark:text-zinc-400">
          <div>
            <span className="font-medium">Capabilities: </span>
            {capabilities.data?.map((c) => c.capability_key).join(", ") || "none listed"}
          </div>
          <div>
            <span className="font-medium">Benchmarks: </span>
            {benchmarks.data?.map((b) => `${b.benchmark_name} ${b.metric_name}=${b.metric_value}`).join(", ") || "none listed"}
          </div>
          <div>
            <span className="font-medium">Safety evaluations: </span>
            {safetyEvaluations.data?.map((s) => `${s.evaluator}: ${s.result}`).join(", ") || "none listed"}
          </div>
          <div>
            <span className="font-medium">Deployment profiles: </span>
            {deploymentProfiles.data?.map((p) => p.name).join(", ") || "none listed"}
          </div>
        </div>
      )}
    </li>
  );
}
