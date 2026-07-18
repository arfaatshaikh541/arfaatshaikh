"use client";

import { Banner, Button, Card, TextField } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ApiError, api } from "@/lib/api";
import {
  LEAD_STATUSES,
  type ExportFormat,
  type ExportRecord,
  type LeadListResponse,
  type SavedView,
} from "@/lib/types";

const PAGE_SIZE = 25;

const STATUS_STYLES: Record<string, string> = {
  new: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  reviewed: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300",
  qualified: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  unqualified: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  assigned: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300",
  contacted: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  interested: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  converted: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  do_not_contact: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  archived: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
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

type FilterState = {
  search: string;
  status: string;
  tag: string;
  category: string;
  city: string;
  minScore: string;
  maxScore: string;
  sortBy: string;
  sortDir: string;
};

const DEFAULT_FILTERS: FilterState = {
  search: "",
  status: "",
  tag: "",
  category: "",
  city: "",
  minScore: "",
  maxScore: "",
  sortBy: "created_at",
  sortDir: "desc",
};

function buildQuery(filters: FilterState, page: number): string {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.status) params.set("status", filters.status);
  if (filters.tag) params.set("tag", filters.tag);
  if (filters.category) params.set("category", filters.category);
  if (filters.city) params.set("city", filters.city);
  if (filters.minScore) params.set("min_score", filters.minScore);
  if (filters.maxScore) params.set("max_score", filters.maxScore);
  params.set("sort_by", filters.sortBy);
  params.set("sort_dir", filters.sortDir);
  params.set("page", String(page));
  params.set("page_size", String(PAGE_SIZE));
  return params.toString();
}

function toExportFilters(filters: FilterState) {
  return {
    status: filters.status ? [filters.status] : undefined,
    tag: filters.tag || undefined,
    category: filters.category || undefined,
    city: filters.city || undefined,
    min_score: filters.minScore ? Number(filters.minScore) : undefined,
    max_score: filters.maxScore ? Number(filters.maxScore) : undefined,
    search: filters.search || undefined,
    sort_by: filters.sortBy,
    sort_dir: filters.sortDir,
  };
}

export default function LeadsPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [actionError, setActionError] = useState<string | null>(null);
  const [bulkStatus, setBulkStatus] = useState("");
  const [bulkTag, setBulkTag] = useState("");
  const [newViewName, setNewViewName] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("xlsx");
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  const queryString = useMemo(() => buildQuery(filters, page), [filters, page]);

  const leadsQuery = useQuery<LeadListResponse>({
    queryKey: ["leads", queryString],
    queryFn: () => api.get<LeadListResponse>(`/leads?${queryString}`),
  });

  const savedViewsQuery = useQuery<SavedView[]>({
    queryKey: ["saved-views"],
    queryFn: () => api.get<SavedView[]>("/saved-views"),
    enabled: !leadsQuery.isError,
  });

  const items = leadsQuery.data?.items ?? [];
  const total = leadsQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const updateFilter = <K extends keyof FilterState>(key: K, value: FilterState[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const toggleSelected = (leadId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(leadId)) next.delete(leadId);
      else next.add(leadId);
      return next;
    });
  };

  const toggleSelectAll = () => {
    setSelected((prev) => (prev.size === items.length ? new Set() : new Set(items.map((i) => i.lead_id))));
  };

  const refreshLeads = () => queryClient.invalidateQueries({ queryKey: ["leads"] });

  const runBulkAction = async (action: string, fn: () => Promise<unknown>) => {
    setActionError(null);
    setPending(action);
    try {
      await fn();
      setSelected(new Set());
      refreshLeads();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : `Could not ${action}.`);
    } finally {
      setPending(null);
    }
  };

  const handleBulkStatus = () => {
    if (!bulkStatus) return;
    runBulkAction("change status", () =>
      api.post("/leads/bulk/status", { lead_ids: Array.from(selected), status: bulkStatus }),
    );
  };

  const handleBulkTag = () => {
    if (!bulkTag.trim()) return;
    runBulkAction("add tag", () =>
      api.post("/leads/bulk/tags", { lead_ids: Array.from(selected), tag: bulkTag.trim() }),
    );
    setBulkTag("");
  };

  const handleExportSelected = async () => {
    setActionError(null);
    setExportNotice(null);
    setPending("export selected");
    try {
      await api.post<ExportRecord>("/exports", {
        format: exportFormat,
        lead_ids: Array.from(selected),
      });
      setExportNotice(`Export of ${selected.size} lead(s) started.`);
      setSelected(new Set());
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not start export.");
    } finally {
      setPending(null);
    }
  };

  const handleExportAllMatching = async () => {
    setActionError(null);
    setExportNotice(null);
    setPending("export all");
    try {
      await api.post<ExportRecord>("/exports", {
        format: exportFormat,
        filters: toExportFilters(filters),
      });
      setExportNotice("Export of all leads matching your current filters started.");
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not start export.");
    } finally {
      setPending(null);
    }
  };

  const applySavedView = (view: SavedView) => {
    const f = view.filters as Partial<Record<keyof FilterState, string>>;
    setFilters({
      search: f.search ?? "",
      status: f.status ?? "",
      tag: f.tag ?? "",
      category: f.category ?? "",
      city: f.city ?? "",
      minScore: f.minScore ?? "",
      maxScore: f.maxScore ?? "",
      sortBy: f.sortBy ?? "created_at",
      sortDir: f.sortDir ?? "desc",
    });
    setPage(1);
  };

  const handleSaveView = async () => {
    if (!newViewName.trim()) return;
    setActionError(null);
    try {
      await api.post("/saved-views", { name: newViewName.trim(), filters });
      setNewViewName("");
      queryClient.invalidateQueries({ queryKey: ["saved-views"] });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not save this view.");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Leads</h1>
      </div>

      {leadsQuery.isError && <Banner tone="info">You don&apos;t have permission to view leads.</Banner>}
      {actionError && <Banner tone="error">{actionError}</Banner>}
      {exportNotice && (
        <Banner tone="success">
          {exportNotice}{" "}
          <Link href="/exports" className="underline">
            View exports
          </Link>
          .
        </Banner>
      )}

      {!leadsQuery.isError && (
        <>
          <Card>
            <div className="flex flex-wrap items-end gap-3">
              <TextField
                label="Search"
                value={filters.search}
                onChange={(e) => updateFilter("search", e.target.value)}
                placeholder="Business name"
              />
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                  Status
                </label>
                <select
                  value={filters.status}
                  onChange={(e) => updateFilter("status", e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="">Any status</option>
                  {LEAD_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>
              <TextField
                label="Tag"
                value={filters.tag}
                onChange={(e) => updateFilter("tag", e.target.value)}
              />
              <TextField
                label="Category"
                value={filters.category}
                onChange={(e) => updateFilter("category", e.target.value)}
              />
              <TextField
                label="City"
                value={filters.city}
                onChange={(e) => updateFilter("city", e.target.value)}
              />
              <TextField
                label="Min score"
                type="number"
                min="0"
                max="100"
                value={filters.minScore}
                onChange={(e) => updateFilter("minScore", e.target.value)}
              />
              <TextField
                label="Max score"
                type="number"
                min="0"
                max="100"
                value={filters.maxScore}
                onChange={(e) => updateFilter("maxScore", e.target.value)}
              />
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                  Sort by
                </label>
                <select
                  value={filters.sortBy}
                  onChange={(e) => updateFilter("sortBy", e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="created_at">Created</option>
                  <option value="name">Name</option>
                  <option value="score">Score</option>
                  <option value="status">Status</option>
                  <option value="rating">Rating</option>
                  <option value="review_count">Review count</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                  Direction
                </label>
                <select
                  value={filters.sortDir}
                  onChange={(e) => updateFilter("sortDir", e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="desc">Descending</option>
                  <option value="asc">Ascending</option>
                </select>
              </div>
              <Button variant="ghost" onClick={() => setFilters(DEFAULT_FILTERS)}>
                Clear filters
              </Button>
            </div>

            <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-slate-200 pt-4 dark:border-slate-800">
              {savedViewsQuery.data && savedViewsQuery.data.length > 0 && (
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                    Saved views
                  </label>
                  <select
                    defaultValue=""
                    onChange={(e) => {
                      const view = savedViewsQuery.data?.find((v) => v.id === e.target.value);
                      if (view) applySavedView(view);
                    }}
                    className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  >
                    <option value="" disabled>
                      Apply a saved view…
                    </option>
                    {savedViewsQuery.data.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <TextField
                label="Save current filters as"
                value={newViewName}
                onChange={(e) => setNewViewName(e.target.value)}
                placeholder="View name"
              />
              <Button variant="secondary" onClick={handleSaveView} disabled={!newViewName.trim()}>
                Save view
              </Button>
            </div>

            <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-slate-200 pt-4 dark:border-slate-800">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                  Export format
                </label>
                <select
                  value={exportFormat}
                  onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="xlsx">XLSX</option>
                  <option value="csv">CSV</option>
                </select>
              </div>
              <Button
                variant="secondary"
                isLoading={pending === "export all"}
                onClick={handleExportAllMatching}
              >
                Export all matching filters
              </Button>
            </div>
          </Card>

          {selected.size > 0 && (
            <Card>
              <div className="flex flex-wrap items-end gap-3">
                <p className="self-center text-sm font-medium">{selected.size} selected</p>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                    Change status
                  </label>
                  <div className="flex gap-2">
                    <select
                      value={bulkStatus}
                      onChange={(e) => setBulkStatus(e.target.value)}
                      className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                    >
                      <option value="">Select…</option>
                      {LEAD_STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {s.replace(/_/g, " ")}
                        </option>
                      ))}
                    </select>
                    <Button
                      variant="secondary"
                      isLoading={pending === "change status"}
                      disabled={!bulkStatus}
                      onClick={handleBulkStatus}
                    >
                      Apply
                    </Button>
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                    Add tag
                  </label>
                  <div className="flex gap-2">
                    <input
                      value={bulkTag}
                      onChange={(e) => setBulkTag(e.target.value)}
                      className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                      placeholder="tag name"
                    />
                    <Button
                      variant="secondary"
                      isLoading={pending === "add tag"}
                      disabled={!bulkTag.trim()}
                      onClick={handleBulkTag}
                    >
                      Apply
                    </Button>
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">
                    Export
                  </label>
                  <Button
                    variant="secondary"
                    isLoading={pending === "export selected"}
                    onClick={handleExportSelected}
                  >
                    Export selected ({exportFormat.toUpperCase()})
                  </Button>
                </div>
              </div>
            </Card>
          )}

          <Card>
            {items.length > 0 ? (
              <>
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
                      <th className="w-8 py-2">
                        <input
                          type="checkbox"
                          aria-label="Select all on page"
                          checked={items.length > 0 && selected.size === items.length}
                          onChange={toggleSelectAll}
                          className="h-4 w-4 rounded border-slate-300"
                        />
                      </th>
                      <th className="py-2 font-medium">Business</th>
                      <th className="py-2 font-medium">Category</th>
                      <th className="py-2 font-medium">City</th>
                      <th className="py-2 font-medium">Status</th>
                      <th className="py-2 font-medium">Score</th>
                      <th className="py-2 font-medium">Tags</th>
                      <th className="py-2 font-medium">Assigned</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {items.map((item) => (
                      <tr key={item.lead_id}>
                        <td className="py-2">
                          <input
                            type="checkbox"
                            aria-label={`Select ${item.business_name}`}
                            checked={selected.has(item.lead_id)}
                            onChange={() => toggleSelected(item.lead_id)}
                            className="h-4 w-4 rounded border-slate-300"
                          />
                        </td>
                        <td className="py-2">
                          <Link
                            href={`/leads/${item.lead_id}`}
                            className="font-medium text-brand-700 hover:underline dark:text-brand-400"
                          >
                            {item.business_name}
                          </Link>
                        </td>
                        <td className="py-2 text-slate-500 dark:text-slate-400">{item.category ?? "—"}</td>
                        <td className="py-2 text-slate-500 dark:text-slate-400">{item.city ?? "—"}</td>
                        <td className="py-2">
                          <StatusBadge status={item.status} />
                        </td>
                        <td className="py-2 text-slate-500 dark:text-slate-400">
                          {item.score !== null ? item.score.toFixed(0) : "—"}
                        </td>
                        <td className="py-2">
                          <div className="flex flex-wrap gap-1">
                            {item.tags.map((tag) => (
                              <span
                                key={tag}
                                className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="py-2 text-slate-500 dark:text-slate-400">
                          {item.assigned_to_user_id ? "Assigned" : "Unassigned"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-4 flex items-center justify-between text-sm">
                  <p className="text-slate-500 dark:text-slate-400">
                    Page {page} of {totalPages} ({total} lead{total === 1 ? "" : "s"})
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                No leads yet. Leads appear here once a campaign has discovered businesses and they&apos;ve
                been scored.
              </p>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
