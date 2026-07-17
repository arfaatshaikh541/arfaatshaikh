"use client";

import { Button } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { API_BASE_URL, apiClient, ApiError } from "@/lib/api-client";
import type { EvidenceRead } from "@/lib/types";

const EVIDENCE_TYPES = [
  { value: "note", label: "Note" },
  { value: "url", label: "URL" },
  { value: "document", label: "Document (file upload)" },
];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function EvidenceList({
  targetType,
  targetId,
  canManage,
}: {
  targetType: "compliance_control" | "incident";
  targetId: string;
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [evidenceType, setEvidenceType] = useState("note");
  const [sourceUrl, setSourceUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const queryKey = ["evidence", targetType, targetId];

  const evidenceQuery = useQuery({
    queryKey,
    queryFn: () =>
      apiClient.get<EvidenceRead[]>("/api/evidence", { target_type: targetType, target_id: targetId }),
  });

  const resetForm = () => {
    setTitle("");
    setDescription("");
    setSourceUrl("");
    setEvidenceType("note");
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const addEvidence = async () => {
    setError(null);
    setIsBusy(true);
    try {
      if (evidenceType === "document") {
        if (!file) throw new Error("Choose a file to upload.");
        const formData = new FormData();
        formData.set("title", title);
        formData.set("description", description);
        formData.set("target_type", targetType);
        formData.set("target_id", targetId);
        formData.set("file", file);
        await apiClient.postForm("/api/evidence/document", formData);
      } else {
        await apiClient.post("/api/evidence", {
          title,
          description,
          evidence_type: evidenceType,
          source_url: evidenceType === "url" ? sourceUrl : null,
          target_type: targetType,
          target_id: targetId,
        });
      }
      resetForm();
      queryClient.invalidateQueries({ queryKey });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  const deleteEvidence = async (evidenceId: string) => {
    setError(null);
    setIsBusy(true);
    try {
      await apiClient.delete(`/api/evidence/${evidenceId}`);
      queryClient.invalidateQueries({ queryKey });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {error ? <p className="text-xs text-severity-critical">{error}</p> : null}
      {evidenceQuery.data && evidenceQuery.data.length > 0 ? (
        <ul className="flex flex-col gap-1.5 text-sm">
          {evidenceQuery.data.map((e) => (
            <li key={e.id} className="flex items-start justify-between gap-2 border-b border-surface-border/50 pb-1.5">
              <div>
                <p className="text-ink-900">{e.title}</p>
                {e.description ? <p className="text-xs text-ink-500">{e.description}</p> : null}
                {e.source_url ? (
                  <a href={e.source_url} target="_blank" rel="noreferrer" className="text-xs text-accent hover:underline">
                    {e.source_url}
                  </a>
                ) : null}
                {e.evidence_type === "document" && e.file_name ? (
                  <a
                    href={`${API_BASE_URL}/api/evidence/${e.id}/file`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-accent hover:underline"
                  >
                    {e.file_name}
                    {e.file_size_bytes !== null ? ` (${formatFileSize(e.file_size_bytes)})` : ""}
                  </a>
                ) : null}
                <p className="text-xs text-ink-500">
                  {e.evidence_type} · collected {new Date(e.collected_at).toLocaleDateString()}
                </p>
              </div>
              {canManage ? (
                <Button size="sm" variant="ghost" isLoading={isBusy} onClick={() => deleteEvidence(e.id)}>
                  Remove
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-500">No evidence recorded yet.</p>
      )}

      {canManage ? (
        <div className="flex flex-col gap-2 rounded border border-surface-border p-3">
          <input
            type="text"
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="h-9 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="h-9 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          />
          <div className="flex gap-2">
            <select
              value={evidenceType}
              onChange={(e) => setEvidenceType(e.target.value)}
              className="h-9 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
            >
              {EVIDENCE_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
            {evidenceType === "url" ? (
              <input
                type="text"
                placeholder="https://…"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                className="h-9 flex-1 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
              />
            ) : null}
            {evidenceType === "document" ? (
              <input
                ref={fileInputRef}
                type="file"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="h-9 flex-1 rounded border border-surface-border bg-surface-800 px-3 py-1.5 text-sm text-ink-900"
              />
            ) : null}
          </div>
          <Button
            size="sm"
            disabled={
              !title.trim() ||
              (evidenceType === "url" && !sourceUrl.trim()) ||
              (evidenceType === "document" && !file)
            }
            isLoading={isBusy}
            onClick={addEvidence}
          >
            Add evidence
          </Button>
        </div>
      ) : null}
    </div>
  );
}
