"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type OperatorMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface Cluster {
  id: string;
  name: string;
}

interface CapacityOffer {
  id: string;
  cluster_id: string;
  accelerator_type: string;
  total_capacity: number;
  available_capacity: number;
  price_per_unit_hour: number;
  currency: string;
  confidential_computing_available: boolean;
  estimated_kwh_per_unit_hour: number;
  status: string;
}

interface Reservation {
  id: string;
  enterprise_tenant_id: string;
  capacity_offer_id: string;
  quantity: number;
  price_per_unit_hour: number;
  estimated_cost: number;
  status: string;
  held_at: string;
  expires_at: string;
}

// Roles known (from docs/security/permission-matrix.md) to hold the
// server-side operator.capacity.manage / operator.reservations.view
// permissions -- a UX convenience only, re-checked independently by
// control-api on every request.
const CAN_MANAGE = new Set(["operator_platform_owner", "operator_capacity_manager", "operator_cloud_administrator", "operator_edge_administrator", "operator_infrastructure_administrator"]);
const CAN_VIEW_RESERVATIONS = new Set(["operator_platform_owner", "operator_capacity_manager"]);

export default function OperatorCapacityPage({ params }: { params: Promise<{ operatorId: string }> }) {
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

  const clusters = useQuery({
    queryKey: ["clusters", operatorId],
    queryFn: () => api.get<Cluster[]>(`/api/v1/operators/${operatorId}/clusters`),
  });
  const offers = useQuery({
    queryKey: ["capacity-offers", operatorId],
    queryFn: () => api.get<CapacityOffer[]>(`/api/v1/operators/${operatorId}/capacity-offers`),
  });
  const reservations = useQuery({
    queryKey: ["operator-capacity-reservations", operatorId],
    queryFn: () => api.get<Reservation[]>(`/api/v1/operators/${operatorId}/capacity-reservations`),
    enabled: canViewReservations,
  });

  const invalidateOffers = () => queryClient.invalidateQueries({ queryKey: ["capacity-offers", operatorId] });
  const clusterName = (id: string) => clusters.data?.find((c) => c.id === id)?.name ?? id;

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not have access to this operator.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 p-8">
      <Link href={`/dashboard/operator/${operatorId}`} className="text-sm underline">&larr; Operator overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Capacity offers &amp; reservations</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Capacity you publish here is visible to every enterprise tenant on the platform (a
        single-operator marketplace -- bilateral agreements and cross-operator federation are a
        later milestone). available_capacity is only ever changed by the placement engine&apos;s
        atomic reserve/release/expiry paths, never by direct edit here except to add new supply.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Offers</h2>
        <ul className="flex flex-col gap-2">
          {offers.data?.map((o) => (
            <OfferRow key={o.id} operatorId={operatorId} offer={o} clusterName={clusterName(o.cluster_id)} canManage={canManage} onChanged={invalidateOffers} />
          ))}
          {offers.data?.length === 0 && <li className="text-sm text-zinc-500">No capacity offers published yet.</li>}
        </ul>
      </section>

      {canManage && (
        <CreateOfferForm operatorId={operatorId} clusters={clusters.data} onCreated={invalidateOffers} />
      )}

      {canViewReservations && (
        <section className="mt-8">
          <h2 className="mb-3 text-lg font-medium">Reservations held against your capacity</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {reservations.data?.map((r) => (
              <li key={r.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <span>{r.quantity} unit(s) &middot; ${r.estimated_cost.toFixed(2)}</span>
                  <span className="text-zinc-500">{r.status}</span>
                </div>
                <p className="mt-1 text-xs text-zinc-500">
                  Held {new Date(r.held_at).toLocaleString()} &middot; expires {new Date(r.expires_at).toLocaleString()}
                </p>
              </li>
            ))}
            {reservations.data?.length === 0 && <li className="text-zinc-500">No reservations yet.</li>}
          </ul>
        </section>
      )}
    </main>
  );
}

function OfferRow({
  operatorId,
  offer,
  clusterName,
  canManage,
  onChanged,
}: {
  operatorId: string;
  offer: CapacityOffer;
  clusterName: string;
  canManage: boolean;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  const setStatus = async (status: string) => {
    setError(null);
    try {
      await api.patch(`/api/v1/operators/${operatorId}/capacity-offers/${offer.id}`, { status });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update offer.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span className="font-medium">{clusterName} &middot; {offer.accelerator_type}</span>
        <span className="text-zinc-500">{offer.status}</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {offer.available_capacity} / {offer.total_capacity} available &middot; ${offer.price_per_unit_hour}/unit/hr &middot;{" "}
        {offer.confidential_computing_available ? "confidential computing available" : "no confidential computing"}
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
  clusters,
  onCreated,
}: {
  operatorId: string;
  clusters: Cluster[] | undefined;
  onCreated: () => void;
}) {
  const [clusterId, setClusterId] = useState("");
  const [acceleratorType, setAcceleratorType] = useState("nvidia-h100");
  const [totalCapacity, setTotalCapacity] = useState("");
  const [pricePerUnitHour, setPricePerUnitHour] = useState("");
  const [confidentialComputing, setConfidentialComputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/capacity-offers`, {
        cluster_id: clusterId,
        accelerator_type: acceleratorType,
        total_capacity: Number(totalCapacity),
        price_per_unit_hour: Number(pricePerUnitHour),
        currency: "USD",
        confidential_computing_available: confidentialComputing,
        estimated_kwh_per_unit_hour: 0.5,
      });
      setClusterId("");
      setTotalCapacity("");
      setPricePerUnitHour("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to publish offer.");
    }
  };

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Publish a new capacity offer</h3>
      <div className="flex flex-col gap-2">
        <select value={clusterId} onChange={(e) => setClusterId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Select a cluster</option>
          {clusters?.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <input placeholder="Accelerator type (e.g. nvidia-h100, cpu_only)" value={acceleratorType}
          onChange={(e) => setAcceleratorType(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <input placeholder="Total capacity (units)" type="number" value={totalCapacity}
          onChange={(e) => setTotalCapacity(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <input placeholder="Price per unit per hour (USD)" type="number" step="0.01" value={pricePerUnitHour}
          onChange={(e) => setPricePerUnitHour(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={confidentialComputing} onChange={(e) => setConfidentialComputing(e.target.checked)} />
          Confidential computing available
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!clusterId || !totalCapacity || !pricePerUnitHour}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Publish offer
        </button>
      </div>
    </section>
  );
}
