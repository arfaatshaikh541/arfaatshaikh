"use client";

import { Badge, Button } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { apiFetch } from "@/lib/api-client";
import type { NotificationOut } from "@/lib/types";

export function NotificationsBell() {
  const { tenantId } = useCurrentTenant();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const unreadQuery = useQuery({
    queryKey: ["notifications-unread-count", tenantId],
    queryFn: () => apiFetch<{ count: number }>("/tenants/me/notifications/unread-count"),
    enabled: Boolean(tenantId),
    refetchInterval: 60_000,
  });
  const notificationsQuery = useQuery({
    queryKey: ["notifications", tenantId],
    queryFn: () => apiFetch<NotificationOut[]>("/tenants/me/notifications"),
    enabled: Boolean(tenantId) && open,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["notifications", tenantId] });
    queryClient.invalidateQueries({ queryKey: ["notifications-unread-count", tenantId] });
  };

  const markReadMutation = useMutation({
    mutationFn: (notificationId: string) =>
      apiFetch(`/tenants/me/notifications/${notificationId}/read`, { method: "POST" }),
    onSuccess: invalidate,
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => apiFetch("/tenants/me/notifications/read-all", { method: "POST" }),
    onSuccess: invalidate,
  });

  const unreadCount = unreadQuery.data?.count ?? 0;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-md p-2 text-surface-300 hover:bg-surface-800 hover:text-surface-100"
        aria-label="Notifications"
      >
        <span aria-hidden>🔔</span>
        {unreadCount > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="absolute right-0 z-10 mt-2 w-80 rounded-md border border-surface-800 bg-surface-900 shadow-lg">
          <div className="flex items-center justify-between border-b border-surface-800 px-3 py-2">
            <span className="text-sm font-semibold text-surface-100">Notifications</span>
            {unreadCount > 0 ? (
              <Button variant="ghost" onClick={() => markAllReadMutation.mutate()}>
                Mark all read
              </Button>
            ) : null}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {notificationsQuery.data?.map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={() => !n.is_read && markReadMutation.mutate(n.id)}
                className="flex w-full flex-col items-start gap-1 border-b border-surface-900 px-3 py-2 text-left hover:bg-surface-800"
              >
                <div className="flex w-full items-center justify-between">
                  <span className="text-sm text-surface-100">{n.title}</span>
                  {!n.is_read ? <Badge tone="accent">new</Badge> : null}
                </div>
                {n.body ? <span className="text-xs text-surface-400">{n.body}</span> : null}
                <span className="text-xs text-surface-600">
                  {new Date(n.created_at).toLocaleString()}
                </span>
              </button>
            ))}
            {notificationsQuery.data && notificationsQuery.data.length === 0 ? (
              <p className="px-3 py-4 text-center text-sm text-surface-500">No notifications yet.</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
