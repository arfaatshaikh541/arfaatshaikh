"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";

type Dashboard = {
  source_count: number;
  edition_count: number;
  retrieval_eligible_count: number;
  pending_review_count: number;
  open_correction_count: number;
};

export function SourceRegistryPanel() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [message, setMessage] = useState("Loading registry status…");

  useEffect(() => {
    void apiFetch<Dashboard>("/sources/admin/dashboard")
      .then((result) => { setData(result); setMessage(""); })
      .catch((error: unknown) => {
        setMessage(error instanceof ApiError && error.status === 403
          ? "Platform administrator access is required to view registry administration metrics."
          : "Registry metrics could not be loaded.");
      });
  }, []);

  if (!data) return <p role="status">{message}</p>;
  return <div className="metric-grid" aria-label="Source registry metrics">
    <article><strong>{data.source_count}</strong><span>Registered sources</span></article>
    <article><strong>{data.edition_count}</strong><span>Registered editions</span></article>
    <article><strong>{data.retrieval_eligible_count}</strong><span>Retrieval eligible</span></article>
    <article><strong>{data.pending_review_count}</strong><span>Open reviews</span></article>
    <article><strong>{data.open_correction_count}</strong><span>Open corrections</span></article>
  </div>;
}
