"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type EnterpriseMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface UsageAggregation {
  id: string;
  usage_metric_key: string;
  period_start: string;
  period_end: string;
  total_quantity: number;
  source_event_count: number;
}

interface QuoteLineItem {
  usage_metric_key: string;
  quantity: number;
  unit_price: number;
  amount: number;
}

interface Quote {
  id: string;
  operator_id: string;
  line_items: QuoteLineItem[];
  estimated_total: number;
  currency: string;
  created_at: string;
}

interface Budget {
  id: string;
  name: string;
  period_days: number;
  threshold_amount: number;
  currency: string;
  hard_limit: boolean;
  status: string;
}

interface Invoice {
  id: string;
  operator_id: string;
  total: number;
  currency: string;
  status: string;
  issued_at: string;
}

interface CreditNote {
  id: string;
  invoice_id: string;
  amount: number;
  reason: string;
  status: string;
  created_at: string;
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
// server-side usage.view / billing.view / budgets.manage / billing.dispute
// permissions -- a UX convenience only, re-checked independently by
// control-api on every request.
const CAN_VIEW_USAGE = new Set(["enterprise_owner", "enterprise_admin", "finops_manager", "application_owner"]);
const CAN_VIEW_BILLING = new Set(["enterprise_owner", "enterprise_admin", "finops_manager"]);
const CAN_MANAGE_BUDGETS = new Set(["enterprise_owner", "enterprise_admin", "finops_manager", "ai_platform_engineer", "devops_engineer"]);
const CAN_DISPUTE = new Set(["enterprise_owner", "enterprise_admin", "finops_manager", "compliance_manager"]);

export default function EnterpriseBillingPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["tenant-members", tenantId],
    queryFn: () => api.get<EnterpriseMembership[]>(`/api/v1/enterprises/${tenantId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const canViewUsage = CAN_VIEW_USAGE.has(myRole);
  const canViewBilling = CAN_VIEW_BILLING.has(myRole);
  const canManageBudgets = CAN_MANAGE_BUDGETS.has(myRole);
  const canDispute = CAN_DISPUTE.has(myRole);

  const aggregations = useQuery({
    queryKey: ["usage-aggregations", tenantId],
    queryFn: () => api.get<UsageAggregation[]>(`/api/v1/enterprises/${tenantId}/usage-aggregations`),
    enabled: canViewUsage,
  });
  const quotes = useQuery({
    queryKey: ["quotes", tenantId],
    queryFn: () => api.get<Quote[]>(`/api/v1/enterprises/${tenantId}/quotes`),
    enabled: canViewBilling,
  });
  const budgets = useQuery({
    queryKey: ["budgets", tenantId],
    queryFn: () => api.get<Budget[]>(`/api/v1/enterprises/${tenantId}/budgets`),
    enabled: canManageBudgets,
  });
  const invoices = useQuery({
    queryKey: ["invoices", tenantId],
    queryFn: () => api.get<Invoice[]>(`/api/v1/enterprises/${tenantId}/invoices`),
    enabled: canViewBilling,
  });
  const creditNotes = useQuery({
    queryKey: ["credit-notes", tenantId],
    queryFn: () => api.get<CreditNote[]>(`/api/v1/enterprises/${tenantId}/credit-notes`),
    enabled: canViewBilling,
  });
  const disputes = useQuery({
    queryKey: ["billing-disputes", tenantId],
    queryFn: () => api.get<BillingDispute[]>(`/api/v1/enterprises/${tenantId}/billing-disputes`),
    enabled: canViewBilling,
  });

  const invalidate = (key: string) => queryClient.invalidateQueries({ queryKey: [key, tenantId] });

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
        <p>You do not have access to this tenant&apos;s billing data.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
      <Link href={`/dashboard/enterprise/${tenantId}`} className="text-sm underline"><span aria-hidden="true" className="rtl-mirror">&larr;</span> Tenant overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Usage, billing &amp; settlement</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Quotes and invoices below are always priced server-side against the chosen operator&apos;s
        active price book -- this page never supplies a price itself.
      </p>

      {canViewUsage && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Usage (aggregated)</h2>
          <ul className="flex flex-col gap-1 text-sm">
            {aggregations.data?.map((a) => (
              <li key={a.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                {a.usage_metric_key}: {a.total_quantity} ({a.source_event_count} event(s)) &middot;{" "}
                {new Date(a.period_start).toLocaleDateString()} &ndash; {new Date(a.period_end).toLocaleDateString()}
              </li>
            ))}
            {aggregations.data?.length === 0 && <li className="text-zinc-500">No aggregated usage yet.</li>}
          </ul>
        </section>
      )}

      {canViewBilling && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Quotes</h2>
          <ul className="mb-3 flex flex-col gap-2 text-sm">
            {quotes.data?.map((q) => (
              <li key={q.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                <div className="flex items-center justify-between flex-wrap gap-1">
                  <span>{q.currency} {q.estimated_total.toFixed(2)}</span>
                  <span className="text-xs text-zinc-500">{new Date(q.created_at).toLocaleDateString()}</span>
                </div>
                <ul className="mt-1 text-xs text-zinc-500">
                  {q.line_items.map((li, i) => <li key={i}>{li.usage_metric_key}: {li.quantity} &times; {li.unit_price} = {li.amount}</li>)}
                </ul>
              </li>
            ))}
            {quotes.data?.length === 0 && <li className="text-zinc-500">No quotes requested yet.</li>}
          </ul>
          <CreateQuoteForm tenantId={tenantId} onCreated={() => invalidate("quotes")} />
        </section>
      )}

      {canManageBudgets && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Budgets</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {budgets.data?.map((b) => (
              <BudgetRow key={b.id} tenantId={tenantId} budget={b} onChanged={() => invalidate("budgets")} />
            ))}
            {budgets.data?.length === 0 && <li className="text-zinc-500">No budgets defined yet.</li>}
          </ul>
          <CreateBudgetForm tenantId={tenantId} onCreated={() => invalidate("budgets")} />
        </section>
      )}

      {canViewBilling && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Invoices</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {invoices.data?.map((inv) => (
              <InvoiceRow key={inv.id} tenantId={tenantId} invoice={inv} canDispute={canDispute}
                onChanged={() => { invalidate("invoices"); invalidate("billing-disputes"); }} />
            ))}
            {invoices.data?.length === 0 && <li className="text-zinc-500">No invoices issued yet.</li>}
          </ul>
        </section>
      )}

      {canViewBilling && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Credit notes</h2>
          <ul className="flex flex-col gap-1 text-sm">
            {creditNotes.data?.map((cn) => (
              <li key={cn.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                <div className="flex items-center justify-between flex-wrap gap-1">
                  <span>{cn.amount.toFixed(2)} &middot; {cn.reason}</span>
                  <span className="text-zinc-500">{cn.status}</span>
                </div>
              </li>
            ))}
            {creditNotes.data?.length === 0 && <li className="text-zinc-500">No credit notes issued yet.</li>}
          </ul>
        </section>
      )}

      {canViewBilling && (
        <section>
          <h2 className="mb-3 text-lg font-medium">Billing disputes</h2>
          <ul className="flex flex-col gap-1 text-sm">
            {disputes.data?.map((d) => (
              <li key={d.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                <div className="flex items-center justify-between flex-wrap gap-1">
                  <span>{d.reason}</span>
                  <span className={d.status === "open" ? "text-amber-600" : "text-zinc-500"}>{d.status}</span>
                </div>
                <p className="mt-1 text-xs text-zinc-500">Opened {new Date(d.opened_at).toLocaleString()}</p>
              </li>
            ))}
            {disputes.data?.length === 0 && <li className="text-zinc-500">No disputes on record.</li>}
          </ul>
        </section>
      )}
    </main>
  );
}

function CreateQuoteForm({ tenantId, onCreated }: { tenantId: string; onCreated: () => void }) {
  const [operatorId, setOperatorId] = useState("");
  const [metricKey, setMetricKey] = useState(USAGE_METRIC_KEYS[0]);
  const [quantity, setQuantity] = useState("1");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/quotes`, {
        operator_id: operatorId, items: [{ usage_metric_key: metricKey, quantity: Number(quantity) }],
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create quote.");
    }
  };

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Request a quote</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Operator id" value={operatorId} onChange={(e) => setOperatorId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Operator id" />
        <div className="flex gap-2 flex-wrap">
          <select aria-label="Usage metric" value={metricKey} onChange={(e) => setMetricKey(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
            {USAGE_METRIC_KEYS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <input placeholder="Quantity" type="number" min={0} value={quantity} onChange={(e) => setQuantity(e.target.value)}
            className="w-28 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Quantity" />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!operatorId} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Get quote
        </button>
      </div>
    </div>
  );
}

function BudgetRow({ tenantId, budget, onChanged }: { tenantId: string; budget: Budget; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);

  const archive = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/budgets/${budget.id}/archive`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to archive budget.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between flex-wrap gap-1">
        <span className="font-medium">{budget.name}</span>
        <span className="text-zinc-500">{budget.status}</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {budget.currency} {budget.threshold_amount} over {budget.period_days}d {budget.hard_limit ? "(hard limit)" : ""}
      </p>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      {budget.status === "active" && (
        <button onClick={archive} className="mt-2 text-xs text-red-600 underline">Archive</button>
      )}
    </li>
  );
}

function CreateBudgetForm({ tenantId, onCreated }: { tenantId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [periodDays, setPeriodDays] = useState("30");
  const [thresholdAmount, setThresholdAmount] = useState("1000");
  const [currency, setCurrency] = useState("USD");
  const [hardLimit, setHardLimit] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/budgets`, {
        name, period_days: Number(periodDays), threshold_amount: Number(thresholdAmount), currency, hard_limit: hardLimit,
      });
      setName("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create budget.");
    }
  };

  return (
    <div className="mt-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Define a new budget</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Name" />
        <div className="flex gap-2 flex-wrap">
          <input placeholder="Threshold amount" type="number" min={0} value={thresholdAmount} onChange={(e) => setThresholdAmount(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Threshold amount" />
          <input placeholder="Currency" value={currency} onChange={(e) => setCurrency(e.target.value)}
            className="w-24 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Currency" />
        </div>
        <input placeholder="Period (days)" type="number" min={1} value={periodDays} onChange={(e) => setPeriodDays(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Period (days)" />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={hardLimit} onChange={(e) => setHardLimit(e.target.checked)} />
          Hard limit
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!name} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Create budget
        </button>
      </div>
    </div>
  );
}

function InvoiceRow({ tenantId, invoice, canDispute, onChanged }: { tenantId: string; invoice: Invoice; canDispute: boolean; onChanged: () => void }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [disputing, setDisputing] = useState(false);

  const openDispute = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/billing-disputes`, { invoice_id: invoice.id, reason });
      setDisputing(false);
      setReason("");
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to open dispute.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
      <div className="flex items-center justify-between flex-wrap gap-1">
        <span>{invoice.currency} {invoice.total.toFixed(2)}</span>
        <span className={invoice.status === "disputed" ? "text-red-600" : "text-zinc-500"}>{invoice.status}</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">Issued {new Date(invoice.issued_at).toLocaleString()}</p>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      {canDispute && invoice.status === "issued" && !disputing && (
        <button onClick={() => setDisputing(true)} className="mt-2 text-xs text-red-600 underline">Dispute</button>
      )}
      {disputing && (
        <div className="mt-2 flex flex-col gap-2">
          <input placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Reason" />
          <div className="flex gap-3 flex-wrap">
            <button onClick={openDispute} disabled={!reason} className="text-xs text-red-600 underline disabled:opacity-50">Submit dispute</button>
            <button onClick={() => setDisputing(false)} className="text-xs underline">Cancel</button>
          </div>
        </div>
      )}
    </li>
  );
}
