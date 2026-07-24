"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type OperatorMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface NetworkCapability {
  id: string;
  capability_type: string;
  bandwidth_gbps: number;
}

interface NetworkServiceOffer {
  id: string;
  network_capability_id: string;
  service_class: string;
  total_bandwidth_gbps: number;
  available_bandwidth_gbps: number;
  max_latency_ms?: number;
  price_per_unit_hour: number;
  currency: string;
  status: string;
}

interface NetworkReservation {
  id: string;
  enterprise_tenant_id: string;
  bandwidth_gbps: number;
  estimated_cost: number;
  status: string;
  provisioning_status: string;
  committed_at: string;
}

interface NetworkHealthEvent {
  id: string;
  event_type: string;
  severity: string;
  occurred_at: string;
}

// Roles known (from docs/security/permission-matrix.md) to hold the
// server-side operator.network.manage / operator.reservations.view
// permissions -- a UX convenience only, re-checked independently by
// control-api on every request.
const CAN_MANAGE = new Set(["operator_platform_owner", "operator_network_administrator"]);
const CAN_VIEW_RESERVATIONS = new Set(["operator_platform_owner", "operator_capacity_manager"]);

export default function OperatorNetworkServicesPage({ params }: { params: Promise<{ operatorId: string }> }) {
  const { operatorId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["operator-members", operatorId],
    queryFn: () => api.get<OperatorMembership[]>(`/api/v1/operators/${operatorId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const canManage = CAN_MANAGE.has(myRole);
  const canViewReservations = CAN_VIEW_RESERVATIONS.has(myRole);

  const capabilities = useQuery({
    queryKey: ["network-capabilities", operatorId],
    queryFn: () => api.get<NetworkCapability[]>(`/api/v1/operators/${operatorId}/network-capabilities`),
  });
  const offers = useQuery({
    queryKey: ["network-service-offers", operatorId],
    queryFn: () => api.get<NetworkServiceOffer[]>(`/api/v1/operators/${operatorId}/network-service-offers`),
  });
  const reservations = useQuery({
    queryKey: ["operator-network-reservations", operatorId],
    queryFn: () => api.get<NetworkReservation[]>(`/api/v1/operators/${operatorId}/network-reservations`),
    enabled: canViewReservations,
  });
  const healthEvents = useQuery({
    queryKey: ["operator-network-health-events", operatorId],
    queryFn: () => api.get<NetworkHealthEvent[]>(`/api/v1/operators/${operatorId}/network-health-events`),
    enabled: canViewReservations,
  });

  const invalidateOffers = () => queryClient.invalidateQueries({ queryKey: ["network-service-offers", operatorId] });
  const capabilityLabel = (id: string) => {
    const c = capabilities.data?.find((x) => x.id === id);
    return c ? `${c.capability_type} (${c.bandwidth_gbps} Gbps)` : id;
  };

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not have access to this operator.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-8">
      <Link href={`/dashboard/operator/${operatorId}`} className="text-sm underline">&larr; Operator overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Network service offers &amp; reservations</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Network services you publish here are built against your already-registered network
        capabilities (private connectivity, private 5G, network slices) and visible to every
        enterprise tenant on the platform. A committed reservation is provisioned by sending a
        signed command to the cluster agent resolved from the offer&apos;s capability location --
        GRIDKEEP requests and verifies authorised network services through operator connectors, it
        never replaces your own network control systems.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Offers</h2>
        <ul className="flex flex-col gap-2">
          {offers.data?.map((o) => (
            <OfferRow key={o.id} operatorId={operatorId} offer={o} capabilityLabel={capabilityLabel(o.network_capability_id)} canManage={canManage} onChanged={invalidateOffers} />
          ))}
          {offers.data?.length === 0 && <li className="text-sm text-zinc-500">No network service offers published yet.</li>}
        </ul>
      </section>

      {canManage && (
        <CreateOfferForm operatorId={operatorId} capabilities={capabilities.data} onCreated={invalidateOffers} />
      )}

      {canViewReservations && (
        <section className="mt-8">
          <h2 className="mb-3 text-lg font-medium">Reservations held against your offers</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {reservations.data?.map((r) => (
              <li key={r.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <span>{r.bandwidth_gbps} Gbps &middot; ${r.estimated_cost.toFixed(2)}</span>
                  <span className="text-zinc-500">{r.status} / {r.provisioning_status}</span>
                </div>
                <p className="mt-1 text-xs text-zinc-500">
                  Committed {new Date(r.committed_at).toLocaleString()}
                </p>
              </li>
            ))}
            {reservations.data?.length === 0 && <li className="text-zinc-500">No reservations yet.</li>}
          </ul>
        </section>
      )}

      {canViewReservations && (
        <section className="mt-8">
          <h2 className="mb-3 text-lg font-medium">Network health events</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {healthEvents.data?.map((e) => (
              <li key={e.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                <div className="flex items-center justify-between">
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
      )}
    </main>
  );
}

function OfferRow({
  operatorId,
  offer,
  capabilityLabel,
  canManage,
  onChanged,
}: {
  operatorId: string;
  offer: NetworkServiceOffer;
  capabilityLabel: string;
  canManage: boolean;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  const setStatus = async (status: string) => {
    setError(null);
    try {
      await api.patch(`/api/v1/operators/${operatorId}/network-service-offers/${offer.id}`, { status });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update offer.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span className="font-medium">{capabilityLabel} &middot; {offer.service_class}</span>
        <span className="text-zinc-500">{offer.status}</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {offer.available_bandwidth_gbps} / {offer.total_bandwidth_gbps} Gbps available &middot; ${offer.price_per_unit_hour}/Gbps/hr
        {offer.max_latency_ms != null && ` · ≤${offer.max_latency_ms}ms latency`}
      </p>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {canManage && (
        <div className="mt-2 flex gap-3">
          {offer.status !== "active" && (
            <button onClick={() => setStatus("active")} className="text-xs underline">Activate</button>
          )}
          {offer.status === "active" && (
            <button onClick={() => setStatus("paused")} className="text-xs underline">Pause</button>
          )}
          {offer.status !== "withdrawn" && (
            <button onClick={() => setStatus("withdrawn")} className="text-xs text-red-600 underline">Withdraw</button>
          )}
        </div>
      )}
    </li>
  );
}

function CreateOfferForm({
  operatorId,
  capabilities,
  onCreated,
}: {
  operatorId: string;
  capabilities: NetworkCapability[] | undefined;
  onCreated: () => void;
}) {
  const [capabilityId, setCapabilityId] = useState("");
  const [serviceClass, setServiceClass] = useState("");
  const [totalBandwidthGbps, setTotalBandwidthGbps] = useState("");
  const [maxLatencyMs, setMaxLatencyMs] = useState("");
  const [pricePerUnitHour, setPricePerUnitHour] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/network-service-offers`, {
        network_capability_id: capabilityId,
        service_class: serviceClass,
        total_bandwidth_gbps: Number(totalBandwidthGbps),
        max_latency_ms: maxLatencyMs ? Number(maxLatencyMs) : undefined,
        price_per_unit_hour: Number(pricePerUnitHour),
        currency: "USD",
      });
      setCapabilityId("");
      setServiceClass("");
      setTotalBandwidthGbps("");
      setMaxLatencyMs("");
      setPricePerUnitHour("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to publish offer.");
    }
  };

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Publish a new network service offer</h3>
      <div className="flex flex-col gap-2">
        <select aria-label="Network capability" value={capabilityId} onChange={(e) => setCapabilityId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Select a network capability</option>
          {capabilities?.map((c) => (
            <option key={c.id} value={c.id}>{c.capability_type} ({c.bandwidth_gbps} Gbps)</option>
          ))}
        </select>
        <input placeholder="Service class (e.g. private-5g-standard, network-slice-low-latency)" value={serviceClass}
          onChange={(e) => setServiceClass(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Service class (e.g. private-5g-standard, network-slice-low-latency)" />
        <input placeholder="Total bandwidth (Gbps)" type="number" value={totalBandwidthGbps}
          onChange={(e) => setTotalBandwidthGbps(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Total bandwidth (Gbps)" />
        <input placeholder="Max latency (ms, optional)" type="number" step="0.1" value={maxLatencyMs}
          onChange={(e) => setMaxLatencyMs(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Max latency (ms, optional)" />
        <input placeholder="Price per Gbps per hour (USD)" type="number" step="0.01" value={pricePerUnitHour}
          onChange={(e) => setPricePerUnitHour(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Price per Gbps per hour (USD)" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!capabilityId || !serviceClass || !totalBandwidthGbps || !pricePerUnitHour}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Publish offer
        </button>
      </div>
    </section>
  );
}
