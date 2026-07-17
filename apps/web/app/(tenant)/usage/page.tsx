"use client";

import { Banner, Card } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CreditTransaction, Subscription, WalletBalance } from "@/lib/types";

export default function UsagePage() {
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
        </Card>
      </div>

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
