"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type EnterpriseMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface Workload {
  id: string;
  name: string;
}

interface WorkloadVersion {
  id: string;
  version: number;
  status: string;
}

interface CapacityOffer {
  id: string;
  operator_id: string;
  region_id: string;
  accelerator_type: string;
  available_capacity: number;
  price_per_unit_hour: number;
  currency: string;
  confidential_computing_available: boolean;
  degraded: boolean;
}

interface BilateralAgreement {
  id: string;
  operator_id: string;
  status: string;
  currency: string;
  platform_fee_rate: number;
}

interface PlacementEvaluation {
  id: string;
  capacity_offer_id: string;
  operator_id: string;
  accelerator_type: string;
  decision: string;
  rank?: number;
  estimated_cost: number;
  estimated_energy_kwh: number;
  reason_codes: string[];
  explanation: Record<string, unknown>;
}

interface Reservation {
  id: string;
  capacity_offer_id: string;
  quantity: number;
  price_per_unit_hour: number;
  estimated_cost: number;
  status: string;
  approval_required: boolean;
  requested_by: string;
  held_at: string;
  expires_at: string;
}

interface PlacementRequest {
  id: string;
  workload_version_id: string;
  quantity: number;
  simulate: boolean;
  status: string;
}

interface EvaluatePlacementResult {
  request: PlacementRequest;
  evaluations: PlacementEvaluation[];
  reservation?: Reservation;
}

// Roles known (from docs/security/permission-matrix.md) to hold the
// server-side reservations.* permission each action requires -- a UX
// convenience only, re-checked independently by control-api on every
// request.
const CAN_RESERVE = new Set(["enterprise_owner", "enterprise_admin", "ai_platform_engineer", "devops_engineer", "finops_manager"]);
const CAN_APPROVE = new Set(["enterprise_owner", "enterprise_admin", "security_administrator", "compliance_manager"]);
const CAN_CANCEL = new Set(["enterprise_owner", "enterprise_admin", "ai_platform_engineer", "devops_engineer", "finops_manager"]);

export default function PlacementPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["tenant-members", tenantId],
    queryFn: () => api.get<EnterpriseMembership[]>(`/api/v1/enterprises/${tenantId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const canReserve = CAN_RESERVE.has(myRole);
  const canApprove = CAN_APPROVE.has(myRole);
  const canCancel = CAN_CANCEL.has(myRole);

  const offers = useQuery({
    queryKey: ["placement-capacity-offers", tenantId],
    queryFn: () => api.get<CapacityOffer[]>(`/api/v1/enterprises/${tenantId}/capacity-offers`),
  });
  const reservations = useQuery({
    queryKey: ["placement-reservations", tenantId],
    queryFn: () => api.get<Reservation[]>(`/api/v1/enterprises/${tenantId}/capacity-reservations`),
  });
  const agreements = useQuery({
    queryKey: ["placement-bilateral-agreements", tenantId],
    queryFn: () => api.get<BilateralAgreement[]>(`/api/v1/enterprises/${tenantId}/bilateral-agreements`),
  });

  const invalidateReservations = () => queryClient.invalidateQueries({ queryKey: ["placement-reservations", tenantId] });
  const invalidateOffers = () => queryClient.invalidateQueries({ queryKey: ["placement-capacity-offers", tenantId] });

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not have access to this tenant&apos;s capacity and placement.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 p-8">
      <Link href={`/dashboard/enterprise/${tenantId}`} className="text-sm underline">&larr; Tenant overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Capacity &amp; placement</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Every placement decision below is explainable -- ranking is a plain, auditable sort by
        cost (never an AI/ML decision), and every rejected candidate carries reason codes,
        including real sovereignty-policy evaluations against the published policy engine. A
        private offer only appears below once an operator has granted your tenant access to it,
        sometimes at a price specific to your own bilateral agreement; a degraded offer stays out
        of eligible rankings until its operator clears it.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Available capacity (marketplace)</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {offers.data?.map((o) => (
            <li key={o.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
              <div className="flex items-center justify-between">
                <span>{o.accelerator_type}</span>
                <span className="flex items-center gap-2">
                  {o.degraded && <span className="rounded bg-red-100 px-2 py-0.5 text-xs text-red-900 dark:bg-red-900 dark:text-red-100">degraded</span>}
                  <span className="text-zinc-500">{o.available_capacity} available</span>
                </span>
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                ${o.price_per_unit_hour}/unit/hr &middot; {o.confidential_computing_available ? "confidential computing" : "no confidential computing"}
              </p>
            </li>
          ))}
          {offers.data?.length === 0 && <li className="text-zinc-500">No capacity offers visible yet.</li>}
        </ul>
      </section>

      {(agreements.data?.length ?? 0) > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Bilateral agreements</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {agreements.data?.map((a) => (
              <li key={a.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <span>operator {a.operator_id.slice(0, 8)}&hellip; &middot; {a.currency} &middot; {(a.platform_fee_rate * 100).toFixed(1)}% platform fee</span>
                  <span className={a.status === "active" ? "text-emerald-600" : "text-zinc-500"}>{a.status}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {canReserve && (
        <EvaluatePlacementForm
          tenantId={tenantId}
          onEvaluated={() => {
            invalidateReservations();
            invalidateOffers();
          }}
        />
      )}

      <section className="mt-8">
        <h2 className="mb-3 text-lg font-medium">Reservations</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {reservations.data?.map((r) => (
            <ReservationRow
              key={r.id}
              tenantId={tenantId}
              reservation={r}
              myUserId={user?.user_id}
              canApprove={canApprove}
              canCancel={canCancel}
              onChanged={() => {
                invalidateReservations();
                invalidateOffers();
              }}
            />
          ))}
          {reservations.data?.length === 0 && <li className="text-zinc-500">No reservations yet.</li>}
        </ul>
      </section>
    </main>
  );
}

function ReservationRow({
  tenantId,
  reservation,
  myUserId,
  canApprove,
  canCancel,
  onChanged,
}: {
  tenantId: string;
  reservation: Reservation;
  myUserId: string | undefined;
  canApprove: boolean;
  canCancel: boolean;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  const approveCommit = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/capacity-reservations/${reservation.id}/approve-commit`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to approve reservation.");
    }
  };

  const cancel = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/capacity-reservations/${reservation.id}/cancel`, { reason: "cancelled from dashboard" });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to cancel reservation.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span>{reservation.quantity} unit(s) &middot; ${reservation.estimated_cost.toFixed(2)}</span>
        <span className="text-zinc-500">{reservation.status}</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        Held {new Date(reservation.held_at).toLocaleString()}
        {reservation.status === "held" && ` · expires ${new Date(reservation.expires_at).toLocaleString()}`}
      </p>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="mt-2 flex gap-3">
        {reservation.status === "held" && canApprove && reservation.requested_by !== myUserId && (
          <button onClick={approveCommit} className="text-xs underline">Approve &amp; commit</button>
        )}
        {reservation.status === "held" && reservation.requested_by === myUserId && (
          <span className="text-xs text-zinc-500">Awaiting a different approver</span>
        )}
        {canCancel && (reservation.status === "held" || reservation.status === "committed") && (
          <button onClick={cancel} className="text-xs text-red-600 underline">Cancel</button>
        )}
      </div>
    </li>
  );
}

function EvaluatePlacementForm({ tenantId, onEvaluated }: { tenantId: string; onEvaluated: () => void }) {
  const [workloadId, setWorkloadId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [simulate, setSimulate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvaluatePlacementResult | null>(null);

  const workloads = useQuery({
    queryKey: ["placement-workloads", tenantId],
    queryFn: () => api.get<Workload[]>(`/api/v1/enterprises/${tenantId}/workloads`),
  });
  const versions = useQuery({
    queryKey: ["placement-workload-versions", tenantId, workloadId],
    queryFn: () => api.get<WorkloadVersion[]>(`/api/v1/enterprises/${tenantId}/workloads/${workloadId}/versions`),
    enabled: !!workloadId,
  });
  const publishedVersions = versions.data?.filter((v) => v.status === "published") ?? [];

  const evaluate = async () => {
    setError(null);
    setResult(null);
    try {
      const res = await api.post<EvaluatePlacementResult>(`/api/v1/enterprises/${tenantId}/placement-requests`, {
        workload_version_id: versionId,
        quantity: Number(quantity),
        simulate,
      });
      setResult(res);
      onEvaluated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to evaluate placement.");
    }
  };

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Evaluate &amp; reserve placement</h3>
      <div className="flex flex-col gap-2">
        <select value={workloadId} onChange={(e) => { setWorkloadId(e.target.value); setVersionId(""); }}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Select a workload</option>
          {workloads.data?.map((w) => (
            <option key={w.id} value={w.id}>{w.name}</option>
          ))}
        </select>
        <select value={versionId} onChange={(e) => setVersionId(e.target.value)} disabled={!workloadId}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Select a published version</option>
          {publishedVersions.map((v) => (
            <option key={v.id} value={v.id}>v{v.version}</option>
          ))}
        </select>
        <input placeholder="Quantity" type="number" min={1} value={quantity} onChange={(e) => setQuantity(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={simulate} onChange={(e) => setSimulate(e.target.checked)} />
          Simulate only (do not reserve capacity)
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={evaluate} disabled={!versionId || !quantity}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          {simulate ? "Simulate placement" : "Evaluate & reserve"}
        </button>
      </div>

      {result && (
        <div className="mt-4 flex flex-col gap-2">
          <h4 className="text-xs font-medium">Evaluated candidates (ranked, explained)</h4>
          <ul className="flex flex-col gap-2 text-xs">
            {result.evaluations
              .slice()
              .sort((a, b) => (a.rank ?? 999) - (b.rank ?? 999))
              .map((ev) => (
                <li key={ev.id} className="rounded border border-zinc-100 p-2 dark:border-zinc-900">
                  <div className="flex items-center justify-between">
                    <span>{ev.accelerator_type} {ev.rank ? `(rank ${ev.rank})` : ""}</span>
                    <span className={ev.decision === "eligible" ? "text-emerald-600" : "text-red-600"}>{ev.decision}</span>
                  </div>
                  <p className="mt-1 text-zinc-500">
                    Cost ${ev.estimated_cost.toFixed(2)} &middot; {ev.estimated_energy_kwh.toFixed(2)} kWh estimated
                  </p>
                  {ev.reason_codes.length > 0 && (
                    <p className="mt-1 text-zinc-500">Reasons: {ev.reason_codes.join(", ")}</p>
                  )}
                </li>
              ))}
          </ul>
          {result.reservation ? (
            <p className="text-xs text-emerald-600">
              Reservation created: {result.reservation.status} (${result.reservation.estimated_cost.toFixed(2)})
            </p>
          ) : (
            !simulate && <p className="text-xs text-amber-600">No capacity could be reserved for this request.</p>
          )}
        </div>
      )}
    </section>
  );
}
