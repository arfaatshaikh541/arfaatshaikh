"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type EnterpriseMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface NetworkServiceOffer {
  id: string;
  operator_id: string;
  region_id: string;
  service_class: string;
  available_bandwidth_gbps: number;
  max_latency_ms?: number;
  price_per_unit_hour: number;
  currency: string;
}

interface NetworkServiceEvaluation {
  id: string;
  network_service_offer_id: string;
  operator_id: string;
  service_class: string;
  decision: string;
  rank?: number;
  estimated_cost: number;
  reason_codes: string[];
  explanation: Record<string, unknown>;
}

interface NetworkReservation {
  id: string;
  network_service_offer_id: string;
  bandwidth_gbps: number;
  price_per_unit_hour: number;
  estimated_cost: number;
  status: string;
  provisioning_status: string;
  committed_at: string;
}

interface NetworkServiceRequest {
  id: string;
  required_bandwidth_gbps: number;
  simulate: boolean;
  status: string;
}

interface EvaluateNetworkServiceResult {
  request: NetworkServiceRequest;
  evaluations: NetworkServiceEvaluation[];
  reservation?: NetworkReservation;
}

interface NetworkHealthEvent {
  id: string;
  event_type: string;
  severity: string;
  occurred_at: string;
}

// Roles known (from docs/security/permission-matrix.md) to hold the
// server-side network.view / reservations.create / reservations.cancel
// permissions -- a UX convenience only, re-checked independently by
// control-api on every request.
const CAN_RESERVE = new Set(["enterprise_owner", "enterprise_admin", "ai_platform_engineer", "devops_engineer", "finops_manager"]);
const CAN_CANCEL = new Set(["enterprise_owner", "enterprise_admin", "ai_platform_engineer", "devops_engineer", "finops_manager"]);

export default function EnterpriseNetworkServicesPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["tenant-members", tenantId],
    queryFn: () => api.get<EnterpriseMembership[]>(`/api/v1/enterprises/${tenantId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const canReserve = CAN_RESERVE.has(myRole);
  const canCancel = CAN_CANCEL.has(myRole);

  const offers = useQuery({
    queryKey: ["network-service-offers-enterprise", tenantId],
    queryFn: () => api.get<NetworkServiceOffer[]>(`/api/v1/enterprises/${tenantId}/network-service-offers`),
  });
  const reservations = useQuery({
    queryKey: ["tenant-network-reservations", tenantId],
    queryFn: () => api.get<NetworkReservation[]>(`/api/v1/enterprises/${tenantId}/network-reservations`),
  });
  const healthEvents = useQuery({
    queryKey: ["tenant-network-health-events", tenantId],
    queryFn: () => api.get<NetworkHealthEvent[]>(`/api/v1/enterprises/${tenantId}/network-health-events`),
  });

  const invalidateReservations = () => queryClient.invalidateQueries({ queryKey: ["tenant-network-reservations", tenantId] });
  const invalidateOffers = () => queryClient.invalidateQueries({ queryKey: ["network-service-offers-enterprise", tenantId] });
  const invalidateHealthEvents = () => queryClient.invalidateQueries({ queryKey: ["tenant-network-health-events", tenantId] });

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
        <p>You do not have access to this tenant&apos;s network services.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
      <Link href={`/dashboard/enterprise/${tenantId}`} className="text-sm underline">&larr; Tenant overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Network services</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Private connectivity, private 5G, and network-slice capacity across every operator on the
        platform. Reserving a network service commits immediately -- there is no dual-control
        approval step for network reservations, unlike capacity reservations.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Available network services (marketplace)</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {offers.data?.map((o) => (
            <li key={o.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
              <div className="flex items-center justify-between flex-wrap gap-1">
                <span>{o.service_class}</span>
                <span className="text-zinc-500">{o.available_bandwidth_gbps} Gbps available</span>
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                ${o.price_per_unit_hour}/Gbps/hr{o.max_latency_ms != null && ` · ≤${o.max_latency_ms}ms latency`}
              </p>
            </li>
          ))}
          {offers.data?.length === 0 && <li className="text-zinc-500">No network service offers visible yet.</li>}
        </ul>
      </section>

      {canReserve && (
        <EvaluateNetworkServiceForm
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
              canCancel={canCancel}
              onChanged={() => {
                invalidateReservations();
                invalidateOffers();
                invalidateHealthEvents();
              }}
            />
          ))}
          {reservations.data?.length === 0 && <li className="text-zinc-500">No reservations yet.</li>}
        </ul>
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-lg font-medium">Network health events</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {healthEvents.data?.map((e) => (
            <li key={e.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
              <div className="flex items-center justify-between flex-wrap gap-1">
                <span>{e.event_type}</span>
                <span className={e.severity === "critical" ? "text-red-600" : e.severity === "warning" ? "text-amber-600" : "text-zinc-500"}>
                  {e.severity}
                </span>
              </div>
              <p className="mt-1 text-xs text-zinc-500">{new Date(e.occurred_at).toLocaleString()}</p>
            </li>
          ))}
          {healthEvents.data?.length === 0 && <li className="text-zinc-500">No network health events yet.</li>}
        </ul>
      </section>
    </main>
  );
}

function ReservationRow({
  tenantId,
  reservation,
  canCancel,
  onChanged,
}: {
  tenantId: string;
  reservation: NetworkReservation;
  canCancel: boolean;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  const cancel = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/network-reservations/${reservation.id}/cancel`, { reason: "cancelled from dashboard" });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to cancel reservation.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between flex-wrap gap-1">
        <span>{reservation.bandwidth_gbps} Gbps &middot; ${reservation.estimated_cost.toFixed(2)}</span>
        <span className="text-zinc-500">{reservation.status} / {reservation.provisioning_status}</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        Committed {new Date(reservation.committed_at).toLocaleString()}
      </p>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {canCancel && reservation.status === "committed" && (
        <div className="mt-2 flex gap-3 flex-wrap">
          <button onClick={cancel} className="text-xs text-red-600 underline">Cancel</button>
        </div>
      )}
    </li>
  );
}

function EvaluateNetworkServiceForm({ tenantId, onEvaluated }: { tenantId: string; onEvaluated: () => void }) {
  const [requiredBandwidthGbps, setRequiredBandwidthGbps] = useState("");
  const [maxLatencyMs, setMaxLatencyMs] = useState("");
  const [serviceClass, setServiceClass] = useState("");
  const [simulate, setSimulate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EvaluateNetworkServiceResult | null>(null);

  const evaluate = async () => {
    setError(null);
    setResult(null);
    try {
      const res = await api.post<EvaluateNetworkServiceResult>(`/api/v1/enterprises/${tenantId}/network-service-requests`, {
        required_bandwidth_gbps: Number(requiredBandwidthGbps),
        max_latency_ms: maxLatencyMs ? Number(maxLatencyMs) : undefined,
        service_class: serviceClass || undefined,
        simulate,
      });
      setResult(res);
      onEvaluated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to evaluate network service.");
    }
  };

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Evaluate &amp; reserve a network service</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Required bandwidth (Gbps)" type="number" value={requiredBandwidthGbps}
          onChange={(e) => setRequiredBandwidthGbps(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Required bandwidth (Gbps)" />
        <input placeholder="Max latency (ms, optional)" type="number" step="0.1" value={maxLatencyMs}
          onChange={(e) => setMaxLatencyMs(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Max latency (ms, optional)" />
        <input placeholder="Service class (optional)" value={serviceClass}
          onChange={(e) => setServiceClass(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Service class (optional)" />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={simulate} onChange={(e) => setSimulate(e.target.checked)} />
          Simulate only (do not reserve bandwidth)
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={evaluate} disabled={!requiredBandwidthGbps}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          {simulate ? "Simulate" : "Evaluate & reserve"}
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
                  <div className="flex items-center justify-between flex-wrap gap-1">
                    <span>{ev.service_class} {ev.rank ? `(rank ${ev.rank})` : ""}</span>
                    <span className={ev.decision === "eligible" ? "text-emerald-600" : "text-red-600"}>{ev.decision}</span>
                  </div>
                  <p className="mt-1 text-zinc-500">Cost ${ev.estimated_cost.toFixed(2)}</p>
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
            !simulate && <p className="text-xs text-amber-600">No network service could be reserved for this request.</p>
          )}
        </div>
      )}
    </section>
  );
}
