"use client";

import { use, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, uploadToPresignedURL, type EnterpriseMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface Artefact {
  id: string;
  purpose: string;
  content_type: string;
  content_length?: number;
  status: string;
  malware_scan_status: string;
  checksum_sha256?: string;
  created_at: string;
}

const CAN_UPLOAD = new Set(["enterprise_owner", "enterprise_admin", "security_administrator", "ai_platform_engineer", "data_engineer"]);
const CAN_DELETE = new Set(["enterprise_owner", "enterprise_admin", "security_administrator", "data_engineer"]);

async function sha256Hex(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export default function ArtefactsPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);

  const members = useQuery({
    queryKey: ["tenant-members", tenantId],
    queryFn: () => api.get<EnterpriseMembership[]>(`/api/v1/enterprises/${tenantId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const canUpload = CAN_UPLOAD.has(myRole);
  const canDelete = CAN_DELETE.has(myRole);

  const artefacts = useQuery({
    queryKey: ["artefacts", tenantId],
    queryFn: () => api.get<Artefact[]>(`/api/v1/enterprises/${tenantId}/artefacts`),
  });

  const [purpose, setPurpose] = useState("workload_artefact");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["artefacts", tenantId] });

  const upload = async () => {
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const checksum = await sha256Hex(file);
      const { upload: created, upload_url: uploadUrl } = await api.post<{ upload: Artefact; upload_url: string }>(
        `/api/v1/enterprises/${tenantId}/artefacts`,
        { purpose, content_type: file.type || "application/octet-stream", content_length: file.size },
      );
      await uploadToPresignedURL(uploadUrl, file);
      await api.post(`/api/v1/enterprises/${tenantId}/artefacts/${created.id}/complete`, { checksum_sha256: checksum });
      if (fileInput.current) fileInput.current.value = "";
      invalidate();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const download = async (id: string) => {
    try {
      const { download_url: url } = await api.post<{ download_url: string }>(
        `/api/v1/enterprises/${tenantId}/artefacts/${id}/download`, {},
      );
      window.open(url, "_blank");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to get download URL.");
    }
  };

  const remove = async (id: string) => {
    try {
      await api.delete(`/api/v1/enterprises/${tenantId}/artefacts/${id}`);
      invalidate();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete artefact.");
    }
  };

  if (artefacts.isError && artefacts.error instanceof ApiError && artefacts.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
        <p>You do not have access to this tenant&apos;s artefacts.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
      <Link href={`/dashboard/enterprise/${tenantId}`} className="text-sm underline"><span aria-hidden="true" className="rtl-mirror">&larr;</span> Tenant overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Artefacts</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Uploads go straight from your browser to storage via a short-lived, server-issued URL --
        control-api never sees the file bytes or holds storage credentials. Completion is verified
        server-side by re-hashing the object, not by trusting what the browser reports.
      </p>

      {canUpload && (
        <section className="mb-8 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h2 className="mb-2 text-sm font-medium">Upload an artefact</h2>
          <div className="flex flex-col gap-2">
            <select aria-label="Artefact purpose" value={purpose} onChange={(e) => setPurpose(e.target.value)}
              className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
              <option value="workload_artefact">Workload artefact</option>
              <option value="model_artefact">Model artefact</option>
              <option value="sbom_raw">Raw SBOM document</option>
              <option value="other">Other</option>
            </select>
            <input ref={fileInput} type="file" aria-label="Artefact file" className="text-sm" />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button onClick={upload} disabled={uploading}
              className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
              {uploading ? "Uploading..." : "Upload"}
            </button>
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-3 text-lg font-medium">Uploaded artefacts</h2>
        <ul className="flex flex-col gap-2">
          {artefacts.data?.map((a) => (
            <li key={a.id} className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
              <div className="flex items-center justify-between flex-wrap gap-1">
                <span>{a.purpose} &middot; {a.content_type}</span>
                <span className="text-xs text-zinc-500">{a.status}</span>
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                {a.content_length ? `${a.content_length} bytes` : ""} &middot; malware scan: {a.malware_scan_status}
              </p>
              <div className="mt-2 flex gap-3 flex-wrap">
                {a.status === "uploaded" && (
                  <button onClick={() => download(a.id)} className="text-xs underline">Download</button>
                )}
                {canDelete && a.status !== "deleted" && (
                  <button onClick={() => remove(a.id)} className="text-xs text-red-600 underline">Delete</button>
                )}
              </div>
            </li>
          ))}
          {artefacts.data?.length === 0 && <li className="text-sm text-zinc-500">No artefacts uploaded yet.</li>}
        </ul>
      </section>
    </main>
  );
}
