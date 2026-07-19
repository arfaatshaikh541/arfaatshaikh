"use client";

import { Banner, Button, Card } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "@/lib/api";
import type {
  CheckoutSessionResponse,
  CreditTransaction,
  Invoice,
  InvoiceListResponse,
  PlanListResponse,
  PortalSessionResponse,
  Subscription,
  WalletBalance,
} from "@/lib/types";

function PlanCard({
  planKey,
  name,
  description,
  monthlyPriceUsd,
  monthlyCreditGrant,
  checkoutAvailable,
  isCurrentPlan,
  onUpgrade,
  isStartingCheckout,
}: {
  planKey: string;
  name: string;
  description: string;
  monthlyPriceUsd: number;
  monthlyCreditGrant: number;
  checkoutAvailable: boolean;
  isCurrentPlan: boolean;
  onUpgrade: (planKey: string) => void;
  isStartingCheckout: boolean;
}) {
  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-medium">{name}</h3>
        {isCurrentPlan && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            Current plan
          </span>
        )}
      </div>
      <p className="mt-1 text-2xl font-semibold">
        ${monthlyPriceUsd.toLocaleString()}
        <span className="text-sm font-normal text-slate-500 dark:text-slate-400">/mo</span>
      </p>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{description}</p>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        {monthlyCreditGrant.toLocaleString()} credits/month
      </p>
      {!isCurrentPlan && (
        <Button
          className="mt-4"
          variant={checkoutAvailable ? "primary" : "ghost"}
          disabled={!checkoutAvailable}
          isLoading={isStartingCheckout}
          onClick={() => onUpgrade(planKey)}
        >
          {checkoutAvailable ? "Upgrade" : "Not yet available"}
        </Button>
      )}
    </Card>
  );
}

function InvoiceHistory() {
  const invoicesQuery = useQuery<InvoiceListResponse>({
    queryKey: ["invoices"],
    queryFn: () => api.get<InvoiceListResponse>("/billing/invoices"),
    retry: false,
  });
  if (invoicesQuery.isError) return null;
  const invoices = invoicesQuery.data?.invoices ?? [];

  return (
    <Card>
      <h2 className="mb-4 text-lg font-medium">Invoice history</h2>
      {invoices.length > 0 ? (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
              <th className="py-2 font-medium">Status</th>
              <th className="py-2 font-medium">Amount</th>
              <th className="py-2 font-medium">Period</th>
              <th className="py-2 font-medium">Invoice</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {invoices.map((invoice: Invoice) => (
              <tr key={invoice.id}>
                <td className="py-2 capitalize">{invoice.status}</td>
                <td className="py-2">
                  {invoice.amount_paid.toLocaleString(undefined, {
                    style: "currency",
                    currency: invoice.currency.toUpperCase(),
                  })}
                </td>
                <td className="py-2 text-slate-500 dark:text-slate-400">
                  {invoice.period_start ? new Date(invoice.period_start).toLocaleDateString() : "—"}
                  {invoice.period_end ? ` – ${new Date(invoice.period_end).toLocaleDateString()}` : ""}
                </td>
                <td className="py-2">
                  {invoice.hosted_invoice_url ? (
                    <a
                      href={invoice.hosted_invoice_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-slate-700 underline hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-100"
                    >
                      View
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-sm text-slate-500 dark:text-slate-400">No invoices yet.</p>
      )}
    </Card>
  );
}

export default function UsagePage() {
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [startingCheckoutFor, setStartingCheckoutFor] = useState<string | null>(null);
  const [openingPortal, setOpeningPortal] = useState(false);

  const walletQuery = useQuery<WalletBalance>({
    queryKey: ["wallet"],
    queryFn: () => api.get<WalletBalance>("/usage/wallet"),
  });
  const transactionsQuery = useQuery<CreditTransaction[]>({
    queryKey: ["transactions"],
    queryFn: () => api.get<CreditTransaction[]>("/usage/transactions"),
  });
  const subscriptionQuery = useQuery<Subscription>({
    queryKey: ["subscription"],
    queryFn: () => api.get<Subscription>("/billing/subscription"),
    retry: false,
  });
  const plansQuery = useQuery<PlanListResponse>({
    queryKey: ["billing-plans"],
    queryFn: () => api.get<PlanListResponse>("/billing/plans"),
    retry: false,
  });

  const handleUpgrade = async (planKey: string) => {
    setCheckoutError(null);
    setStartingCheckoutFor(planKey);
    try {
      const result = await api.post<CheckoutSessionResponse>("/billing/checkout-session", {
        plan_key: planKey,
      });
      window.location.href = result.checkout_url;
    } catch (err) {
      setCheckoutError(err instanceof ApiError ? err.message : "Could not start checkout.");
      setStartingCheckoutFor(null);
    }
  };

  const handleManageBilling = async () => {
    setCheckoutError(null);
    setOpeningPortal(true);
    try {
      const result = await api.post<PortalSessionResponse>("/billing/portal-session");
      window.location.href = result.portal_url;
    } catch (err) {
      setCheckoutError(err instanceof ApiError ? err.message : "Could not open the billing portal.");
    } finally {
      setOpeningPortal(false);
    }
  };

  if (walletQuery.isError) {
    return <Banner tone="info">You don&apos;t have permission to view usage and billing.</Banner>;
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Usage &amp; Billing</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">Wallet balance</p>
          <p className="mt-1 text-2xl font-semibold">{walletQuery.data?.balance.toLocaleString() ?? "—"}</p>
        </Card>
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">Available (after reservations)</p>
          <p className="mt-1 text-2xl font-semibold">{walletQuery.data?.available.toLocaleString() ?? "—"}</p>
        </Card>
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">Plan</p>
          <p className="mt-1 text-2xl font-semibold">{subscriptionQuery.data?.plan_name ?? "—"}</p>
          {!subscriptionQuery.isError && (
            <Button
              variant="ghost"
              className="mt-2"
              isLoading={openingPortal}
              onClick={handleManageBilling}
            >
              Manage billing
            </Button>
          )}
        </Card>
      </div>

      {checkoutError && <Banner tone="error">{checkoutError}</Banner>}

      {!plansQuery.isError && plansQuery.data && plansQuery.data.plans.length > 0 && (
        <div>
          <h2 className="mb-3 text-lg font-medium">Plans</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {plansQuery.data.plans.map((plan) => (
              <PlanCard
                key={plan.key}
                planKey={plan.key}
                name={plan.name}
                description={plan.description}
                monthlyPriceUsd={plan.monthly_price_usd}
                monthlyCreditGrant={plan.monthly_credit_grant}
                checkoutAvailable={plan.checkout_available}
                isCurrentPlan={subscriptionQuery.data?.plan_key === plan.key}
                onUpgrade={handleUpgrade}
                isStartingCheckout={startingCheckoutFor === plan.key}
              />
            ))}
          </div>
        </div>
      )}

      <InvoiceHistory />

      <Card>
        <h2 className="mb-4 text-lg font-medium">Credit history</h2>
        {transactionsQuery.data && transactionsQuery.data.length > 0 ? (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
                <th className="py-2 font-medium">Type</th>
                <th className="py-2 font-medium">Amount</th>
                <th className="py-2 font-medium">Reference</th>
                <th className="py-2 font-medium">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {transactionsQuery.data.map((txn) => (
                <tr key={txn.id}>
                  <td className="py-2 capitalize">{txn.type.replace(/_/g, " ")}</td>
                  <td className={`py-2 ${txn.amount < 0 ? "text-red-600" : "text-green-600"}`}>
                    {txn.amount > 0 ? "+" : ""}
                    {txn.amount.toLocaleString()}
                  </td>
                  <td className="py-2 text-slate-500 dark:text-slate-400">{txn.reference ?? "—"}</td>
                  <td className="py-2 text-slate-500 dark:text-slate-400">
                    {new Date(txn.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">No credit activity yet.</p>
        )}
      </Card>
    </div>
  );
}
