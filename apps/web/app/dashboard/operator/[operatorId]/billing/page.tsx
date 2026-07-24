"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type OperatorMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface PriceRule {
  usage_metric_key: string;
  unit_price: number;
}

interface PriceBook {
  id: string;
  version: number;
  currency: string;
  status: string;
  rules?: PriceRule[];
}

interface UsageEvent {
  id: string;
  usage_metric_key: string;
  quantity: number;
  occurred_at: string;
  enterprise_tenant_id: string;
}

interface Invoice {
  id: string;
  enterprise_tenant_id: string;
  total: number;
  currency: string;
  status: string;
  issued_at: string;
}

interface SettlementRecord {
  id: string;
  period_start: string;
  period_end: string;
  gross_amount: number;
  net_amount: number;
  currency: string;
  status: string;
}

interface BillingDispute {
  id: string;
  invoice_id: string;
  reason: string;
  status: string;
  opened_at: string;
}

const USAGE_METRIC_KEYS = [
  "cpu_seconds", "gpu_seconds", "gpu_memory_gb_seconds", "storage_gb_hours", "object_storage_gb_hours",
  "network_ingress_gb", "network_egress_gb", "private_network_gb_hours", "network_slice_gbps_hours",
  "model_requests", "model_tokens", "inference_seconds", "reservation_hours",
  "confidential_computing_premium_hours", "support_hours",
];

// Roles known (from docs/security/permission-matrix.md) to hold the
// server-side operator.pricing.manage / operator.usage.view /
// operator.settlements.view / operator.settlements.manage permissions --
// a UX convenience only, re-checked independently by control-api on every
// request. Price book reads require only operator membership, matching
// this codebase's established "view is membership, manage is a
// permission" convention.
const CAN_MANAGE_PRICING = new Set(["operator_platform_owner", "operator_product_manager", "operator_finance_manager"]);
const CAN_VIEW_USAGE = new Set(["operator_platform_owner", "operator_finance_manager", "operator_auditor"]);
const CAN_VIEW_SETTLEMENTS = new Set(["operator_platform_owner", "operator_finance_manager", "operator_auditor"]);
const CAN_MANAGE_SETTLEMENTS = new Set(["operator_platform_owner", "operator_finance_manager"]);

export default function OperatorBillingPage({ params }: { params: Promise<{ operatorId: string }> }) {
  const { operatorId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["operator-members", operatorId],
    queryFn: () => api.get<OperatorMembership[]>(`/api/v1/operators/${operatorId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const canManagePricing = CAN_MANAGE_PRICING.has(myRole);
  const canViewUsage = CAN_VIEW_USAGE.has(myRole);
  const canViewSettlements = CAN_VIEW_SETTLEMENTS.has(myRole);
  const canManageSettlements = CAN_MANAGE_SETTLEMENTS.has(myRole);

  const priceBooks = useQuery({
    queryKey: ["operator-price-books", operatorId],
    queryFn: () => api.get<PriceBook[]>(`/api/v1/operators/${operatorId}/price-books`),
  });
  const usageEvents = useQuery({
    queryKey: ["operator-usage-events", operatorId],
    queryFn: () => api.get<UsageEvent[]>(`/api/v1/operators/${operatorId}/usage-events`),
    enabled: canViewUsage,
  });
  const invoices = useQuery({
    queryKey: ["operator-invoices", operatorId],
    queryFn: () => api.get<Invoice[]>(`/api/v1/operators/${operatorId}/invoices`),
    enabled: canViewSettlements,
  });
  const settlements = useQuery({
    queryKey: ["operator-settlements", operatorId],
    queryFn: () => api.get<SettlementRecord[]>(`/api/v1/operators/${operatorId}/settlements`),
    enabled: canViewSettlements,
  });
  const disputes = useQuery({
    queryKey: ["operator-billing-disputes", operatorId],
    queryFn: () => api.get<BillingDispute[]>(`/api/v1/operators/${operatorId}/billing-disputes`),
    enabled: canViewSettlements,
  });

  const invalidate = (key: string) => queryClient.invalidateQueries({ queryKey: [key, operatorId] });

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not have access to this operator&apos;s billing data.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 p-8">
      <Link href={`/dashboard/operator/${operatorId}`} className="text-sm underline">&larr; Operator overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Usage, billing &amp; settlement</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Every price and invoice total below is computed server-side from the active price book at
        the moment of computation -- nothing here accepts a price from this page. Usage aggregation
        and invoice generation run on demand; there is no live background scheduler in this
        environment.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Price books</h2>
        <ul className="flex flex-col gap-2">
          {priceBooks.data?.map((pb) => (
            <PriceBookRow key={pb.id} operatorId={operatorId} book={pb} canManage={canManagePricing} onChanged={() => invalidate("operator-price-books")} />
          ))}
          {priceBooks.data?.length === 0 && <li className="text-sm text-zinc-500">No price books yet.</li>}
        </ul>
        {canManagePricing && <CreatePriceBookForm operatorId={operatorId} onCreated={() => invalidate("operator-price-books")} />}
      </section>

      {canViewUsage && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Usage events</h2>
          <AggregateUsageForm operatorId={operatorId} />
          <ul className="mt-3 flex flex-col gap-1 text-sm">
            {usageEvents.data?.slice(0, 20).map((e) => (
              <li key={e.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                {e.usage_metric_key}: {e.quantity} &middot; {new Date(e.occurred_at).toLocaleString()}
              </li>
            ))}
            {usageEvents.data?.length === 0 && <li className="text-zinc-500">No usage events reported yet.</li>}
          </ul>
        </section>
      )}

      {canViewSettlements && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Invoices</h2>
          <GenerateInvoiceForm operatorId={operatorId} canManage={canManageSettlements} onGenerated={() => invalidate("operator-invoices")} />
          <ul className="mt-3 flex flex-col gap-1 text-sm">
            {invoices.data?.map((inv) => (
              <li key={inv.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <span>{inv.currency} {inv.total.toFixed(2)}</span>
                  <span className={inv.status === "disputed" ? "text-red-600" : "text-zinc-500"}>{inv.status}</span>
                </div>
                <p className="mt-1 text-xs text-zinc-500">Issued {new Date(inv.issued_at).toLocaleString()}</p>
              </li>
            ))}
            {invoices.data?.length === 0 && <li className="text-zinc-500">No invoices issued yet.</li>}
          </ul>
        </section>
      )}

      {canViewSettlements && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Settlements</h2>
          {canManageSettlements && <CreateSettlementForm operatorId={operatorId} onCreated={() => invalidate("operator-settlements")} />}
          <ul className="mt-3 flex flex-col gap-2 text-sm">
            {settlements.data?.map((s) => (
              <SettlementRow key={s.id} operatorId={operatorId} settlement={s} canManage={canManageSettlements} onChanged={() => invalidate("operator-settlements")} />
            ))}
            {settlements.data?.length === 0 && <li className="text-zinc-500">No settlement records yet.</li>}
          </ul>
        </section>
      )}

      {canViewSettlements && (
        <section>
          <h2 className="mb-3 text-lg font-medium">Billing disputes</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {disputes.data?.map((d) => (
              <DisputeRow key={d.id} operatorId={operatorId} dispute={d} canManage={canManageSettlements} onChanged={() => { invalidate("operator-billing-disputes"); invalidate("operator-invoices"); }} />
            ))}
            {disputes.data?.length === 0 && <li className="text-zinc-500">No disputes on record.</li>}
          </ul>
        </section>
      )}
    </main>
  );
}

function PriceBookRow({ operatorId, book, canManage, onChanged }: { operatorId: string; book: PriceBook; canManage: boolean; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);

  const activate = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/price-books/${book.id}/activate`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to activate price book.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span className="font-medium">v{book.version} ({book.currency})</span>
        <span className={book.status === "active" ? "text-emerald-600" : "text-zinc-500"}>{book.status}</span>
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      {canManage && book.status === "draft" && (
        <button onClick={activate} className="mt-2 text-xs underline">Activate</button>
      )}
    </li>
  );
}

function CreatePriceBookForm({ operatorId, onCreated }: { operatorId: string; onCreated: () => void }) {
  const [currency, setCurrency] = useState("USD");
  const [metricKey, setMetricKey] = useState(USAGE_METRIC_KEYS[0]);
  const [unitPrice, setUnitPrice] = useState("1.00");
  const [rules, setRules] = useState<PriceRule[]>([]);
  const [error, setError] = useState<string | null>(null);

  const addRule = () => {
    setRules([...rules, { usage_metric_key: metricKey, unit_price: Number(unitPrice) }]);
  };

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/price-books`, { currency, rules });
      setRules([]);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create price book.");
    }
  };

  return (
    <div className="mt-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Draft a new price book</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Currency" value={currency} onChange={(e) => setCurrency(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <div className="flex gap-2">
          <select value={metricKey} onChange={(e) => setMetricKey(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
            {USAGE_METRIC_KEYS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <input placeholder="Unit price" type="number" min={0} step="0.0001" value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)}
            className="w-28 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
          <button onClick={addRule} className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700">Add rule</button>
        </div>
        {rules.length > 0 && (
          <ul className="text-xs text-zinc-500">
            {rules.map((r, i) => <li key={i}>{r.usage_metric_key}: {r.unit_price}</li>)}
          </ul>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={rules.length === 0} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Create draft price book
        </button>
      </div>
    </div>
  );
}

function AggregateUsageForm({ operatorId }: { operatorId: string }) {
  const [tenantId, setTenantId] = useState("");
  const [periodStart, setPeriodStart] = useState("2020-01-01T00:00:00Z");
  const [periodEnd, setPeriodEnd] = useState("2030-01-01T00:00:00Z");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const aggregate = async () => {
    setError(null);
    setDone(false);
    try {
      await api.post(`/api/v1/operators/${operatorId}/usage-aggregations`, {
        enterprise_tenant_id: tenantId, period_start: periodStart, period_end: periodEnd,
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to aggregate usage.");
    }
  };

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Aggregate usage for a tenant</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Enterprise tenant id" value={tenantId} onChange={(e) => setTenantId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <div className="flex gap-2">
          <input placeholder="Period start (RFC3339)" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
          <input placeholder="Period end (RFC3339)" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {done && <p className="text-sm text-emerald-600">Aggregated.</p>}
        <button onClick={aggregate} disabled={!tenantId} className="self-start rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium disabled:opacity-50 dark:border-zinc-700">
          Aggregate now
        </button>
      </div>
    </div>
  );
}

function GenerateInvoiceForm({ operatorId, canManage, onGenerated }: { operatorId: string; canManage: boolean; onGenerated: () => void }) {
  const [tenantId, setTenantId] = useState("");
  const [periodStart, setPeriodStart] = useState("2020-01-01T00:00:00Z");
  const [periodEnd, setPeriodEnd] = useState("2030-01-01T00:00:00Z");
  const [taxAmount, setTaxAmount] = useState("0");
  const [error, setError] = useState<string | null>(null);

  if (!canManage) return null;

  const generate = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/invoices`, {
        enterprise_tenant_id: tenantId, period_start: periodStart, period_end: periodEnd, tax_amount: Number(taxAmount),
      });
      onGenerated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate invoice.");
    }
  };

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Generate an invoice</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Enterprise tenant id" value={tenantId} onChange={(e) => setTenantId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        <div className="flex gap-2">
          <input placeholder="Period start (RFC3339)" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
          <input placeholder="Period end (RFC3339)" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        </div>
        <input placeholder="Tax amount" type="number" min={0} step="0.01" value={taxAmount} onChange={(e) => setTaxAmount(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={generate} disabled={!tenantId} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Generate invoice
        </button>
      </div>
    </div>
  );
}

function CreateSettlementForm({ operatorId, onCreated }: { operatorId: string; onCreated: () => void }) {
  const [periodStart, setPeriodStart] = useState("2020-01-01T00:00:00Z");
  const [periodEnd, setPeriodEnd] = useState("2030-01-01T00:00:00Z");
  const [feeRate, setFeeRate] = useState("0.10");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/settlements`, {
        period_start: periodStart, period_end: periodEnd, platform_fee_rate: Number(feeRate),
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create settlement.");
    }
  };

  return (
    <div className="mb-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Create a settlement</h3>
      <div className="flex flex-col gap-2">
        <div className="flex gap-2">
          <input placeholder="Period start (RFC3339)" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
          <input placeholder="Period end (RFC3339)" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        </div>
        <input placeholder="Platform fee rate (0-1)" type="number" min={0} max={1} step="0.01" value={feeRate} onChange={(e) => setFeeRate(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-white dark:text-zinc-900">
          Create settlement
        </button>
      </div>
    </div>
  );
}

function SettlementRow({ operatorId, settlement, canManage, onChanged }: { operatorId: string; settlement: SettlementRecord; canManage: boolean; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);

  const reconcile = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/settlements/${settlement.id}/reconcile`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to reconcile settlement.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span>{settlement.currency} {settlement.gross_amount.toFixed(2)} gross / {settlement.net_amount.toFixed(2)} net</span>
        <span className="text-zinc-500">{settlement.status}</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {new Date(settlement.period_start).toLocaleDateString()} &ndash; {new Date(settlement.period_end).toLocaleDateString()}
      </p>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {canManage && settlement.status === "pending" && (
        <button onClick={reconcile} className="mt-2 text-xs underline">Reconcile</button>
      )}
    </li>
  );
}

function DisputeRow({ operatorId, dispute, canManage, onChanged }: { operatorId: string; dispute: BillingDispute; canManage: boolean; onChanged: () => void }) {
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const resolve = async (status: string) => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/billing-disputes/${dispute.id}/resolve`, { status, resolution_note: note });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to resolve dispute.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span>{dispute.reason}</span>
        <span className={dispute.status === "open" ? "text-amber-600" : "text-zinc-500"}>{dispute.status}</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">Opened {new Date(dispute.opened_at).toLocaleString()}</p>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      {canManage && (dispute.status === "open" || dispute.status === "under_review") && (
        <div className="mt-2 flex flex-col gap-2">
          <input placeholder="Resolution note" value={note} onChange={(e) => setNote(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-xs dark:border-zinc-700 dark:bg-zinc-900" />
          <div className="flex gap-3">
            <button onClick={() => resolve("resolved")} className="text-xs underline">Resolve</button>
            <button onClick={() => resolve("rejected")} className="text-xs text-red-600 underline">Reject</button>
          </div>
        </div>
      )}
    </li>
  );
}
