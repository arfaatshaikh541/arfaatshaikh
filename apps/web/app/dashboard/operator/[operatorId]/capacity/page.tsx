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
  visibility: string;
  degraded: boolean;
  degraded_reason: string;
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

interface BilateralAgreement {
  id: string;
  enterprise_tenant_id: string;
  status: string;
  currency: string;
  platform_fee_rate: number;
  minimum_commitment_hours?: number;
  minimum_commitment_amount?: number;
  notes: string;
}

interface CapacityOfferGrant {
  id: string;
  capacity_offer_id: string;
  enterprise_tenant_id: string;
  bilateral_agreement_id?: string;
  price_per_unit_hour_override?: number;
  status: string;
}

// Roles known (from docs/security/permission-matrix.md) to hold the
// server-side operator.capacity.manage / operator.reservations.view /
// operator.agreements.manage permissions -- a UX convenience only,
// re-checked independently by control-api on every request.
const CAN_MANAGE = new Set(["operator_platform_owner", "operator_capacity_manager", "operator_cloud_administrator", "operator_edge_administrator", "operator_infrastructure_administrator"]);
const CAN_VIEW_RESERVATIONS = new Set(["operator_platform_owner", "operator_capacity_manager"]);
const CAN_MANAGE_AGREEMENTS = new Set(["operator_platform_owner", "operator_product_manager", "operator_compliance_officer"]);

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
  const canManageAgreements = CAN_MANAGE_AGREEMENTS.has(myRole);

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
  const agreements = useQuery({
    queryKey: ["bilateral-agreements", operatorId],
    queryFn: () => api.get<BilateralAgreement[]>(`/api/v1/operators/${operatorId}/bilateral-agreements`),
  });

  const invalidateOffers = () => queryClient.invalidateQueries({ queryKey: ["capacity-offers", operatorId] });
  const invalidateAgreements = () => queryClient.invalidateQueries({ queryKey: ["bilateral-agreements", operatorId] });
  const clusterName = (id: string) => clusters.data?.find((c) => c.id === id)?.name ?? id;

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
        <p>You do not have access to this operator.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
      <Link href={`/dashboard/operator/${operatorId}`} className="text-sm underline">&larr; Operator overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Capacity offers &amp; reservations</h1>
      <p className="mb-6 text-sm text-zinc-500">
        A public offer is visible to every enterprise tenant on the platform; a private offer is
        visible only to a tenant you have explicitly granted access to below, optionally at its
        own tenant-specific price. Marking an offer degraded excludes it from placement with an
        explained reason code -- it stays visible, just not reservable, until you clear it.
        available_capacity is only ever changed by the placement engine&apos;s atomic
        reserve/release/expiry paths, never by direct edit here except to add new supply.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Offers</h2>
        <ul className="flex flex-col gap-2">
          {offers.data?.map((o) => (
            <OfferRow key={o.id} operatorId={operatorId} offer={o} clusterName={clusterName(o.cluster_id)}
              canManage={canManage} canManageAgreements={canManageAgreements} agreements={agreements.data}
              onChanged={invalidateOffers} />
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
                <div className="flex items-center justify-between flex-wrap gap-1">
                  <span>{r.quantity} unit(s) &middot; ${r.estimated_cost.toFixed(2)} at ${r.price_per_unit_hour}/unit/hr</span>
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

      <section className="mt-8">
        <h2 className="mb-3 text-lg font-medium">Bilateral agreements</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {agreements.data?.map((a) => (
            <AgreementRow key={a.id} operatorId={operatorId} agreement={a} canManage={canManageAgreements} onChanged={invalidateAgreements} />
          ))}
          {agreements.data?.length === 0 && <li className="text-zinc-500">No bilateral agreements yet.</li>}
        </ul>
        {canManageAgreements && <CreateAgreementForm operatorId={operatorId} onCreated={invalidateAgreements} />}
      </section>
    </main>
  );
}

function OfferRow({
  operatorId,
  offer,
  clusterName,
  canManage,
  canManageAgreements,
  agreements,
  onChanged,
}: {
  operatorId: string;
  offer: CapacityOffer;
  clusterName: string;
  canManage: boolean;
  canManageAgreements: boolean;
  agreements: BilateralAgreement[] | undefined;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [degradedReasonInput, setDegradedReasonInput] = useState("");
  const [grantsOpen, setGrantsOpen] = useState(false);
  const queryClient = useQueryClient();

  const grants = useQuery({
    queryKey: ["capacity-offer-grants", operatorId, offer.id],
    queryFn: () => api.get<CapacityOfferGrant[]>(`/api/v1/operators/${operatorId}/capacity-offers/${offer.id}/grants`),
    enabled: grantsOpen,
  });
  const invalidateGrants = () => queryClient.invalidateQueries({ queryKey: ["capacity-offer-grants", operatorId, offer.id] });

  const setStatus = async (status: string) => {
    setError(null);
    try {
      await api.patch(`/api/v1/operators/${operatorId}/capacity-offers/${offer.id}`, { status });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update offer.");
    }
  };

  const setVisibility = async (visibility: string) => {
    setError(null);
    try {
      await api.patch(`/api/v1/operators/${operatorId}/capacity-offers/${offer.id}`, { visibility });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update offer.");
    }
  };

  const setDegraded = async (degraded: boolean) => {
    setError(null);
    try {
      await api.patch(`/api/v1/operators/${operatorId}/capacity-offers/${offer.id}`, {
        degraded, degraded_reason: degraded ? degradedReasonInput : "",
      });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update offer.");
    }
  };

  const revokeGrant = async (grantID: string) => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/capacity-offer-grants/${grantID}/revoke`, {});
      invalidateGrants();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to revoke grant.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800">
      <div className="flex items-center justify-between flex-wrap gap-1">
        <span className="font-medium">{clusterName} &middot; {offer.accelerator_type}</span>
        <div className="flex items-center gap-2 flex-wrap">
          {offer.visibility === "private" && <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">private</span>}
          {offer.degraded && <span className="rounded bg-red-100 px-2 py-0.5 text-xs text-red-900 dark:bg-red-900 dark:text-red-100">degraded</span>}
          <span className="text-zinc-500">{offer.status}</span>
        </div>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {offer.available_capacity} / {offer.total_capacity} available &middot; ${offer.price_per_unit_hour}/unit/hr &middot;{" "}
        {offer.confidential_computing_available ? "confidential computing available" : "no confidential computing"}
      </p>
      {offer.degraded && offer.degraded_reason && <p className="mt-1 text-xs text-red-600">Degraded: {offer.degraded_reason}</p>}
      {error && <p className="text-xs text-red-600">{error}</p>}
      {canManage && (
        <div className="mt-2 flex flex-wrap gap-3">
          {offer.status !== "active" && <button onClick={() => setStatus("active")} className="text-xs underline">Activate</button>}
          {offer.status === "active" && <button onClick={() => setStatus("paused")} className="text-xs underline">Pause</button>}
          {offer.status !== "withdrawn" && <button onClick={() => setStatus("withdrawn")} className="text-xs text-red-600 underline">Withdraw</button>}
          <button onClick={() => setVisibility(offer.visibility === "public" ? "private" : "public")} className="text-xs underline">
            Make {offer.visibility === "public" ? "private" : "public"}
          </button>
          {offer.degraded ? (
            <button onClick={() => setDegraded(false)} className="text-xs underline">Clear degraded</button>
          ) : (
            <button onClick={() => setDegraded(true)} className="text-xs text-red-600 underline">Mark degraded</button>
          )}
          <button onClick={() => setGrantsOpen(!grantsOpen)} className="text-xs underline">
            {grantsOpen ? "Hide grants" : "Manage grants"}
          </button>
        </div>
      )}
      {canManage && !offer.degraded && (
        <input placeholder="Degraded reason (used when you mark degraded)" value={degradedReasonInput}
          onChange={(e) => setDegradedReasonInput(e.target.value)}
          className="mt-2 w-full rounded-md border border-zinc-300 px-3 py-1.5 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Degraded reason (used when you mark degraded)" />
      )}
      {grantsOpen && (
        <div className="mt-3 rounded-md border border-zinc-200 p-3 dark:border-zinc-800">
          <ul className="flex flex-col gap-2 text-xs">
            {grants.data?.map((g) => (
              <li key={g.id} className="flex items-center justify-between flex-wrap gap-1">
                <span>
                  tenant {g.enterprise_tenant_id.slice(0, 8)}&hellip;
                  {g.price_per_unit_hour_override != null && <> &middot; ${g.price_per_unit_hour_override}/unit/hr override</>}
                </span>
                <span className="flex items-center gap-2 flex-wrap">
                  <span className="text-zinc-500">{g.status}</span>
                  {g.status === "active" && <button onClick={() => revokeGrant(g.id)} className="text-red-600 underline">Revoke</button>}
                </span>
              </li>
            ))}
            {grants.data?.length === 0 && <li className="text-zinc-500">No grants issued for this offer yet.</li>}
          </ul>
          {canManageAgreements && (
            <CreateGrantForm operatorId={operatorId} offerId={offer.id} agreements={agreements} onCreated={invalidateGrants} />
          )}
        </div>
      )}
    </li>
  );
}

function CreateGrantForm({
  operatorId,
  offerId,
  agreements,
  onCreated,
}: {
  operatorId: string;
  offerId: string;
  agreements: BilateralAgreement[] | undefined;
  onCreated: () => void;
}) {
  const [tenantId, setTenantId] = useState("");
  const [agreementId, setAgreementId] = useState("");
  const [priceOverride, setPriceOverride] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/capacity-offers/${offerId}/grants`, {
        enterprise_tenant_id: tenantId,
        bilateral_agreement_id: agreementId || undefined,
        price_per_unit_hour_override: priceOverride ? Number(priceOverride) : undefined,
      });
      setTenantId("");
      setPriceOverride("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create grant.");
    }
  };

  return (
    <div className="mt-3 flex flex-col gap-2">
      <input placeholder="Enterprise tenant id" value={tenantId} onChange={(e) => setTenantId(e.target.value)}
        className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Enterprise tenant id" />
      <div className="flex gap-2 flex-wrap">
        <select aria-label="Bilateral agreement" value={agreementId} onChange={(e) => setAgreementId(e.target.value)}
          className="flex-1 rounded-md border border-zinc-300 px-3 py-1.5 text-xs dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">No linked agreement</option>
          {agreements?.filter((a) => a.status === "active").map((a) => (
            <option key={a.id} value={a.id}>{a.enterprise_tenant_id.slice(0, 8)}&hellip; ({a.platform_fee_rate * 100}% fee)</option>
          ))}
        </select>
        <input placeholder="Price override (optional)" type="number" min={0} step="0.01" value={priceOverride}
          onChange={(e) => setPriceOverride(e.target.value)}
          className="w-40 rounded-md border border-zinc-300 px-3 py-1.5 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Price override (optional)" />
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <button onClick={create} disabled={!tenantId} className="self-start rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium disabled:opacity-50 dark:border-zinc-700">
        Grant access
      </button>
    </div>
  );
}

function AgreementRow({
  operatorId,
  agreement,
  canManage,
  onChanged,
}: {
  operatorId: string;
  agreement: BilateralAgreement;
  canManage: boolean;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  const terminate = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/bilateral-agreements/${agreement.id}/terminate`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to terminate agreement.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between flex-wrap gap-1">
        <span>tenant {agreement.enterprise_tenant_id.slice(0, 8)}&hellip; &middot; {agreement.currency} &middot; {(agreement.platform_fee_rate * 100).toFixed(1)}% platform fee</span>
        <span className={agreement.status === "active" ? "text-emerald-600" : "text-zinc-500"}>{agreement.status}</span>
      </div>
      {(agreement.minimum_commitment_hours || agreement.minimum_commitment_amount) && (
        <p className="mt-1 text-xs text-zinc-500">
          Minimum commitment: {agreement.minimum_commitment_hours ? `${agreement.minimum_commitment_hours}h` : ""}
          {agreement.minimum_commitment_hours && agreement.minimum_commitment_amount ? " / " : ""}
          {agreement.minimum_commitment_amount ? `${agreement.currency} ${agreement.minimum_commitment_amount}` : ""}
        </p>
      )}
      {agreement.notes && <p className="mt-1 text-xs text-zinc-500">{agreement.notes}</p>}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      {canManage && agreement.status === "active" && (
        <button onClick={terminate} className="mt-2 text-xs text-red-600 underline">Terminate</button>
      )}
    </li>
  );
}

function CreateAgreementForm({ operatorId, onCreated }: { operatorId: string; onCreated: () => void }) {
  const [tenantId, setTenantId] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [feeRate, setFeeRate] = useState("0.10");
  const [minCommitmentHours, setMinCommitmentHours] = useState("");
  const [minCommitmentAmount, setMinCommitmentAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/bilateral-agreements`, {
        enterprise_tenant_id: tenantId,
        currency,
        platform_fee_rate: Number(feeRate),
        minimum_commitment_hours: minCommitmentHours ? Number(minCommitmentHours) : undefined,
        minimum_commitment_amount: minCommitmentAmount ? Number(minCommitmentAmount) : undefined,
        notes,
      });
      setTenantId("");
      setNotes("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create bilateral agreement.");
    }
  };

  return (
    <div className="mt-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Establish a new bilateral agreement</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Enterprise tenant id" value={tenantId} onChange={(e) => setTenantId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Enterprise tenant id" />
        <div className="flex gap-2 flex-wrap">
          <input placeholder="Currency" value={currency} onChange={(e) => setCurrency(e.target.value)}
            className="w-24 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Currency" />
          <input placeholder="Platform fee rate (0-1)" type="number" min={0} max={1} step="0.01" value={feeRate}
            onChange={(e) => setFeeRate(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Platform fee rate (0-1)" />
        </div>
        <div className="flex gap-2 flex-wrap">
          <input placeholder="Min. commitment (hours, optional)" type="number" min={0} value={minCommitmentHours}
            onChange={(e) => setMinCommitmentHours(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Min. commitment (hours, optional)" />
          <input placeholder="Min. commitment (amount, optional)" type="number" min={0} value={minCommitmentAmount}
            onChange={(e) => setMinCommitmentAmount(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Min. commitment (amount, optional)" />
        </div>
        <input placeholder="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Notes (optional)" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!tenantId} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Create agreement
        </button>
      </div>
    </div>
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
  const [visibility, setVisibility] = useState("public");
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
        visibility,
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
        <select aria-label="Cluster" value={clusterId} onChange={(e) => setClusterId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Select a cluster</option>
          {clusters?.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <input placeholder="Accelerator type (e.g. nvidia-h100, cpu_only)" value={acceleratorType}
          onChange={(e) => setAcceleratorType(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Accelerator type (e.g. nvidia-h100, cpu_only)" />
        <input placeholder="Total capacity (units)" type="number" value={totalCapacity}
          onChange={(e) => setTotalCapacity(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Total capacity (units)" />
        <input placeholder="Price per unit per hour (USD)" type="number" step="0.01" value={pricePerUnitHour}
          onChange={(e) => setPricePerUnitHour(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Price per unit per hour (USD)" />
        <select aria-label="Visibility" value={visibility} onChange={(e) => setVisibility(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="public">Public (visible to every tenant)</option>
          <option value="private">Private (visible only to tenants you grant)</option>
        </select>
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
