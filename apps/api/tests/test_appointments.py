from datetime import date, datetime, timedelta

from tests.factories import add_member, login, make_tenant_with_owner


def _next_weekday(start: date, weekday: int) -> date:
    """weekday: Monday=0 ... Sunday=6."""
    days_ahead = weekday - start.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return start + timedelta(days=days_ahead)


def _set_monday_only_hours(client, tenant, csrf):
    resp = client.patch(
        "/api/tenants/me/settings",
        json={
            "business_hours": {
                "mon": {"start": "09:00", "end": "12:00"},
                "tue": None,
                "wed": None,
                "thu": None,
                "fri": None,
                "sat": None,
                "sun": None,
            }
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200


def test_available_slots_respects_business_hours(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    _set_monday_only_hours(client, tenant, csrf)
    monday = _next_weekday(date.today(), 0)

    resp = client.get(
        "/api/tenants/me/appointments/available-slots",
        params={"on_date": monday.isoformat(), "duration_minutes": 60},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert resp.status_code == 200
    slots = resp.json()
    assert len(slots) == 3

    tuesday = monday + timedelta(days=1)
    closed_resp = client.get(
        "/api/tenants/me/appointments/available-slots",
        params={"on_date": tuesday.isoformat(), "duration_minutes": 60},
        headers={"X-Tenant-Id": str(tenant.id)},
    )
    assert closed_resp.json() == []


def test_booking_excludes_slot_from_availability_and_rejects_double_booking(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    agent, agent_membership = add_member(db_session, tenant, role_slug="sales_agent")
    csrf = login(client, owner.email)
    _set_monday_only_hours(client, tenant, csrf)
    monday = _next_weekday(date.today(), 0)

    lead_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Bookable"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]

    slots = client.get(
        "/api/tenants/me/appointments/available-slots",
        params={
            "on_date": monday.isoformat(),
            "duration_minutes": 60,
            "assigned_membership_id": str(agent_membership.id),
        },
        headers={"X-Tenant-Id": str(tenant.id)},
    ).json()
    assert len(slots) == 3
    chosen = slots[1]

    book_resp = client.post(
        "/api/tenants/me/appointments",
        json={
            "lead_id": lead_id,
            "assigned_membership_id": str(agent_membership.id),
            "starts_at": chosen["starts_at"],
            "ends_at": chosen["ends_at"],
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert book_resp.status_code == 201
    appointment_id = book_resp.json()["id"]

    after_booking = client.get(
        "/api/tenants/me/appointments/available-slots",
        params={
            "on_date": monday.isoformat(),
            "duration_minutes": 60,
            "assigned_membership_id": str(agent_membership.id),
        },
        headers={"X-Tenant-Id": str(tenant.id)},
    ).json()
    assert len(after_booking) == 2
    assert chosen not in after_booking

    # Booking the exact same slot again for the same staff member must be
    # rejected server-side, regardless of what the client's availability
    # check said a moment ago.
    double_book_resp = client.post(
        "/api/tenants/me/appointments",
        json={
            "lead_id": lead_id,
            "assigned_membership_id": str(agent_membership.id),
            "starts_at": chosen["starts_at"],
            "ends_at": chosen["ends_at"],
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert double_book_resp.status_code == 422
    assert appointment_id is not None


def test_appointment_lifecycle(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    _set_monday_only_hours(client, tenant, csrf)
    monday = _next_weekday(date.today(), 0)

    lead_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Lifecycle"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]

    slot = client.get(
        "/api/tenants/me/appointments/available-slots",
        params={"on_date": monday.isoformat(), "duration_minutes": 60},
        headers={"X-Tenant-Id": str(tenant.id)},
    ).json()[0]

    appointment = client.post(
        "/api/tenants/me/appointments",
        json={"lead_id": lead_id, "starts_at": slot["starts_at"], "ends_at": slot["ends_at"]},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()

    confirm_resp = client.post(
        f"/api/tenants/me/appointments/{appointment['id']}/confirm",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert confirm_resp.json()["status"] == "confirmed"

    next_slot = client.get(
        "/api/tenants/me/appointments/available-slots",
        params={"on_date": monday.isoformat(), "duration_minutes": 60},
        headers={"X-Tenant-Id": str(tenant.id)},
    ).json()[0]
    reschedule_resp = client.post(
        f"/api/tenants/me/appointments/{appointment['id']}/reschedule",
        json={"starts_at": next_slot["starts_at"], "ends_at": next_slot["ends_at"]},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert reschedule_resp.status_code == 200
    assert datetime.fromisoformat(reschedule_resp.json()["starts_at"]) == datetime.fromisoformat(
        next_slot["starts_at"]
    )

    no_reason_resp = client.post(
        f"/api/tenants/me/appointments/{appointment['id']}/cancel",
        json={"reason": ""},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert no_reason_resp.status_code == 422

    cancel_resp = client.post(
        f"/api/tenants/me/appointments/{appointment['id']}/cancel",
        json={"reason": "Client rescheduled by phone."},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


def test_appointment_completed_and_no_show(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    csrf = login(client, owner.email)
    _set_monday_only_hours(client, tenant, csrf)
    monday = _next_weekday(date.today(), 0)
    lead_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "Statusy"},
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()["id"]
    slots = client.get(
        "/api/tenants/me/appointments/available-slots",
        params={"on_date": monday.isoformat(), "duration_minutes": 60},
        headers={"X-Tenant-Id": str(tenant.id)},
    ).json()

    completed = client.post(
        "/api/tenants/me/appointments",
        json={
            "lead_id": lead_id,
            "starts_at": slots[0]["starts_at"],
            "ends_at": slots[0]["ends_at"],
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()
    complete_resp = client.post(
        f"/api/tenants/me/appointments/{completed['id']}/complete",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert complete_resp.json()["status"] == "completed"

    no_show = client.post(
        "/api/tenants/me/appointments",
        json={
            "lead_id": lead_id,
            "starts_at": slots[1]["starts_at"],
            "ends_at": slots[1]["ends_at"],
        },
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    ).json()
    no_show_resp = client.post(
        f"/api/tenants/me/appointments/{no_show['id']}/no-show",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert no_show_resp.json()["status"] == "no_show"


def test_appointment_requires_permission(client, db_session):
    tenant, owner = make_tenant_with_owner(db_session)
    viewer, _m = add_member(db_session, tenant, role_slug="viewer")
    csrf = login(client, viewer.email)
    resp = client.get(
        "/api/tenants/me/appointments",
        headers={"X-Tenant-Id": str(tenant.id), "X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403


def test_appointment_cross_tenant_lead_rejected(client, db_session):
    tenant_a, owner_a = make_tenant_with_owner(db_session)
    tenant_b, owner_b = make_tenant_with_owner(db_session)
    csrf_b = login(client, owner_b.email)
    lead_b_id = client.post(
        "/api/tenants/me/leads",
        json={"first_name": "B-Lead"},
        headers={"X-Tenant-Id": str(tenant_b.id), "X-CSRF-Token": csrf_b},
    ).json()["id"]

    csrf_a = login(client, owner_a.email)
    resp = client.post(
        "/api/tenants/me/appointments",
        json={
            "lead_id": lead_b_id,
            "starts_at": "2026-08-03T09:00:00+04:00",
            "ends_at": "2026-08-03T10:00:00+04:00",
        },
        headers={"X-Tenant-Id": str(tenant_a.id), "X-CSRF-Token": csrf_a},
    )
    assert resp.status_code == 422
