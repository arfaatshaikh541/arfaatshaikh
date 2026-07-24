"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type EnterpriseMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface Workload {
  id: string;
  workload_key: string;
  workload_type: string;
  name: string;
  status: string;
}

interface WorkloadVersion {
  id: string;
  version: number;
  status: string;
  container_image_id?: string;
  model_version_id?: string;
  requested_by: string;
  residency_requirements: { allowed_countries?: string[] };
}

interface ContainerImage {
  id: string;
  repository: string;
  digest: string;
  status: string;
}

interface Model {
  id: string;
  name: string;
}

interface ModelVersion {
  id: string;
  version: number;
  status: string;
}

interface Component {
  id: string;
  component_key: string;
  name: string;
  container_image_id: string;
  is_primary: boolean;
}

interface HealthCheck {
  id: string;
  check_type: string;
  path: string;
  interval_seconds: number;
  timeout_seconds: number;
  failure_threshold: number;
}

const WORKLOAD_TYPES = [
  "containerised_inference_api", "retrieval_augmented_generation_application", "private_ai_assistant",
  "computer_vision_inference", "speech_to_text_service", "text_to_speech_service", "embedding_service",
  "ai_agent_runtime", "batch_inference", "model_evaluation",
];

const CAN_CREATE = new Set(["enterprise_owner", "enterprise_admin", "ai_platform_engineer", "application_owner"]);
const CAN_PUBLISH = new Set(["enterprise_owner", "enterprise_admin", "ai_platform_engineer", "application_owner"]);
const CAN_RETIRE = new Set(["enterprise_owner", "enterprise_admin", "security_administrator"]);

export default function WorkloadsPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["tenant-members", tenantId],
    queryFn: () => api.get<EnterpriseMembership[]>(`/api/v1/enterprises/${tenantId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const canCreate = CAN_CREATE.has(myRole);
  const canPublish = CAN_PUBLISH.has(myRole);
  const canRetire = CAN_RETIRE.has(myRole);

  const workloads = useQuery({
    queryKey: ["workloads", tenantId],
    queryFn: () => api.get<Workload[]>(`/api/v1/enterprises/${tenantId}/workloads`),
  });
  const images = useQuery({
    queryKey: ["images", tenantId],
    queryFn: () => api.get<ContainerImage[]>(`/api/v1/enterprises/${tenantId}/images`),
  });
  const approvedImages = images.data?.filter((i) => i.status === "approved") ?? [];

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["workloads", tenantId] });

  if (workloads.isError && workloads.error instanceof ApiError && workloads.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
        <p>You do not have access to this tenant&apos;s workloads.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
      <Link href={`/dashboard/enterprise/${tenantId}`} className="text-sm underline">&larr; Tenant overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Workloads</h1>
      <p className="mb-6 text-sm text-zinc-500">
        A workload version can only reference an <em>approved</em> container image and an{" "}
        <em>approved</em> model version whose permitted geographies cover this version&apos;s
        declared residency requirements. Publishing is dual control, and a published version
        becomes immutable.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Registered workloads</h2>
        <ul className="flex flex-col gap-3">
          {workloads.data?.map((w) => (
            <WorkloadCard
              key={w.id}
              tenantId={tenantId}
              workload={w}
              approvedImages={approvedImages}
              myUserId={user?.user_id}
              canPublish={canPublish}
              canRetire={canRetire}
            />
          ))}
          {workloads.data?.length === 0 && <li className="text-sm text-zinc-500">No workloads registered yet.</li>}
        </ul>
      </section>

      {canCreate && <CreateWorkloadForm tenantId={tenantId} onCreated={invalidate} />}
    </main>
  );
}

function WorkloadCard({
  tenantId,
  workload,
  approvedImages,
  myUserId,
  canPublish,
  canRetire,
}: {
  tenantId: string;
  workload: Workload;
  approvedImages: ContainerImage[];
  myUserId: string | undefined;
  canPublish: boolean;
  canRetire: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [containerImageId, setContainerImageId] = useState("");
  const [modelId, setModelId] = useState("");
  const [modelVersionId, setModelVersionId] = useState("");
  const [allowedCountries, setAllowedCountries] = useState("");

  const versions = useQuery({
    queryKey: ["workload-versions", workload.id],
    queryFn: () => api.get<WorkloadVersion[]>(`/api/v1/enterprises/${tenantId}/workloads/${workload.id}/versions`),
    enabled: expanded,
  });
  const models = useQuery({
    queryKey: ["models", tenantId],
    queryFn: () => api.get<Model[]>(`/api/v1/enterprises/${tenantId}/models`),
    enabled: expanded,
  });
  const modelVersions = useQuery({
    queryKey: ["model-versions", modelId],
    queryFn: () => api.get<ModelVersion[]>(`/api/v1/enterprises/${tenantId}/models/${modelId}/versions`),
    enabled: expanded && !!modelId,
  });
  const approvedModelVersions = modelVersions.data?.filter((v) => v.status === "approved") ?? [];

  const invalidateVersions = () => versions.refetch();

  const createDraft = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/workloads/${workload.id}/versions`, {
        container_image_id: containerImageId || null,
        model_version_id: modelVersionId || null,
        residency_requirements: allowedCountries
          ? { allowed_countries: allowedCountries.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean) }
          : {},
        resource_requirements: {},
      });
      setContainerImageId("");
      setModelVersionId("");
      setAllowedCountries("");
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to draft workload version.");
    }
  };

  const requestPublish = async (versionId: string) => {
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/workload-versions/${versionId}/request-publish`, {});
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to request publish.");
    }
  };
  const approvePublish = async (versionId: string) => {
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/workload-versions/${versionId}/approve-publish`, {});
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to approve publish.");
    }
  };
  const retireVersion = async (versionId: string) => {
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/workload-versions/${versionId}/retire`, { reason: "retired from dashboard" });
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to retire version.");
    }
  };
  const deprecateVersion = async (versionId: string) => {
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/workload-versions/${versionId}/deprecate`, {});
      invalidateVersions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to deprecate version.");
    }
  };
  const [componentsOpenFor, setComponentsOpenFor] = useState<string | null>(null);

  return (
    <li className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
      <button onClick={() => setExpanded(!expanded)} className="flex w-full items-center justify-between text-left">
        <span className="font-medium">{workload.name} <span className="text-zinc-500">({workload.workload_type})</span></span>
        <span className="text-xs text-zinc-500">{workload.status} {expanded ? "−" : "+"}</span>
      </button>

      {expanded && (
        <div className="mt-3 flex flex-col gap-3">
          {error && <p className="text-sm text-red-600">{error}</p>}

          <ul className="flex flex-col gap-2">
            {versions.data?.map((v) => (
              <li key={v.id} className="rounded border border-zinc-100 p-2 dark:border-zinc-900">
                <div className="flex items-center justify-between flex-wrap gap-1">
                  <span>v{v.version}</span>
                  <span className="text-xs text-zinc-500">{v.status}</span>
                </div>
                {v.residency_requirements?.allowed_countries && v.residency_requirements.allowed_countries.length > 0 && (
                  <p className="text-xs text-zinc-500">Allowed countries: {v.residency_requirements.allowed_countries.join(", ")}</p>
                )}
                <div className="mt-1 flex flex-wrap gap-2">
                  {v.status === "draft" && canPublish && (
                    <button onClick={() => requestPublish(v.id)} className="text-xs underline">Request publish</button>
                  )}
                  {v.status === "pending_publish" && v.requested_by === myUserId && (
                    <span className="text-xs text-zinc-500">Awaiting a different approver</span>
                  )}
                  {v.status === "pending_publish" && canPublish && v.requested_by !== myUserId && (
                    <button onClick={() => approvePublish(v.id)} className="text-xs underline">Approve publish</button>
                  )}
                  {v.status === "published" && canPublish && (
                    <button onClick={() => deprecateVersion(v.id)} className="text-xs underline">Deprecate</button>
                  )}
                  {v.status === "published" && canRetire && (
                    <button onClick={() => retireVersion(v.id)} className="text-xs text-red-600 underline">Retire</button>
                  )}
                  <button onClick={() => setComponentsOpenFor(componentsOpenFor === v.id ? null : v.id)} className="text-xs underline">
                    {componentsOpenFor === v.id ? "Hide components" : "Components"}
                  </button>
                </div>
                {componentsOpenFor === v.id && <VersionComponentsPanel tenantId={tenantId} versionId={v.id} canEdit={canPublish} />}
              </li>
            ))}
            {versions.data?.length === 0 && <li className="text-xs text-zinc-500">No versions yet.</li>}
          </ul>

          {canPublish && (
            <div className="flex flex-col gap-2 rounded border border-zinc-100 p-2 dark:border-zinc-900">
              <h4 className="text-xs font-medium">Draft a new version</h4>
              <select aria-label="Container image" value={containerImageId} onChange={(e) => setContainerImageId(e.target.value)}
                className="rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900">
                <option value="">No container image</option>
                {approvedImages.map((img) => (
                  <option key={img.id} value={img.id}>{img.repository}@{img.digest.slice(0, 19)}&hellip;</option>
                ))}
              </select>
              <select aria-label="Model" value={modelId} onChange={(e) => { setModelId(e.target.value); setModelVersionId(""); }}
                className="rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900">
                <option value="">No model</option>
                {models.data?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
              {modelId && (
                <select aria-label="Model version" value={modelVersionId} onChange={(e) => setModelVersionId(e.target.value)}
                  className="rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900">
                  <option value="">Select an approved model version</option>
                  {approvedModelVersions.map((v) => <option key={v.id} value={v.id}>v{v.version}</option>)}
                </select>
              )}
              <input placeholder="Allowed countries (comma-separated, e.g. AE,SA)" value={allowedCountries}
                onChange={(e) => setAllowedCountries(e.target.value)}
                className="rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Allowed countries (comma-separated, e.g. AE,SA)" />
              <button onClick={createDraft} className="self-start rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-white dark:text-zinc-900">
                Create draft version
              </button>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

// VersionComponentsPanel lists a workload version's components and lets a
// publisher add new ones -- consumes GET/POST .../components, which existed
// with no frontend caller before Milestone 15.
function VersionComponentsPanel({ tenantId, versionId, canEdit }: { tenantId: string; versionId: string; canEdit: boolean }) {
  const [error, setError] = useState<string | null>(null);
  const [componentKey, setComponentKey] = useState("");
  const [name, setName] = useState("");
  const [containerImageId, setContainerImageId] = useState("");
  const [isPrimary, setIsPrimary] = useState(false);
  const [healthChecksOpenFor, setHealthChecksOpenFor] = useState<string | null>(null);

  const components = useQuery({
    queryKey: ["workload-version-components", versionId],
    queryFn: () => api.get<Component[]>(`/api/v1/enterprises/${tenantId}/workload-versions/${versionId}/components`),
  });

  const addComponent = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/workload-versions/${versionId}/components`, {
        component_key: componentKey, name, container_image_id: containerImageId,
        command: [], args: [], env: {}, is_primary: isPrimary,
      });
      setComponentKey("");
      setName("");
      setContainerImageId("");
      setIsPrimary(false);
      components.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add component.");
    }
  };

  return (
    <div className="mt-2 flex flex-col gap-2 rounded border border-zinc-100 p-2 dark:border-zinc-900">
      <h4 className="text-xs font-medium">Components</h4>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <ul className="flex flex-col gap-2">
        {components.data?.map((c) => (
          <li key={c.id} className="rounded border border-zinc-100 p-2 dark:border-zinc-900">
            <div className="flex items-center justify-between text-xs flex-wrap gap-1">
              <span>{c.name} <span className="text-zinc-500">({c.component_key})</span></span>
              {c.is_primary && <span className="text-zinc-500">primary</span>}
            </div>
            <button
              onClick={() => setHealthChecksOpenFor(healthChecksOpenFor === c.id ? null : c.id)}
              className="mt-1 text-xs underline"
            >
              {healthChecksOpenFor === c.id ? "Hide health checks" : "Health checks"}
            </button>
            {healthChecksOpenFor === c.id && <ComponentHealthChecksPanel tenantId={tenantId} componentId={c.id} canEdit={canEdit} />}
          </li>
        ))}
        {components.data?.length === 0 && <li className="text-xs text-zinc-500">No components yet.</li>}
      </ul>
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          <input placeholder="Component key" value={componentKey} onChange={(e) => setComponentKey(e.target.value)}
            className="w-32 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Component key" />
          <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)}
            className="w-32 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Name" />
          <input placeholder="Container image ID" value={containerImageId} onChange={(e) => setContainerImageId(e.target.value)}
            className="w-48 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Container image ID" />
          <label className="flex items-center gap-1 text-xs">
            <input type="checkbox" checked={isPrimary} onChange={(e) => setIsPrimary(e.target.checked)} />
            Primary
          </label>
          <button onClick={addComponent} disabled={!componentKey || !name || !containerImageId}
            className="rounded-md bg-zinc-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
            Add component
          </button>
        </div>
      )}
    </div>
  );
}

// ComponentHealthChecksPanel consumes GET/POST
// .../workload-components/{componentID}/health-checks, likewise previously
// unreachable from the frontend.
function ComponentHealthChecksPanel({ tenantId, componentId, canEdit }: { tenantId: string; componentId: string; canEdit: boolean }) {
  const [error, setError] = useState<string | null>(null);
  const [checkType, setCheckType] = useState("http");
  const [path, setPath] = useState("");

  const healthChecks = useQuery({
    queryKey: ["component-health-checks", componentId],
    queryFn: () => api.get<HealthCheck[]>(`/api/v1/enterprises/${tenantId}/workload-components/${componentId}/health-checks`),
  });

  const addHealthCheck = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/workload-components/${componentId}/health-checks`, {
        check_type: checkType, path, command: [], interval_seconds: 10, timeout_seconds: 5, failure_threshold: 3,
      });
      setPath("");
      healthChecks.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add health check.");
    }
  };

  return (
    <div className="mt-1 flex flex-col gap-1 rounded border border-zinc-100 p-2 dark:border-zinc-900">
      {error && <p className="text-xs text-red-600">{error}</p>}
      <ul className="flex flex-col gap-1 text-xs">
        {healthChecks.data?.map((hc) => (
          <li key={hc.id} className="flex items-center justify-between flex-wrap gap-1">
            <span>{hc.check_type} {hc.path}</span>
            <span className="text-zinc-500">every {hc.interval_seconds}s</span>
          </li>
        ))}
        {healthChecks.data?.length === 0 && <li className="text-zinc-500">No health checks yet.</li>}
      </ul>
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          <select aria-label="Health check type" value={checkType} onChange={(e) => setCheckType(e.target.value)}
            className="rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900">
            <option value="http">http</option>
            <option value="tcp">tcp</option>
            <option value="command">command</option>
          </select>
          <input placeholder="Path (e.g. /health)" value={path} onChange={(e) => setPath(e.target.value)}
            className="w-40 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Path (e.g. /health)" />
          <button onClick={addHealthCheck} className="rounded-md bg-zinc-900 px-3 py-1 text-xs font-medium text-white dark:bg-white dark:text-zinc-900">
            Add health check
          </button>
        </div>
      )}
    </div>
  );
}

function CreateWorkloadForm({ tenantId, onCreated }: { tenantId: string; onCreated: () => void }) {
  const [workloadKey, setWorkloadKey] = useState("");
  const [workloadType, setWorkloadType] = useState(WORKLOAD_TYPES[0]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/workloads`, {
        workload_key: workloadKey, workload_type: workloadType, name, description,
      });
      setWorkloadKey("");
      setName("");
      setDescription("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create workload.");
    }
  };

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Create a new workload</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Workload key (e.g. fictional-rag-app)" value={workloadKey} onChange={(e) => setWorkloadKey(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Workload key (e.g. fictional-rag-app)" />
        <select aria-label="Workload type" value={workloadType} onChange={(e) => setWorkloadType(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          {WORKLOAD_TYPES.map((t) => <option key={t} value={t}>{t.replaceAll("_", " ")}</option>)}
        </select>
        <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Name" />
        <input placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Description" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!workloadKey || !name}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Create workload
        </button>
      </div>
    </section>
  );
}
