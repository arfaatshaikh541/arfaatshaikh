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
  enterprise_tenant_id?: string;
  bilateral_agreement_id?: string;
  period_start: string;
  period_end: string;
  gross_amount: number;
  net_amount: number;
  currency: string;
  status: string;
}

interface BilateralAgreement {
  id: string;
  enterprise_tenant_id: string;
  status: string;
  currency: string;
  platform_fee_rate: number;
}

interface BillingDispute {
  id: string;
  invoice_id: string;
  reason: string;
  status: string;
  opened_at: string;
}

interface Adjustment {
  id: string;
  invoice_id?: string;
  settlement_id?: string;
  operator_id: string;
  enterprise_tenant_id?: string;
  amount: number;
  reason: string;
  created_at: string;
}

interface CreditNote {
  id: string;
  invoice_id: string;
  enterprise_tenant_id: string;
  operator_id: string;
  amount: number;
  reason: string;
  status: string;
  created_at: string;
  applied_at?: string;
}

interface BillingProviderEvent {
  id: string;
  invoice_id?: string;
  settlement_id?: string;
  provider_type: string;
  event_type: string;
  external_ref?: string;
  occurred_at: string;
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
  const agreements = useQuery({
    queryKey: ["operator-bilateral-agreements", operatorId],
    queryFn: () => api.get<BilateralAgreement[]>(`/api/v1/operators/${operatorId}/bilateral-agreements`),
    enabled: canViewSettlements,
  });
  const creditNotes = useQuery({
    queryKey: ["operator-credit-notes", operatorId],
    queryFn: () => api.get<CreditNote[]>(`/api/v1/operators/${operatorId}/credit-notes`),
    enabled: canViewSettlements,
  });

  const invalidate = (key: string) => queryClient.invalidateQueries({ queryKey: [key, operatorId] });

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not have access to this operator&apos;s billing data.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-8">
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
          <ul className="mt-3 flex flex-col gap-2 text-sm">
            {invoices.data?.map((inv) => (
              <InvoiceRow key={inv.id} operatorId={operatorId} invoice={inv} canManage={canManageSettlements} onChanged={() => invalidate("operator-invoices")} />
            ))}
            {invoices.data?.length === 0 && <li className="text-zinc-500">No invoices issued yet.</li>}
          </ul>
        </section>
      )}

      {canViewSettlements && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Credit notes</h2>
          {canManageSettlements && (
            <CreateCreditNoteForm operatorId={operatorId} onCreated={() => { invalidate("operator-credit-notes"); invalidate("operator-invoices"); }} />
          )}
          <ul className="mt-3 flex flex-col gap-1 text-sm">
            {creditNotes.data?.map((cn) => (
              <li key={cn.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <span>{cn.amount.toFixed(2)} &middot; {cn.reason}</span>
                  <span className="text-zinc-500">{cn.status}</span>
                </div>
                <p className="mt-1 text-xs text-zinc-500">
                  Invoice {cn.invoice_id.slice(0, 8)}&hellip; &middot; issued {new Date(cn.created_at).toLocaleString()}
                  {cn.applied_at && <> &middot; applied {new Date(cn.applied_at).toLocaleString()}</>}
                </p>
              </li>
            ))}
            {creditNotes.data?.length === 0 && <li className="text-zinc-500">No credit notes issued yet.</li>}
          </ul>
        </section>
      )}

      {canViewSettlements && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Settlements</h2>
          {canManageSettlements && (
            <div className="flex flex-col gap-3">
              <CreateSettlementForm operatorId={operatorId} onCreated={() => invalidate("operator-settlements")} />
              <CreateSettlementForAgreementForm operatorId={operatorId} agreements={agreements.data} onCreated={() => invalidate("operator-settlements")} />
            </div>
          )}
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
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Currency" />
        <div className="flex gap-2">
          <select aria-label="Usage metric" value={metricKey} onChange={(e) => setMetricKey(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
            {USAGE_METRIC_KEYS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <input placeholder="Unit price" type="number" min={0} step="0.0001" value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)}
            className="w-28 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Unit price" />
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
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Enterprise tenant id" />
        <div className="flex gap-2">
          <input placeholder="Period start (RFC3339)" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Period start (RFC3339)" />
          <input placeholder="Period end (RFC3339)" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Period end (RFC3339)" />
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
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Enterprise tenant id" />
        <div className="flex gap-2">
          <input placeholder="Period start (RFC3339)" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Period start (RFC3339)" />
          <input placeholder="Period end (RFC3339)" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Period end (RFC3339)" />
        </div>
        <input placeholder="Tax amount" type="number" min={0} step="0.01" value={taxAmount} onChange={(e) => setTaxAmount(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Tax amount" />
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
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Period start (RFC3339)" />
          <input placeholder="Period end (RFC3339)" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Period end (RFC3339)" />
        </div>
        <input placeholder="Platform fee rate (0-1)" type="number" min={0} max={1} step="0.01" value={feeRate} onChange={(e) => setFeeRate(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Platform fee rate (0-1)" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-white dark:text-zinc-900">
          Create settlement
        </button>
      </div>
    </div>
  );
}

// CreateSettlementForAgreementForm creates a settlement scoped to exactly
// one bilateral agreement's own tenant, priced at that agreement's own
// contracted platform fee rate -- there is deliberately no fee-rate input
// here, since the server always reads it from the agreement itself, never
// from this request.
function CreateSettlementForAgreementForm({ operatorId, agreements, onCreated }: { operatorId: string; agreements: BilateralAgreement[] | undefined; onCreated: () => void }) {
  const [agreementId, setAgreementId] = useState("");
  const [periodStart, setPeriodStart] = useState("2020-01-01T00:00:00Z");
  const [periodEnd, setPeriodEnd] = useState("2030-01-01T00:00:00Z");
  const [error, setError] = useState<string | null>(null);

  const activeAgreements = agreements?.filter((a) => a.status === "active") ?? [];
  if (activeAgreements.length === 0) return null;

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/settlements/for-agreement`, {
        bilateral_agreement_id: agreementId, period_start: periodStart, period_end: periodEnd,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create settlement for agreement.");
    }
  };

  return (
    <div className="mb-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Create a settlement for a bilateral agreement</h3>
      <p className="mb-2 text-xs text-zinc-500">
        Scoped to exactly that agreement&apos;s tenant, priced at its own contracted platform fee
        rate -- there is no fee-rate field here because the server never accepts one for this path.
      </p>
      <div className="flex flex-col gap-2">
        <select aria-label="Bilateral agreement" value={agreementId} onChange={(e) => setAgreementId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Select an agreement</option>
          {activeAgreements.map((a) => (
            <option key={a.id} value={a.id}>tenant {a.enterprise_tenant_id.slice(0, 8)}&hellip; ({(a.platform_fee_rate * 100).toFixed(1)}% fee)</option>
          ))}
        </select>
        <div className="flex gap-2">
          <input placeholder="Period start (RFC3339)" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Period start (RFC3339)" />
          <input placeholder="Period end (RFC3339)" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Period end (RFC3339)" />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!agreementId} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Create settlement for agreement
        </button>
      </div>
    </div>
  );
}

function SettlementRow({ operatorId, settlement, canManage, onChanged }: { operatorId: string; settlement: SettlementRecord; canManage: boolean; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const queryClient = useQueryClient();

  const adjustments = useQuery({
    queryKey: ["settlement-adjustments", settlement.id],
    queryFn: () => api.get<Adjustment[]>(`/api/v1/operators/${operatorId}/settlements/${settlement.id}/adjustments`),
    enabled: detailsOpen,
  });
  const providerEvents = useQuery({
    queryKey: ["settlement-provider-events", settlement.id],
    queryFn: () => api.get<BillingProviderEvent[]>(`/api/v1/operators/${operatorId}/settlements/${settlement.id}/provider-events`),
    enabled: detailsOpen,
  });

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
        {settlement.bilateral_agreement_id && <> &middot; from bilateral agreement (tenant {settlement.enterprise_tenant_id?.slice(0, 8)}&hellip;)</>}
      </p>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="mt-2 flex gap-3">
        {canManage && settlement.status === "pending" && (
          <button onClick={reconcile} className="text-xs underline">Reconcile</button>
        )}
        <button onClick={() => setDetailsOpen((v) => !v)} className="text-xs underline">
          {detailsOpen ? "Hide details" : "Adjustments & provider events"}
        </button>
      </div>
      {detailsOpen && (
        <div className="mt-3 flex flex-col gap-3 border-t border-zinc-200 pt-3 dark:border-zinc-800">
          <div>
            <h4 className="mb-1 text-xs font-medium text-zinc-500">Adjustments</h4>
            <ul className="flex flex-col gap-1 text-xs">
              {adjustments.data?.map((a) => (
                <li key={a.id} className="rounded-md border border-zinc-200 px-3 py-1.5 dark:border-zinc-800">
                  {a.amount.toFixed(2)} &middot; {a.reason}
                </li>
              ))}
              {adjustments.data?.length === 0 && <li className="text-zinc-500">No adjustments recorded.</li>}
            </ul>
            {canManage && (
              <CreateAdjustmentForm
                operatorId={operatorId}
                settlementId={settlement.id}
                onCreated={() => queryClient.invalidateQueries({ queryKey: ["settlement-adjustments", settlement.id] })}
              />
            )}
          </div>
          <div>
            <h4 className="mb-1 text-xs font-medium text-zinc-500">Provider events</h4>
            <ul className="flex flex-col gap-1 text-xs">
              {providerEvents.data?.map((e) => (
                <li key={e.id} className="rounded-md border border-zinc-200 px-3 py-1.5 dark:border-zinc-800">
                  {e.provider_type} &middot; {e.event_type} &middot; {new Date(e.occurred_at).toLocaleString()}
                </li>
              ))}
              {providerEvents.data?.length === 0 && <li className="text-zinc-500">No provider events recorded.</li>}
            </ul>
          </div>
        </div>
      )}
    </li>
  );
}

function InvoiceRow({ operatorId, invoice, canManage, onChanged }: { operatorId: string; invoice: Invoice; canManage: boolean; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const queryClient = useQueryClient();

  const adjustments = useQuery({
    queryKey: ["invoice-adjustments", invoice.id],
    queryFn: () => api.get<Adjustment[]>(`/api/v1/operators/${operatorId}/invoices/${invoice.id}/adjustments`),
    enabled: detailsOpen,
  });
  const providerEvents = useQuery({
    queryKey: ["invoice-provider-events", invoice.id],
    queryFn: () => api.get<BillingProviderEvent[]>(`/api/v1/operators/${operatorId}/invoices/${invoice.id}/provider-events`),
    enabled: detailsOpen,
  });

  const markPaid = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/invoices/${invoice.id}/mark-paid`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to mark invoice paid.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between">
        <span>{invoice.currency} {invoice.total.toFixed(2)}</span>
        <span className={invoice.status === "disputed" ? "text-red-600" : "text-zinc-500"}>{invoice.status}</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">Issued {new Date(invoice.issued_at).toLocaleString()}</p>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      <div className="mt-2 flex gap-3">
        {canManage && invoice.status !== "paid" && invoice.status !== "void" && (
          <button onClick={markPaid} className="text-xs underline">Mark paid</button>
        )}
        <button onClick={() => setDetailsOpen((v) => !v)} className="text-xs underline">
          {detailsOpen ? "Hide details" : "Adjustments & provider events"}
        </button>
      </div>
      {detailsOpen && (
        <div className="mt-3 flex flex-col gap-3 border-t border-zinc-200 pt-3 dark:border-zinc-800">
          <div>
            <h4 className="mb-1 text-xs font-medium text-zinc-500">Adjustments</h4>
            <ul className="flex flex-col gap-1 text-xs">
              {adjustments.data?.map((a) => (
                <li key={a.id} className="rounded-md border border-zinc-200 px-3 py-1.5 dark:border-zinc-800">
                  {a.amount.toFixed(2)} &middot; {a.reason}
                </li>
              ))}
              {adjustments.data?.length === 0 && <li className="text-zinc-500">No adjustments recorded.</li>}
            </ul>
            {canManage && (
              <CreateAdjustmentForm
                operatorId={operatorId}
                invoiceId={invoice.id}
                onCreated={() => queryClient.invalidateQueries({ queryKey: ["invoice-adjustments", invoice.id] })}
              />
            )}
          </div>
          <div>
            <h4 className="mb-1 text-xs font-medium text-zinc-500">Provider events</h4>
            <ul className="flex flex-col gap-1 text-xs">
              {providerEvents.data?.map((e) => (
                <li key={e.id} className="rounded-md border border-zinc-200 px-3 py-1.5 dark:border-zinc-800">
                  {e.provider_type} &middot; {e.event_type} &middot; {new Date(e.occurred_at).toLocaleString()}
                </li>
              ))}
              {providerEvents.data?.length === 0 && <li className="text-zinc-500">No provider events recorded.</li>}
            </ul>
          </div>
        </div>
      )}
    </li>
  );
}

// CreateAdjustmentForm posts to the single shared POST /adjustments
// endpoint, scoping the adjustment to exactly one of an invoice or a
// settlement depending on which id the caller passes in.
function CreateAdjustmentForm({ operatorId, invoiceId, settlementId, onCreated }: { operatorId: string; invoiceId?: string; settlementId?: string; onCreated: () => void }) {
  const [amount, setAmount] = useState("0.00");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/adjustments`, {
        invoice_id: invoiceId, settlement_id: settlementId, amount: Number(amount), reason,
      });
      setReason("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create adjustment.");
    }
  };

  return (
    <div className="mt-2 flex flex-col gap-2">
      <div className="flex gap-2">
        <input placeholder="Amount" type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
          className="w-28 rounded-md border border-zinc-300 px-3 py-1.5 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Amount" />
        <input placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)}
          className="flex-1 rounded-md border border-zinc-300 px-3 py-1.5 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Reason" />
        <button onClick={create} disabled={!reason} className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium disabled:opacity-50 dark:border-zinc-700">
          Add adjustment
        </button>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}

function CreateCreditNoteForm({ operatorId, onCreated }: { operatorId: string; onCreated: () => void }) {
  const [invoiceId, setInvoiceId] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [amount, setAmount] = useState("0.00");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/credit-notes`, {
        invoice_id: invoiceId, enterprise_tenant_id: tenantId, amount: Number(amount), reason,
      });
      setReason("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create credit note.");
    }
  };

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Issue a credit note</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Invoice id" value={invoiceId} onChange={(e) => setInvoiceId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Invoice id" />
        <input placeholder="Enterprise tenant id" value={tenantId} onChange={(e) => setTenantId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Enterprise tenant id" />
        <div className="flex gap-2">
          <input placeholder="Amount" type="number" min={0} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
            className="w-32 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Amount" />
          <input placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Reason" />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!invoiceId || !tenantId || !reason} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Issue credit note
        </button>
      </div>
    </div>
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
            className="rounded-md border border-zinc-300 px-3 py-2 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Resolution note" />
          <div className="flex gap-3">
            <button onClick={() => resolve("resolved")} className="text-xs underline">Resolve</button>
            <button onClick={() => resolve("rejected")} className="text-xs text-red-600 underline">Reject</button>
          </div>
        </div>
      )}
    </li>
  );
}
