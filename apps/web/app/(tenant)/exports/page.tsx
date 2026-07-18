"use client";

import { Banner, Button, Card } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "@/lib/api";
import type { ExportDownload, ExportListResponse, ExportRecord } from "@/lib/types";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  processing: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  completed: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
        STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
      }`}
    >
      {status}
    </span>
  );
}

function formatSize(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function DownloadButton({ exportRecord }: { exportRecord: ExportRecord }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async () => {
    setPending(true);
    setError(null);
    try {
      const download = await api.get<ExportDownload>(`/exports/${exportRecord.id}/download`);
      // The API returns a short-lived, freshly-signed object-storage URL
      // (not proxied through this app) - navigating to it directly is the
      // correct way to hand the browser the file.
      window.location.href = download.url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not get a download link.");
    } finally {
      setPending(false);
    }
  };

  if (exportRecord.status !== "completed") return null;

  return (
    <div>
      <Button variant="secondary" isLoading={pending} onClick={handleDownload}>
        Download
      </Button>
      {error && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}

export default function ExportsPage() {
  const exportsQuery = useQuery<ExportListResponse>({
    queryKey: ["exports"],
    queryFn: () => api.get<ExportListResponse>("/exports"),
    // Poll while anything is still pending/processing, so status/download
    // availability update without a manual refresh - the same job-status
    // pattern the Campaigns list would use if it polled today.
    refetchInterval: (query) => {
      const exports = query.state.data?.exports ?? [];
      const hasActiveJob = exports.some((e) => e.status === "pending" || e.status === "processing");
      return hasActiveJob ? 3000 : false;
    },
  });

  const items = exportsQuery.data?.exports ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Exports</h1>
      </div>

      {exportsQuery.isError && (
        <Banner tone="info">You don&apos;t have permission to view exports.</Banner>
      )}

      {!exportsQuery.isError && (
        <Card>
          {items.length > 0 ? (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
                  <th className="py-2 font-medium">Requested</th>
                  <th className="py-2 font-medium">Format</th>
                  <th className="py-2 font-medium">Status</th>
                  <th className="py-2 font-medium">Rows</th>
                  <th className="py-2 font-medium">Errors</th>
                  <th className="py-2 font-medium">Size</th>
                  <th className="py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {items.map((exportRecord) => (
                  <tr key={exportRecord.id}>
                    <td className="py-2 text-slate-500 dark:text-slate-400">
                      {new Date(exportRecord.created_at).toLocaleString()}
                    </td>
                    <td className="py-2 uppercase">{exportRecord.format}</td>
                    <td className="py-2">
                      <StatusBadge status={exportRecord.status} />
                      {exportRecord.status === "failed" && exportRecord.error_message && (
                        <p className="mt-1 max-w-xs text-xs text-red-600 dark:text-red-400">
                          {exportRecord.error_message}
                        </p>
                      )}
                    </td>
                    <td className="py-2 text-slate-500 dark:text-slate-400">
                      {exportRecord.row_count ?? "—"}
                    </td>
                    <td className="py-2 text-slate-500 dark:text-slate-400">
                      {exportRecord.error_count > 0 ? exportRecord.error_count : "—"}
                    </td>
                    <td className="py-2 text-slate-500 dark:text-slate-400">
                      {formatSize(exportRecord.file_size_bytes)}
                    </td>
                    <td className="py-2">
                      <DownloadButton exportRecord={exportRecord} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              No exports yet. Select leads on the Leads page and choose &quot;Export&quot;, or
              export everything matching your current filters.
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
