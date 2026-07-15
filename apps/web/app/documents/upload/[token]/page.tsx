"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Card, CardHeader } from "@/components/ui/card";
import { api } from "@/lib/api-client";
import type { PublicDocumentRequest } from "@/lib/types";

export default function PublicDocumentUploadPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState(false);

  const requestQuery = useQuery({
    queryKey: ["public", "document-request", token],
    queryFn: () => api.get<PublicDocumentRequest>(`/public/documents/${token}`),
  });

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api"}/public/documents/${token}/upload`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message ?? "Upload failed.");
      }
      setUploaded(true);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  if (requestQuery.isLoading) {
    return <div className="flex min-h-screen items-center justify-center text-ink-muted">Loading…</div>;
  }
  if (requestQuery.isError || !requestQuery.data) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Alert tone="error">This upload link could not be found.</Alert>
      </div>
    );
  }

  const request = requestQuery.data;

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4 py-12">
      <div className="w-full max-w-md">
        <h1 className="text-xl font-semibold text-ink">{request.title}</h1>
        {request.description && <p className="mt-1 text-sm text-ink-muted">{request.description}</p>}

        <Card className="mt-6">
          {uploaded ? (
            <Alert tone="success">Thank you — your file has been received.</Alert>
          ) : (
            <div className="space-y-4">
              <CardHeader title="Upload your file" description="PDF, Word, Excel, or image files, up to 20MB." />
              {uploadError && <Alert tone="error">{uploadError}</Alert>}
              <input type="file" onChange={handleUpload} disabled={uploading} className="text-sm text-ink-muted" />
              {uploading && <p className="text-sm text-ink-faint">Uploading…</p>}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
