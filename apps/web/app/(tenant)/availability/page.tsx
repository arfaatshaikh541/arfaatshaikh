"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { AvailabilityExceptionItem, AvailabilityWindow } from "@/lib/types";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

interface DayState {
  enabled: boolean;
  start_time: string;
  end_time: string;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function inNinetyDays(): string {
  const d = new Date();
  d.setDate(d.getDate() + 90);
  return d.toISOString().slice(0, 10);
}

export default function AvailabilityPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [days, setDays] = useState<DayState[]>(DAYS.map(() => ({ enabled: false, start_time: "09:00", end_time: "17:00" })));
  const [exceptionDate, setExceptionDate] = useState("");
  const [exceptionReason, setExceptionReason] = useState("");

  const windowsQuery = useQuery({
    queryKey: ["availability", user?.id],
    queryFn: () => api.get<AvailabilityWindow[]>(`/tenant/availability/${user!.id}`),
    enabled: !!user,
  });
  const exceptionsQuery = useQuery({
    queryKey: ["availability", user?.id, "exceptions"],
    queryFn: () => api.get<AvailabilityExceptionItem[]>(`/tenant/availability/${user!.id}/exceptions?date_from=${todayIso()}&date_to=${inNinetyDays()}`),
    enabled: !!user,
  });

  useEffect(() => {
    if (!windowsQuery.data) return;
    setDays((prev) =>
      prev.map((day, index) => {
        const match = windowsQuery.data!.find((w) => w.day_of_week === index);
        return match ? { enabled: true, start_time: match.start_time.slice(0, 5), end_time: match.end_time.slice(0, 5) } : day;
      }),
    );
  }, [windowsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.put(`/tenant/availability/${user!.id}`, {
        windows: days
          .map((day, index) => ({ ...day, day_of_week: index }))
          .filter((day) => day.enabled)
          .map((day) => ({ day_of_week: day.day_of_week, start_time: `${day.start_time}:00`, end_time: `${day.end_time}:00` })),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["availability", user?.id] }),
  });

  const addException = useMutation({
    mutationFn: () => api.post(`/tenant/availability/${user!.id}/exceptions`, { date: exceptionDate, reason: exceptionReason }),
    onSuccess: () => {
      setExceptionDate("");
      setExceptionReason("");
      queryClient.invalidateQueries({ queryKey: ["availability", user?.id, "exceptions"] });
    },
  });

  const removeException = useMutation({
    mutationFn: (id: string) => api.delete(`/tenant/availability/exceptions/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["availability", user?.id, "exceptions"] }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Your availability</h1>
        <p className="mt-1 text-sm text-ink-muted">The recurring weekly hours clients can book you for, plus any blocked days.</p>
      </div>

      <Card>
        <CardHeader title="Weekly hours" />
        <div className="space-y-3">
          {DAYS.map((label, index) => {
            const day = days[index] ?? { enabled: false, start_time: "09:00", end_time: "17:00" };
            return (
              <div key={label} className="flex items-center gap-3">
                <label className="flex w-32 items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={day.enabled}
                    onChange={(e) => setDays((prev) => prev.map((d, i) => (i === index ? { ...d, enabled: e.target.checked } : d)))}
                  />
                  {label}
                </label>
                {day.enabled && (
                  <>
                    <Input
                      type="time" className="w-32" value={day.start_time}
                      onChange={(e) => setDays((prev) => prev.map((d, i) => (i === index ? { ...d, start_time: e.target.value } : d)))}
                    />
                    <span className="text-ink-faint">to</span>
                    <Input
                      type="time" className="w-32" value={day.end_time}
                      onChange={(e) => setDays((prev) => prev.map((d, i) => (i === index ? { ...d, end_time: e.target.value } : d)))}
                    />
                  </>
                )}
              </div>
            );
          })}
        </div>
        <Button className="mt-4" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? "Saving…" : "Save availability"}
        </Button>
        {saveMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{saveMutation.error instanceof ApiError ? saveMutation.error.message : "Unable to save availability."}</Alert>
          </div>
        )}
        {saveMutation.isSuccess && (
          <div className="mt-3">
            <Alert tone="success">Availability saved.</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Blocked days" description="Whole-day time off — no slots will be offered on these dates." />
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label htmlFor="exception-date">Date</Label>
            <Input id="exception-date" type="date" value={exceptionDate} onChange={(e) => setExceptionDate(e.target.value)} />
          </div>
          <div className="min-w-[220px]">
            <Label htmlFor="exception-reason">Reason (optional)</Label>
            <Input id="exception-reason" value={exceptionReason} onChange={(e) => setExceptionReason(e.target.value)} />
          </div>
          <Button variant="secondary" onClick={() => addException.mutate()} disabled={!exceptionDate || addException.isPending}>
            Block day
          </Button>
        </div>
        <div className="mt-4 space-y-2">
          {exceptionsQuery.data?.map((exception) => (
            <div key={exception.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
              <span className="text-ink">
                {exception.date} {exception.reason && <span className="text-ink-faint">— {exception.reason}</span>}
              </span>
              <Button variant="ghost" onClick={() => removeException.mutate(exception.id)}>
                Remove
              </Button>
            </div>
          ))}
          {exceptionsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No blocked days in the next 90 days.</p>}
        </div>
      </Card>
    </div>
  );
}
