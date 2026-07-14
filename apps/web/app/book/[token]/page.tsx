"use client";

import { use, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { AvailableSlot } from "@/lib/types";

interface AppointmentTypesResponse {
  tenant_name: string;
  appointment_types: { id: string; name: string; description: string; duration_minutes: number }[];
}

interface StaffOption {
  id: string;
  first_name: string;
  last_name: string;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function inDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function PublicBookingPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);

  const [appointmentTypeId, setAppointmentTypeId] = useState("");
  const [staffId, setStaffId] = useState("");
  const [selectedSlot, setSelectedSlot] = useState<AvailableSlot | null>(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [website, setWebsite] = useState(""); // honeypot
  const [validationError, setValidationError] = useState<string | null>(null);

  const typesQuery = useQuery({
    queryKey: ["public", "booking", "types", token],
    queryFn: () => api.get<AppointmentTypesResponse>(`/public/booking/${token}/appointment-types`),
  });
  const staffQuery = useQuery({
    queryKey: ["public", "booking", "staff", token],
    queryFn: () => api.get<StaffOption[]>(`/public/booking/${token}/staff`),
  });
  const slotsQuery = useQuery({
    queryKey: ["public", "booking", "slots", token, staffId, appointmentTypeId],
    queryFn: () =>
      api.get<AvailableSlot[]>(
        `/public/booking/${token}/slots?staff_user_id=${staffId}&date_from=${todayIso()}&date_to=${inDays(14)}&appointment_type_id=${appointmentTypeId}`,
      ),
    enabled: !!staffId && !!appointmentTypeId,
  });

  const bookMutation = useMutation({
    mutationFn: () =>
      api.post<{ status: string; appointment_id?: string }>(`/public/booking/${token}/book`, {
        first_name: firstName, last_name: lastName, email: email || null, phone: phone || null,
        staff_user_id: staffId, appointment_type_id: appointmentTypeId, starts_at: selectedSlot!.start, website,
      }),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    if (!firstName.trim()) {
      setValidationError("Please enter your first name.");
      return;
    }
    if (!email.trim() && !phone.trim()) {
      setValidationError("Please provide an email or phone number so we can confirm your booking.");
      return;
    }
    if (!selectedSlot) {
      setValidationError("Please select a time slot.");
      return;
    }
    bookMutation.mutate();
  };

  if (typesQuery.isLoading) {
    return <div className="flex min-h-screen items-center justify-center text-ink-muted">Loading…</div>;
  }
  if (typesQuery.isError || !typesQuery.data) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Alert tone="error">This booking page could not be found.</Alert>
      </div>
    );
  }
  if (bookMutation.isSuccess) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface px-4">
        <Card className="max-w-md">
          <CardHeader title="Booking confirmed" />
          <Alert tone="success">
            Your appointment with {typesQuery.data.tenant_name} has been booked. A confirmation email will be sent shortly.
          </Alert>
        </Card>
      </div>
    );
  }

  const staffOptions = staffQuery.data ?? [];

  return (
    <div className="min-h-screen bg-surface px-4 py-12">
      <div className="mx-auto max-w-lg">
        <h1 className="text-xl font-semibold text-ink">Book an appointment with {typesQuery.data.tenant_name}</h1>
        <p className="mt-1 text-sm text-ink-muted">Choose an appointment type, a staff member, and a time that works for you.</p>

        <Card className="mt-6">
          <form className="space-y-4" onSubmit={handleSubmit} noValidate>
            {validationError && <Alert tone="error">{validationError}</Alert>}
            {bookMutation.isError && (
              <Alert tone="error">{bookMutation.error instanceof ApiError ? bookMutation.error.message : "Unable to book this appointment."}</Alert>
            )}

            <div>
              <Label>Appointment type</Label>
              <select
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={appointmentTypeId}
                onChange={(e) => { setAppointmentTypeId(e.target.value); setSelectedSlot(null); }}
              >
                <option value="">Select a type</option>
                {typesQuery.data.appointment_types.map((type) => (
                  <option key={type.id} value={type.id}>{type.name} ({type.duration_minutes} min)</option>
                ))}
              </select>
            </div>

            <div>
              <Label>Staff member</Label>
              <select
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                value={staffId}
                onChange={(e) => { setStaffId(e.target.value); setSelectedSlot(null); }}
              >
                <option value="">Select a staff member</option>
                {staffOptions.map((s) => (
                  <option key={s.id} value={s.id}>{s.first_name} {s.last_name}</option>
                ))}
              </select>
            </div>

            {staffId && appointmentTypeId && (
              <div>
                <Label>Available times (next 14 days)</Label>
                <div className="flex flex-wrap gap-2">
                  {slotsQuery.data?.map((slot) => (
                    <button
                      type="button"
                      key={slot.start}
                      onClick={() => setSelectedSlot(slot)}
                      className={`focus-ring rounded-md border px-3 py-1.5 text-xs ${
                        selectedSlot?.start === slot.start ? "border-accent bg-accent/15 text-accent" : "border-surface-border text-ink hover:border-ink-muted"
                      }`}
                    >
                      {new Date(slot.start).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" })}
                    </button>
                  ))}
                  {slotsQuery.data?.length === 0 && <p className="text-sm text-ink-muted">No available times in the next 14 days.</p>}
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>First name</Label>
                <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
              </div>
              <div>
                <Label>Last name</Label>
                <Input value={lastName} onChange={(e) => setLastName(e.target.value)} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Email</Label>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div>
                <Label>Phone</Label>
                <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
              </div>
            </div>

            {/* Honeypot — hidden from real visitors via CSS, left empty by them. */}
            <div className="absolute -left-[9999px]" aria-hidden="true">
              <label>
                Website
                <input tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
              </label>
            </div>

            <Button type="submit" className="w-full" disabled={bookMutation.isPending}>
              {bookMutation.isPending ? "Booking…" : "Confirm booking"}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
