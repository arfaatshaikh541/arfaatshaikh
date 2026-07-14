# Project status

**Current milestone:** Milestone 4 — Booking
**Status:** Complete, verified against a real PostgreSQL + Redis stack. Awaiting your review before starting Milestone 5.
**Last updated:** 2026-07-14

---

## What was built (Milestone 4)

### Backend (`apps/api`)
- **New `booking` module**: `AppointmentType` (tenant-configured catalog, same shape as Milestone 2's `Service`), `StaffAvailability` (recurring weekly windows per staff member — naive clock times interpreted in the tenant's configured timezone, `TenantSettings.timezone`, converted to UTC only at slot-computation time via Python's stdlib `zoneinfo`), `AvailabilityException` (whole-day time-off blocks), `Appointment` (`lead_id` nullable — a callback needn't be tied to a lead — `staff_user_id`, `appointment_type_id`, UTC `starts_at`/`ends_at`, `status`, `location`, `notes`, `created_by` nullable meaning client self-booked, `cancelled_reason`, `reminder_sent_at`).
- **Deterministic slot computation** (`compute_available_slots`): intersects weekly availability, subtracts whole-day exceptions and existing scheduled appointments, slices into the appointment type's duration, excludes anything already in the past. Capped at a 31-day lookup window.
- **Double-booking prevention**: `create_appointment` re-validates no overlapping `SCHEDULED` appointment exists for that staff member under a row lock (`SELECT ... FOR UPDATE`) immediately before insert — a slot the client saw a moment earlier is never trusted blindly. Verified with a real concurrent-style test (book the same slot twice, second attempt gets `409 slot_unavailable`) both in the automated suite and manually over live HTTP against a running server.
- **Two booking paths**: staff-initiated (authenticated, `appointments.manage`/`appointments.view` — already granted to every relevant role since Milestone 1) and public self-service (`POST /public/booking/{token}/book`), which reuses the exact same capture-token, throttle, and honeypot machinery as Milestone 2's public lead capture, finds-or-creates the lead the same way (heuristic email/phone match), then books the appointment.
- **Communications integration**: three new trigger events (`appointment_booked`, `appointment_reminder`, `appointment_cancelled`) added to the existing `EmailTriggerEvent` enum. Since that column is `native_enum=False` (a plain string, not a Postgres `ENUM` type), this needed only a Python-side enum change plus a column-width migration (`VARCHAR(20)` → `VARCHAR(30)`, `appointment_reminder`/`appointment_cancelled` are 21 characters), not a type migration. Reminders run on the same Celery-beat sweep pattern as Milestone 3's task reminders (`send_appointment_reminders_for_tenant`, unit-tested directly, thin per-tenant-loop worker wrapper), reusing `send_templated_email`'s soft-fail design — a notification problem never blocks a booking, cancellation, or the reminder sweep itself.
- **New permission**: `availability.manage` (Administrator/Manager only) — configuring appointment types and setting *other* staff members' availability. Setting your *own* availability only requires the existing `appointments.manage` permission (already on Sales/Support Agent by default) — no new permission needed for the self-service case.
- **No new subscription module was added.** Booking rides on the existing `booking` module, already defined in the Milestone 1 catalog (Growth/Professional/Enterprise plans, not Starter) and unused until now — the third catalog entry in a row (after Milestone 3's `communications`) that the original commercial-model design anticipated correctly.
- **Extended the Engagement Operations seed template**: 2 default appointment types (Free Consultation — 30 min, Callback — 15 min), Mon–Fri 09:00–17:00 availability for the Tenant Owner, and 3 additional email templates (Appointment Booked, Appointment Reminder, Appointment Cancelled) — applied to every newly created tenant, not just the demo tenant.
- **Two new Alembic migrations** (schema + RLS), both exercised through a full upgrade → downgrade → re-upgrade cycle against real Postgres.
- **14 new pytest tests** (86 total with Milestones 1–3's), covering: weekly-availability-driven slot computation, whole-day exceptions blocking a date, double-booking prevention (both the 409 response and that the booked slot disappears from subsequent `GET /slots` results), staff-initiated booking with real notification delivery via the fake email provider, rejecting past-dated bookings, cancellation notifications, the full public booking flow (lead creation + appointment + honeypot), appointment-reminder idempotency, permission enforcement for appointment-type management, the self-vs-other availability authorization rule, and cross-tenant isolation.

### Frontend (`apps/web`)
- `/appointment-types` — admin config screen (list/create), same pattern as Milestone 2's Services screen.
- `/availability` — self-service weekly-hours editor (per-day enable + start/end time) and blocked-day management, scoped to the signed-in user.
- `/appointments` — agenda-style list view grouped by day, staff filter, a "book a new appointment" flow (staff → type → date → slot picker), and complete/no-show/cancel actions per appointment. This is a chronological list grouping, not a drag-and-drop month calendar grid — the same kind of scope decision as Milestone 2's Kanban dropdown-vs-drag-and-drop, made to avoid pulling in a new calendar UI dependency for a first cut.
- `/book/[token]` — the public self-service booking page: appointment type → staff member → available time (next 14 days) → contact details → confirm.
- Lead detail page gained an "Appointments" section (list + link to the booking flow).
- Sidebar nav gained Appointments/My Availability/Appointment Types, gated by the relevant permission and the `booking` module entitlement.

### Worker (`apps/worker`)
- `app/tasks/booking.py` — `send_appointment_reminders` Celery beat task, a thin wrapper around the directly-tested `send_appointment_reminders_for_tenant` service function, added to the beat schedule at a 15-minute interval alongside Milestones 1 and 3's sweeps.

### Tests & verification
- `ruff check app` — 0 errors. `pytest -q` — 86 passed. `eslint` — 0 errors. `tsc --noEmit` — 0 errors. `next build` — succeeds, 28 routes. `vitest run` — 4 passed.
- Both new Alembic migrations exercised through a full upgrade → downgrade → re-upgrade cycle against real Postgres.
- Manually smoke-tested over real HTTP against a freshly seeded demo tenant with the API server actually running: confirmed the 2 seeded appointment types and the Tenant Owner's Mon–Fri availability via `GET`; computed real available slots for a future Monday and booked an appointment through the authenticated API; **attempted to double-book the exact same slot and confirmed the server rejected it with `409 slot_unavailable`** over live HTTP, not just inside the test suite; exercised the full public booking surface (`appointment-types`, `staff`, `slots`, `book`) through the tenant's real capture token and confirmed a new lead was created from the public booking exactly as designed.

## Acceptance criteria — verified

| Criterion (from your Milestone 4 spec) | Verified how |
|---|---|
| Consultation and callback scheduling | `AppointmentType` catalog + `Appointment` booking, both staff-initiated and public self-service |
| Staff availability | `StaffAvailability` (recurring weekly windows, timezone-aware) + `AvailabilityException` (blocked days); self-service via `/availability`, admin override via `availability.manage` |
| Calendar views | `/appointments` agenda view grouped by day with a staff filter — not a drag-and-drop month grid (documented limitation, same style of decision as Milestone 2's Kanban) |
| Booking confirmations | `appointment_booked`/`appointment_reminder`/`appointment_cancelled` templates built on Milestone 3's communications infrastructure (soft-fail sends, delivery log, retry sweep) |

## Known limitations

1. **No drag-and-drop calendar grid.** `/appointments` is a chronological agenda list grouped by day, not a visual month/week calendar. No calendar UI library was introduced this milestone to keep the dependency surface unchanged; revisit if the product requirement is specifically the visual grid, not just the scheduling outcome.
2. **Availability exceptions only support whole-day blocks**, not partial-day (e.g. "out from 2pm–4pm"). Staff wanting a partial block currently have to either shrink their weekly window for that day-of-week generally, or take the whole day off. Revisit if this becomes a real friction point.
3. **Confirmation/reminder emails render times in UTC**, not the tenant's or client's local timezone — the same convention already used for Milestone 3's task-reminder merge fields (`{{task_due_date}}`), kept consistent here (`{{appointment_time}}`) rather than introducing timezone-conversion logic into the email-rendering path for this milestone. A tenant in Asia/Dubai will see UTC times in their own confirmation emails today.
4. **Only one active template per (tenant, trigger_event) is enforced by lookup order, not a database constraint** — same limitation already documented for Milestone 3's `stage_changed` templates, now also applicable to the three new booking trigger events.
5. **`AppointmentRepository.find_overlapping`'s `exclude_id` parameter is unused this milestone** — it exists for a future reschedule/edit feature (change an existing appointment's time without it conflicting with itself) but nothing currently calls it with a non-`None` value, since there is no reschedule endpoint yet, only cancel + rebook.
6. **Same environment caveats as Milestones 1–3 carry forward**: Docker Compose itself was not run end-to-end in this sandbox (no Docker daemon available); all verification used the same application code run directly against local PostgreSQL 16 + Redis 7, including a real running `uvicorn` instance for the HTTP smoke tests (including the double-booking rejection, verified live). No browser was available to visually confirm the new UI — lint/typecheck/build/tests pass and the underlying API calls were manually confirmed working end-to-end, but no screenshot confirms rendering/interaction. Celery beat's scheduler itself was not run continuously in this sandbox; the task *logic* it calls was verified directly.
7. Two real gaps were found and fixed during this milestone's own design/build process (not present in the final code, but worth recording since they reflect real engineering decisions, not just clean-room design): the public booking flow initially had no way for the client to discover *which* staff members are bookable (a `GET /public/booking/{token}/staff` endpoint, returning only id/first/last name, was added to close this); and a first draft of the availability-authorization check accidentally coupled the service layer to a route-level permission-context object, which was refactored to take plain booleans instead, keeping permission-code knowledge in the route layer consistent with every other module.

## Pending decisions

None new this milestone — Milestone 1's pending decisions (tenant-URL routing, production email/storage provider choice) remain open and don't block Milestone 5.

## Next action

Awaiting your review of Milestone 4. To proceed, reply exactly: **APPROVE MILESTONE 5**

Milestone 5 (per the approved architecture) is Workflow Automation:
a trigger-condition-action automation engine (e.g. "when a lead enters
stage X, wait N days, then send template Y or create a task"), building
on the scoring/assignment/communications/booking primitives from
Milestones 3 and 4.
