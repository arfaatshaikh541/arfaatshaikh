"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { AppointmentItem, AppointmentTypeItem, AvailableSlot, TenantMember } from "@/lib/types";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function inDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

const statusTone: Record<string, string> = {
  scheduled: "text-accent",
  completed: "text-emerald-400",
  cancelled: "text-red-400",
  no_show: "text-amber-400",
};

export default function AppointmentsPage() {
  const queryClient = useQueryClient();
  const [dateFrom, setDateFrom] = useState(todayIso());
  const [dateTo, setDateTo] = useState(inDays(14));
  const [staffFilter, setStaffFilter] = useState("");

  const [newStaffId, setNewStaffId] = useState("");
  const [newTypeId, setNewTypeId] = useState("");
  const [newDate, setNewDate] = useState(todayIso());
  const [selectedSlot, setSelectedSlot] = useState<AvailableSlot | null>(null);

  const membersQuery = useQuery({ queryKey: ["tenant", "users"], queryFn: () => api.get<TenantMember[]>("/tenant/users") });
  const typesQuery = useQuery({ queryKey: ["tenant", "appointment-types"], queryFn: () => api.get<AppointmentTypeItem[]>("/tenant/appointment-types") });
  const appointmentsQuery = useQuery({
    queryKey: ["tenant", "appointments", dateFrom, dateTo, staffFilter],
    queryFn: () =>
      api.get<AppointmentItem[]>(
        `/tenant/appointments?date_from=${dateFrom}T00:00:00Z&date_to=${dateTo}T23:59:59Z${staffFilter ? `&staff_user_id=${staffFilter}` : ""}`,
      ),
  });
  const slotsQuery = useQuery({
    queryKey: ["tenant", "appointments", "slots", newStaffId, newTypeId, newDate],
    queryFn: () =>
      api.get<AvailableSlot[]>(`/tenant/appointments/slots?staff_user_id=${newStaffId}&date_from=${newDate}&date_to=${newDate}&appointment_type_id=${newTypeId}`),
    enabled: !!newStaffId && !!newTypeId,
  });

  const createMutation = useMutation({
    mutationFn: () => api.post("/tenant/appointments", { staff_user_id: newStaffId, appointment_type_id: newTypeId, starts_at: selectedSlot!.start }),
    onSuccess: () => {
      setSelectedSlot(null);
      queryClient.invalidateQueries({ queryKey: ["tenant", "appointments"] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.post(`/tenant/appointments/${id}/cancel`, { reason: "Cancelled by staff" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "appointments"] }),
  });
  const completeMutation = useMutation({
    mutationFn: (id: string) => api.post(`/tenant/appointments/${id}/complete`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "appointments"] }),
  });
  const noShowMutation = useMutation({
    mutationFn: (id: string) => api.post(`/tenant/appointments/${id}/no-show`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tenant", "appointments"] }),
  });

  const members = membersQuery.data ?? [];
  const memberName = (userId: string) => {
    const member = members.find((m) => m.user_id === userId);
    return member ? `${member.first_name} ${member.last_name}` : userId;
  };

  const groupedByDay = useMemo(() => {
    const groups: Record<string, AppointmentItem[]> = {};
    for (const appointment of appointmentsQuery.data ?? []) {
      const day = appointment.starts_at.slice(0, 10);
      groups[day] = groups[day] ?? [];
      groups[day].push(appointment);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [appointmentsQuery.data]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Appointments</h1>
        <p className="mt-1 text-sm text-ink-muted">Consultations and callbacks, grouped by day.</p>
      </div>

      <Card>
        <CardHeader title="Book a new appointment" />
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[200px]">
            <Label htmlFor="new-staff">Staff member</Label>
            <select
              id="new-staff" className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
              value={newStaffId} onChange={(e) => { setNewStaffId(e.target.value); setSelectedSlot(null); }}
            >
              <option value="">Select…</option>
              {members.map((m) => (
                <option key={m.user_id} value={m.user_id}>{m.first_name} {m.last_name}</option>
              ))}
            </select>
          </div>
          <div className="min-w-[200px]">
            <Label htmlFor="new-type">Appointment type</Label>
            <select
              id="new-type" className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
              value={newTypeId} onChange={(e) => { setNewTypeId(e.target.value); setSelectedSlot(null); }}
            >
              <option value="">Select…</option>
              {typesQuery.data?.map((t) => (
                <option key={t.id} value={t.id}>{t.name} ({t.duration_minutes} min)</option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="new-date">Date</Label>
            <Input id="new-date" type="date" value={newDate} onChange={(e) => { setNewDate(e.target.value); setSelectedSlot(null); }} />
          </div>
        </div>

        {newStaffId && newTypeId && (
          <div className="mt-4">
            <Label>Available slots</Label>
            <div className="flex flex-wrap gap-2">
              {slotsQuery.data?.map((slot) => (
                <button
                  key={slot.start}
                  onClick={() => setSelectedSlot(slot)}
                  className={`focus-ring rounded-md border px-3 py-1.5 text-xs ${
                    selectedSlot?.start === slot.start ? "border-accent bg-accent/15 text-accent" : "border-surface-border text-ink hover:border-ink-muted"
                  }`}
                >
                  {new Date(slot.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: "UTC" })}
                </button>
              ))}
              {slotsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No available slots on this date.</p>}
            </div>
          </div>
        )}

        <Button className="mt-4" onClick={() => createMutation.mutate()} disabled={!selectedSlot || createMutation.isPending}>
          {createMutation.isPending ? "Booking…" : "Book appointment"}
        </Button>
        {createMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to book appointment."}</Alert>
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div>
            <Label htmlFor="date-from">From</Label>
            <Input id="date-from" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="date-to">To</Label>
            <Input id="date-to" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div className="min-w-[200px]">
            <Label htmlFor="staff-filter">Staff member</Label>
            <select
              id="staff-filter" className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
              value={staffFilter} onChange={(e) => setStaffFilter(e.target.value)}
            >
              <option value="">All staff</option>
              {members.map((m) => (
                <option key={m.user_id} value={m.user_id}>{m.first_name} {m.last_name}</option>
              ))}
            </select>
          </div>
        </div>

        {groupedByDay.length === 0 && <p className="text-sm text-ink-muted">No appointments in this range.</p>}
        <div className="space-y-6">
          {groupedByDay.map(([day, appointments]) => (
            <div key={day}>
              <h3 className="mb-2 text-sm font-medium text-ink-muted">{new Date(day + "T00:00:00Z").toLocaleDateString([], { weekday: "long", month: "short", day: "numeric", timeZone: "UTC" })}</h3>
              <div className="space-y-2">
                {appointments.map((appointment) => (
                  <div key={appointment.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
                    <div>
                      <p className="text-ink">
                        {new Date(appointment.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: "UTC" })} — {appointment.title}
                      </p>
                      <p className="text-xs text-ink-faint">
                        {memberName(appointment.staff_user_id)}
                        <span className={`ml-2 capitalize ${statusTone[appointment.status]}`}>{appointment.status}</span>
                      </p>
                    </div>
                    {appointment.status === "scheduled" && (
                      <div className="flex gap-2">
                        <Button variant="secondary" onClick={() => completeMutation.mutate(appointment.id)}>Complete</Button>
                        <Button variant="secondary" onClick={() => noShowMutation.mutate(appointment.id)}>No-show</Button>
                        <Button variant="danger" onClick={() => cancelMutation.mutate(appointment.id)}>Cancel</Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
