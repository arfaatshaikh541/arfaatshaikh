"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api, getCsrfToken } from "@/lib/api-client";
import type { DocumentItem, DocumentRequestItem, DocumentRequestStatus } from "@/lib/types";

const STATUS_TONE: Record<DocumentRequestStatus, string> = {
  requested: "text-accent",
  uploaded: "text-amber-400",
  approved: "text-emerald-400",
  rejected: "text-red-400",
};

export default function DocumentRequestDetailPage({ params }: { params: Promise<{ requestId: string }> }) {
  const { requestId } = use(params);
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");

  const requestQuery = useQuery({
    queryKey: ["document-request", requestId],
    queryFn: () => api.get<DocumentRequestItem>(`/tenant/document-requests/${requestId}`),
  });
  const documentsQuery = useQuery({
    queryKey: ["document-request", requestId, "documents"],
    queryFn: () => api.get<DocumentItem[]>(`/tenant/document-requests/${requestId}/documents`),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["document-request", requestId] });
  };

  const approveMutation = useMutation({
    mutationFn: () => api.post(`/tenant/document-requests/${requestId}/approve`, { notes: reviewNotes }),
    onSuccess: invalidate,
  });
  const rejectMutation = useMutation({
    mutationFn: () => api.post(`/tenant/document-requests/${requestId}/reject`, { notes: reviewNotes }),
    onSuccess: invalidate,
  });

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const csrfToken = getCsrfToken();
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api"}/tenant/document-requests/${requestId}/documents`, {
        method: "POST",
        credentials: "include",
        headers: csrfToken ? { "X-CSRF-Token": csrfToken } : undefined,
        body: formData,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message ?? "Upload failed.");
      }
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["document-request", requestId, "documents"] });
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function handleDownload(documentId: string) {
    const { url } = await api.get<{ url: string }>(`/tenant/document-requests/${requestId}/documents/${documentId}/download-url`);
    window.open(url, "_blank", "noopener,noreferrer");
  }

  const request = requestQuery.data;
  if (requestQuery.isLoading || !request) return <p className="text-sm text-ink-muted">Loading…</p>;

  const publicUrl = request.public_token
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/documents/upload/${request.public_token}`
    : null;
  const canReview = request.status === "uploaded";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">{request.title}</h1>
        <p className={`mt-1 text-sm font-medium capitalize ${STATUS_TONE[request.status]}`}>{request.status}</p>
        {request.description && <p className="mt-1 text-sm text-ink-muted">{request.description}</p>}
      </div>

      {publicUrl && (
        <Card>
          <CardHeader title="Client link" description="Share this link so the client can upload directly." />
          <Input readOnly value={publicUrl} onFocus={(e) => e.currentTarget.select()} />
        </Card>
      )}

      {request.status === "approved" && (
        <Alert tone="success">Approved{request.review_notes ? `: ${request.review_notes}` : "."}</Alert>
      )}
      {request.status === "rejected" && (
        <Alert tone="error">Rejected{request.review_notes ? `: ${request.review_notes}` : "."}</Alert>
      )}

      <Card>
        <CardHeader title="Uploads" />
        <div className="space-y-3">
          <input type="file" onChange={handleUpload} disabled={uploading} className="text-sm text-ink-muted" />
          {uploadError && <Alert tone="error">{uploadError}</Alert>}
          {documentsQuery.data?.map((document) => (
            <div key={document.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
              <div>
                <span className="text-ink">{document.file_name}</span>
                <span className="ml-2 text-xs text-ink-faint">
                  {(document.size_bytes / 1024).toFixed(1)} KB {document.uploaded_by ? "" : "· uploaded by client"}
                </span>
              </div>
              <Button variant="secondary" onClick={() => handleDownload(document.id)}>
                Download
              </Button>
            </div>
          ))}
          {documentsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No files uploaded yet.</p>}
        </div>
      </Card>

      {canReview && (
        <Card>
          <CardHeader title="Review" />
          <div className="space-y-4">
            <div>
              <Label htmlFor="review-notes">Notes (optional)</Label>
              <Input id="review-notes" value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)} />
            </div>
            <div className="flex gap-3">
              <Button onClick={() => approveMutation.mutate()} disabled={approveMutation.isPending}>
                {approveMutation.isPending ? "Approving…" : "Approve"}
              </Button>
              <Button variant="secondary" onClick={() => rejectMutation.mutate()} disabled={rejectMutation.isPending}>
                {rejectMutation.isPending ? "Rejecting…" : "Reject"}
              </Button>
            </div>
            {(approveMutation.isError || rejectMutation.isError) && (
              <Alert tone="error">
                {(approveMutation.error ?? rejectMutation.error) instanceof ApiError
                  ? (approveMutation.error ?? rejectMutation.error)!.message
                  : "Unable to submit review."}
              </Alert>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
