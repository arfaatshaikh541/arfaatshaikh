"use client";

import { Alert, Badge, Button, Card } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { ApiError, apiFetch } from "@/lib/api-client";
import type { AppointmentListOut, AppointmentOut, MemberOut } from "@/lib/types";

const STATUS_TONE: Record<string, "success" | "warning" | "neutral" | "danger" | "accent"> = {
  scheduled: "neutral",
  confirmed: "accent",
  completed: "success",
  cancelled: "danger",
  no_show: "warning",
};

export default function AppointmentsPage() {
  const { tenantId } = useCurrentTenant();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [serverError, setServerError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [cancelReason, setCancelReason] = useState("");

  const appointmentsQuery = useQuery({
    queryKey: ["appointments", tenantId, statusFilter],
    queryFn: () =>
      apiFetch<AppointmentListOut>(
        `/tenants/me/appointments?page_size=100${statusFilter ? `&status=${statusFilter}` : ""}`
      ),
    enabled: Boolean(tenantId),
  });
  const membersQuery = useQuery({
    queryKey: ["members", tenantId],
    queryFn: () => apiFetch<MemberOut[]>("/tenants/me/members"),
    enabled: Boolean(tenantId),
  });
  const membersById = new Map((membersQuery.data ?? []).map((m) => [m.id, m]));

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["appointments", tenantId] });

  const confirmMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch<AppointmentOut>(`/tenants/me/appointments/${id}/confirm`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const completeMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch<AppointmentOut>(`/tenants/me/appointments/${id}/complete`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const noShowMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch<AppointmentOut>(`/tenants/me/appointments/${id}/no-show`, { method: "POST" }),
    onSuccess: invalidate,
  });
  const cancelMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      apiFetch<AppointmentOut>(`/tenants/me/appointments/${id}/cancel`, {
        method: "POST",
        body: { reason },
      }),
    onSuccess: () => {
      setCancellingId(null);
      setCancelReason("");
      invalidate();
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const items = appointmentsQuery.data?.items ?? [];

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Appointments</h1>
      <p className="mb-6 text-sm text-surface-400">
        Book new appointments from a lead&apos;s detail page. This view manages the lifecycle of
        every appointment across the workspace.
      </p>

      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}

      <Card>
        <div className="mb-4 flex items-center gap-3">
          <h2 className="text-sm font-semibold text-surface-100">All appointments</h2>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-surface-700 bg-surface-900 px-2 py-1 text-sm text-surface-100"
          >
            <option value="">All statuses</option>
            <option value="scheduled">Scheduled</option>
            <option value="confirmed">Confirmed</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="no_show">No-show</option>
          </select>
        </div>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-800 text-surface-500">
              <th className="pb-2 font-medium">When</th>
              <th className="pb-2 font-medium">Lead</th>
              <th className="pb-2 font-medium">With</th>
              <th className="pb-2 font-medium">Status</th>
              <th className="pb-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => {
              const assignee = a.assigned_membership_id ? membersById.get(a.assigned_membership_id) : null;
              return (
                <tr key={a.id} className="border-b border-surface-900 align-top">
                  <td className="py-2 text-surface-200">
                    {new Date(a.starts_at).toLocaleString()}
                  </td>
                  <td className="py-2 text-surface-400">
                    <Link href={`/leads/${a.lead_id}`} className="text-accent-500 hover:text-accent-400">
                      View lead
                    </Link>
                  </td>
                  <td className="py-2 text-surface-400">
                    {assignee ? `${assignee.first_name} ${assignee.last_name}` : "Unassigned"}
                  </td>
                  <td className="py-2">
                    <Badge tone={STATUS_TONE[a.status] ?? "neutral"}>{a.status}</Badge>
                  </td>
                  <td className="py-2">
                    {a.status === "scheduled" ? (
                      <Button variant="ghost" onClick={() => confirmMutation.mutate(a.id)}>
                        Confirm
                      </Button>
                    ) : null}
                    {["scheduled", "confirmed"].includes(a.status) ? (
                      <>
                        <Button variant="ghost" onClick={() => completeMutation.mutate(a.id)}>
                          Complete
                        </Button>
                        <Button variant="ghost" onClick={() => noShowMutation.mutate(a.id)}>
                          No-show
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => {
                            setServerError(null);
                            setCancellingId(a.id);
                          }}
                        >
                          Cancel
                        </Button>
                      </>
                    ) : null}
                    {cancellingId === a.id ? (
                      <div className="mt-2 flex items-center gap-2">
                        <input
                          className="rounded-md border border-surface-700 bg-surface-900 px-2 py-1 text-xs text-surface-50"
                          placeholder="Cancellation reason"
                          value={cancelReason}
                          onChange={(e) => setCancelReason(e.target.value)}
                        />
                        <Button
                          variant="secondary"
                          loading={cancelMutation.isPending}
                          onClick={() => cancelMutation.mutate({ id: a.id, reason: cancelReason })}
                        >
                          Confirm cancel
                        </Button>
                      </div>
                    ) : null}
                  </td>
                </tr>
              );
            })}
            {items.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-4 text-center text-surface-500">
                  No appointments yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
