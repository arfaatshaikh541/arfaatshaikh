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

type ReviewerQueueItem = {
  assignment_id: string;
  edition_id: string;
  source_title: string;
  edition_key: string;
  review_domain: string;
  status: string;
  due_at: string | null;
};

export function SourceRegistryPanel() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [message, setMessage] = useState("Loading registry status…");
  const [queue, setQueue] = useState<ReviewerQueueItem[] | null>(null);
  const [queueMessage, setQueueMessage] = useState("Loading your reviewer queue…");

  useEffect(() => {
    void apiFetch<Dashboard>("/sources/admin/dashboard")
      .then((result) => { setData(result); setMessage(""); })
      .catch((error: unknown) => {
        setMessage(error instanceof ApiError && error.status === 403
          ? "Platform administrator access is required to view registry administration metrics."
          : "Registry metrics could not be loaded.");
      });
    void apiFetch<ReviewerQueueItem[]>("/sources/reviewer/queue")
      .then((result) => { setQueue(result); setQueueMessage(""); })
      .catch(() => setQueueMessage("Your reviewer queue could not be loaded."));
  }, []);

  return <>
    {!data ? <p role="status">{message}</p> : <div className="metric-grid" aria-label="Source registry metrics">
      <article><strong>{data.source_count}</strong><span>Registered sources</span></article>
      <article><strong>{data.edition_count}</strong><span>Registered editions</span></article>
      <article><strong>{data.retrieval_eligible_count}</strong><span>Retrieval eligible</span></article>
      <article><strong>{data.pending_review_count}</strong><span>Open reviews</span></article>
      <article><strong>{data.open_correction_count}</strong><span>Open corrections</span></article>
    </div>}
    <section aria-labelledby="reviewer-queue-heading" style={{ marginTop: "2.5rem" }}>
      <h2 id="reviewer-queue-heading">Your reviewer queue</h2>
      {queue === null ? (
        <p role="status">{queueMessage}</p>
      ) : queue.length === 0 ? (
        <p className="tool-note">No reviews are currently assigned to your account.</p>
      ) : (
        <ul className="feature-list">
          {queue.map((item) => (
            <li key={item.assignment_id} className="feature-item">
              <div className="feature-list-head">
                <h3>{item.source_title} — {item.edition_key}</h3>
                <span className={`status-pill status-${item.status === "pending" ? "planned" : "available"}`}>{item.status}</span>
              </div>
              <p>{item.review_domain}{item.due_at ? ` · due ${new Date(item.due_at).toLocaleDateString()}` : ""}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  </>;
}
