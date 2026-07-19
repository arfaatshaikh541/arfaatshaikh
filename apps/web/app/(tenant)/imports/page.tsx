"use client";

import { Banner, Button, Card } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { ApiError, api, uploadFile } from "@/lib/api";
import type {
  CsvImportErrorListResponse,
  CsvImportListResponse,
  CsvImportPreview,
  CsvImportRecord,
} from "@/lib/types";

const STATUS_STYLES: Record<string, string> = {
  mapping_required: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  queued: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
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
      {status.replace(/_/g, " ")}
    </span>
  );
}

function ImportErrors({ csvImportId }: { csvImportId: string }) {
  const errorsQuery = useQuery<CsvImportErrorListResponse>({
    queryKey: ["csv-import-errors", csvImportId],
    queryFn: () => api.get<CsvImportErrorListResponse>(`/imports/${csvImportId}/errors`),
  });
  const errors = errorsQuery.data?.errors ?? [];
  if (errors.length === 0) return null;
  return (
    <ul className="mt-2 flex flex-col gap-1 text-xs text-red-600 dark:text-red-400">
      {errors.map((e) => (
        <li key={e.row_number}>
          Row {e.row_number}: {e.message}
        </li>
      ))}
    </ul>
  );
}

function ImportRow({ record }: { record: CsvImportRecord }) {
  const [showErrors, setShowErrors] = useState(false);
  return (
    <li className="rounded-md bg-slate-50 p-3 dark:bg-slate-800/50">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium">{record.original_filename}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {new Date(record.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={record.status} />
          <span className="text-sm text-slate-500 dark:text-slate-400">
            {record.imported_count}/{record.row_count} imported
            {record.error_count > 0 ? `, ${record.error_count} error(s)` : ""}
          </span>
          {record.error_count > 0 && (
            <Button variant="ghost" onClick={() => setShowErrors((v) => !v)}>
              {showErrors ? "Hide errors" : "Show errors"}
            </Button>
          )}
        </div>
      </div>
      {record.error_message && (
        <p className="mt-2 text-sm text-red-600 dark:text-red-400">{record.error_message}</p>
      )}
      {showErrors && <ImportErrors csvImportId={record.id} />}
    </li>
  );
}

export default function ImportsPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [preview, setPreview] = useState<CsvImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const importsQuery = useQuery<CsvImportListResponse>({
    queryKey: ["csv-imports"],
    queryFn: () => api.get<CsvImportListResponse>("/imports"),
    refetchInterval: (query) => {
      const imports = query.state.data?.imports ?? [];
      const hasActiveJob = imports.some((i) => i.status === "queued" || i.status === "processing");
      return hasActiveJob ? 3000 : false;
    },
  });

  const handleFileSelected = async (file: File) => {
    setUploadError(null);
    setUploading(true);
    try {
      const result = await uploadFile<CsvImportPreview>("/imports", file);
      setPreview(result);
      setMapping({ name: result.detected_headers[0] ?? "" });
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Could not upload this file.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleStart = async () => {
    if (!preview || !mapping.name) return;
    setStartError(null);
    setStarting(true);
    try {
      const cleanMapping = Object.fromEntries(
        Object.entries(mapping).filter(([, header]) => header),
      );
      await api.post(`/imports/${preview.id}/start`, { column_mapping: cleanMapping });
      setPreview(null);
      setMapping({});
      queryClient.invalidateQueries({ queryKey: ["csv-imports"] });
    } catch (err) {
      setStartError(err instanceof ApiError ? err.message : "Could not start this import.");
    } finally {
      setStarting(false);
    }
  };

  const imports = importsQuery.data?.imports ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Imports</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Import businesses from a CSV file - each row is deduplicated against your existing data
          the same way a campaign&apos;s discovered businesses are.
        </p>
      </div>

      {importsQuery.isError && (
        <Banner tone="info">You don&apos;t have permission to view imports.</Banner>
      )}
      {uploadError && <Banner tone="error">{uploadError}</Banner>}

      {!importsQuery.isError && (
        <>
          {!preview && (
            <Card>
              <h2 className="text-lg font-medium">Upload a CSV file</h2>
              <div className="mt-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,text/csv"
                  disabled={uploading}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void handleFileSelected(file);
                  }}
                  className="text-sm"
                />
              </div>
            </Card>
          )}

          {preview && (
            <Card>
              <h2 className="text-lg font-medium">Map columns for {preview.original_filename}</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {preview.row_count} row(s) detected. &quot;Business name&quot; is required; leave any
                other field unmapped to skip it.
              </p>
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {preview.mappable_fields.map((field) => (
                  <div key={field}>
                    <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                      {field.replace(/_/g, " ")}
                      {field === "name" ? " *" : ""}
                    </label>
                    <select
                      value={mapping[field] ?? ""}
                      onChange={(e) =>
                        setMapping((prev) => ({ ...prev, [field]: e.target.value }))
                      }
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                    >
                      <option value="">Not mapped</option>
                      {preview.detected_headers.map((header) => (
                        <option key={header} value={header}>
                          {header}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>

              {preview.sample_rows.length > 0 && (
                <div className="mt-4 overflow-x-auto border-t border-slate-200 pt-3 dark:border-slate-800">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="text-slate-500 dark:text-slate-400">
                        {preview.detected_headers.map((h) => (
                          <th key={h} className="py-1 pr-4 font-medium">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.sample_rows.map((row, i) => (
                        <tr key={i} className="text-slate-600 dark:text-slate-300">
                          {preview.detected_headers.map((h) => (
                            <td key={h} className="py-1 pr-4">
                              {row[h] ?? ""}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {startError && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{startError}</p>}
              <div className="mt-4 flex gap-2">
                <Button isLoading={starting} disabled={!mapping.name} onClick={handleStart}>
                  Start import
                </Button>
                <Button variant="ghost" onClick={() => setPreview(null)}>
                  Cancel
                </Button>
              </div>
            </Card>
          )}

          <Card>
            <h2 className="text-lg font-medium">History</h2>
            {imports.length > 0 ? (
              <ul className="mt-3 flex flex-col gap-2">
                {imports.map((record) => (
                  <ImportRow key={record.id} record={record} />
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">No imports yet.</p>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
