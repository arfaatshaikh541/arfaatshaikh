from datetime import UTC, date, datetime, timedelta

from app.tests.conftest import login
from app.tests.factories import add_member, create_tenant_with_owner


def _next_weekday(target_weekday: int) -> date:
    """Returns the next date (strictly after today) matching the given
    `date.weekday()` value, at least 7 days out — avoids any flakiness
    from running near a day boundary."""
    today = datetime.now(UTC).date()
    days_ahead = (target_weekday - today.weekday()) % 7
    return today + timedelta(days=days_ahead + 7)


def _set_owner_monday_availability(client) -> date:
    monday = _next_weekday(0)
    response = client.put(
        f"/api/tenant/availability/{_owner_id(client)}",
        json={"windows": [{"day_of_week": 0, "start_time": "09:00:00", "end_time": "12:00:00"}]},
    )
    assert response.status_code == 200, response.text
    return monday


def _owner_id(client) -> str:
    return client.get("/api/auth/me").json()["id"]


def _create_appointment_type(client, *, duration_minutes: int = 30) -> str:
    response = client.post(
        "/api/tenant/appointment-types", json={"name": "Free Consultation", "duration_minutes": duration_minutes}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_weekly_availability_and_slot_computation(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    monday = _set_owner_monday_availability(client)
    appointment_type_id = _create_appointment_type(client)

    response = client.get(
        f"/api/tenant/appointments/slots?staff_user_id={_owner_id(client)}&date_from={monday.isoformat()}"
        f"&date_to={monday.isoformat()}&appointment_type_id={appointment_type_id}"
    )
    assert response.status_code == 200
    slots = response.json()
    assert len(slots) == 6  # 09:00-12:00 in 30-minute increments
    assert slots[0]["start"].startswith(monday.isoformat())


def test_availability_exception_blocks_the_day(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    monday = _set_owner_monday_availability(client)
    appointment_type_id = _create_appointment_type(client)

    exception_response = client.post(f"/api/tenant/availability/{_owner_id(client)}/exceptions", json={"date": monday.isoformat(), "reason": "Day off"})
    assert exception_response.status_code == 201

    response = client.get(
        f"/api/tenant/appointments/slots?staff_user_id={_owner_id(client)}&date_from={monday.isoformat()}"
        f"&date_to={monday.isoformat()}&appointment_type_id={appointment_type_id}"
    )
    assert response.json() == []


def test_double_booking_is_prevented(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    monday = _set_owner_monday_availability(client)
    appointment_type_id = _create_appointment_type(client)
    slots = client.get(
        f"/api/tenant/appointments/slots?staff_user_id={_owner_id(client)}&date_from={monday.isoformat()}"
        f"&date_to={monday.isoformat()}&appointment_type_id={appointment_type_id}"
    ).json()
    slot_start = slots[0]["start"]

    first = client.post(
        "/api/tenant/appointments",
        json={"staff_user_id": _owner_id(client), "starts_at": slot_start, "appointment_type_id": appointment_type_id},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/tenant/appointments",
        json={"staff_user_id": _owner_id(client), "starts_at": slot_start, "appointment_type_id": appointment_type_id},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "slot_unavailable"

    remaining_slots = client.get(
        f"/api/tenant/appointments/slots?staff_user_id={_owner_id(client)}&date_from={monday.isoformat()}"
        f"&date_to={monday.isoformat()}&appointment_type_id={appointment_type_id}"
    ).json()
    assert not any(s["start"] == slot_start for s in remaining_slots)  # booked slot no longer offered


def test_staff_initiated_booking_notifies_lead(client, db_session, fake_email):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    monday = _set_owner_monday_availability(client)
    appointment_type_id = _create_appointment_type(client)
    client.post(
        "/api/tenant/communications/templates",
        json={"name": "Booked", "trigger_event": "appointment_booked", "subject": "Confirmed: {{appointment_date}}", "body_text": "See you {{appointment_time}}."},
    )

    lead = client.post("/api/tenant/leads", json={"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}).json()
    slot_start = client.get(
        f"/api/tenant/appointments/slots?staff_user_id={_owner_id(client)}&date_from={monday.isoformat()}"
        f"&date_to={monday.isoformat()}&appointment_type_id={appointment_type_id}"
    ).json()[0]["start"]

    response = client.post(
        "/api/tenant/appointments",
        json={"staff_user_id": _owner_id(client), "starts_at": slot_start, "appointment_type_id": appointment_type_id, "lead_id": lead["id"]},
    )
    assert response.status_code == 201, response.text
    assert any(m["to"] == "client.one@testclient.internal" for m in fake_email.sent)

    timeline = client.get(f"/api/tenant/leads/{lead['id']}/timeline").json()
    assert any(a["activity_type"] == "appointment.booked" for a in timeline)


def test_cannot_book_in_the_past(client, db_session):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    response = client.post(
        "/api/tenant/appointments",
        json={"staff_user_id": _owner_id(client), "starts_at": "2020-01-01T09:00:00Z"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "appointment_in_the_past"


def test_cancel_appointment_notifies_lead(client, db_session, fake_email):
    create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")

    monday = _set_owner_monday_availability(client)
    appointment_type_id = _create_appointment_type(client)
    client.post(
        "/api/tenant/communications/templates",
        json={"name": "Cancelled", "trigger_event": "appointment_cancelled", "subject": "Cancelled", "body_text": "Cancelled."},
    )
    lead = client.post("/api/tenant/leads", json={"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}).json()
    slot_start = client.get(
        f"/api/tenant/appointments/slots?staff_user_id={_owner_id(client)}&date_from={monday.isoformat()}"
        f"&date_to={monday.isoformat()}&appointment_type_id={appointment_type_id}"
    ).json()[0]["start"]
    appointment = client.post(
        "/api/tenant/appointments",
        json={"staff_user_id": _owner_id(client), "starts_at": slot_start, "appointment_type_id": appointment_type_id, "lead_id": lead["id"]},
    ).json()

    cancel = client.post(f"/api/tenant/appointments/{appointment['id']}/cancel", json={"reason": "Client requested"})
    assert cancel.status_code == 200
    assert any(m["to"] == "client.one@testclient.internal" and "Cancelled" in m["subject"] for m in fake_email.sent)


def test_public_booking_creates_lead_and_appointment(client, db_session, fake_email):
    from app.tests.factories import create_capture_token

    tenant, owner = create_tenant_with_owner(db_session)
    token = create_capture_token(db_session, tenant.id)

    login(client, "owner@test.internal", "OwnerPass!2345")
    monday = _set_owner_monday_availability(client)
    appointment_type_id = _create_appointment_type(client)
    client.post("/api/auth/logout")

    staff = client.get(f"/api/public/booking/{token}/staff").json()
    assert any(s["id"] == str(owner.id) for s in staff)

    slots = client.get(
        f"/api/public/booking/{token}/slots?staff_user_id={owner.id}&date_from={monday.isoformat()}"
        f"&date_to={monday.isoformat()}&appointment_type_id={appointment_type_id}"
    ).json()
    assert len(slots) > 0

    response = client.post(
        f"/api/public/booking/{token}/book",
        json={
            "first_name": "Public", "last_name": "Client", "email": "public.client@testclient.internal",
            "staff_user_id": str(owner.id), "appointment_type_id": appointment_type_id, "starts_at": slots[0]["start"],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["appointment_id"]

    login(client, "owner@test.internal", "OwnerPass!2345")
    leads = client.get("/api/tenant/leads").json()["items"]
    assert any(lead["email"] == "public.client@testclient.internal" for lead in leads)


def test_public_booking_honeypot_silently_drops(client, db_session):
    from app.tests.factories import create_capture_token

    tenant, _owner = create_tenant_with_owner(db_session)
    token = create_capture_token(db_session, tenant.id)
    login(client, "owner@test.internal", "OwnerPass!2345")
    monday = _set_owner_monday_availability(client)
    appointment_type_id = _create_appointment_type(client)
    owner_id = _owner_id(client)
    client.post("/api/auth/logout")

    slots = client.get(
        f"/api/public/booking/{token}/slots?staff_user_id={owner_id}&date_from={monday.isoformat()}&date_to={monday.isoformat()}&appointment_type_id={appointment_type_id}"
    ).json()

    response = client.post(
        f"/api/public/booking/{token}/book",
        json={
            "first_name": "Bot", "email": "bot@spam.internal", "staff_user_id": owner_id,
            "appointment_type_id": appointment_type_id, "starts_at": slots[0]["start"], "website": "http://spam.example",
        },
    )
    assert response.status_code == 201
    assert response.json() == {"status": "received"}


def test_appointment_reminder_sent_once_and_idempotent(client, db_session, fake_email):
    from app.modules.booking.service import send_appointment_reminders_for_tenant

    tenant, _owner = create_tenant_with_owner(db_session)
    login(client, "owner@test.internal", "OwnerPass!2345")
    monday = _set_owner_monday_availability(client)
    appointment_type_id = _create_appointment_type(client)
    client.post(
        "/api/tenant/communications/templates",
        json={"name": "Reminder", "trigger_event": "appointment_reminder", "subject": "Reminder", "body_text": "Reminder."},
    )
    lead = client.post("/api/tenant/leads", json={"first_name": "Client", "last_name": "One", "email": "client.one@testclient.internal"}).json()
    slot_start = client.get(
        f"/api/tenant/appointments/slots?staff_user_id={_owner_id(client)}&date_from={monday.isoformat()}"
        f"&date_to={monday.isoformat()}&appointment_type_id={appointment_type_id}"
    ).json()[0]["start"]
    client.post(
        "/api/tenant/appointments",
        json={"staff_user_id": _owner_id(client), "starts_at": slot_start, "appointment_type_id": appointment_type_id, "lead_id": lead["id"]},
    )

    cutoff = datetime.fromisoformat(slot_start.replace("Z", "+00:00")) + timedelta(hours=1)
    first_run = send_appointment_reminders_for_tenant(db_session, tenant_id=tenant.id, before=cutoff)
    assert first_run == 1
    assert any(m["to"] == "client.one@testclient.internal" for m in fake_email.sent)

    second_run = send_appointment_reminders_for_tenant(db_session, tenant_id=tenant.id, before=cutoff)
    assert second_run == 0


def test_availability_manage_requires_permission_for_appointment_types(client, db_session):
    tenant, _owner = create_tenant_with_owner(db_session)
    add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")

    login(client, "agent@test.internal", "AgentPass!2345")
    response = client.post("/api/tenant/appointment-types", json={"name": "X", "duration_minutes": 30})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_cannot_set_another_users_availability_without_users_manage(client, db_session):
    tenant, owner = create_tenant_with_owner(db_session)
    agent = add_member(db_session, tenant=tenant, email="agent@test.internal", password="AgentPass!2345", role_name="Sales Agent")
    db_session.commit()

    login(client, "agent@test.internal", "AgentPass!2345")
    response = client.put(f"/api/tenant/availability/{owner.id}", json={"windows": []})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "cannot_manage_others_availability"

    own_response = client.put(f"/api/tenant/availability/{agent.id}", json={"windows": [{"day_of_week": 1, "start_time": "09:00:00", "end_time": "10:00:00"}]})
    assert own_response.status_code == 200


def test_appointments_are_isolated_between_tenants(client, db_session):
    tenant_a, owner_a = create_tenant_with_owner(db_session, name="Tenant A", owner_email="ownera@test.internal")
    create_tenant_with_owner(db_session, name="Tenant B", owner_email="ownerb@test.internal")

    login(client, "ownera@test.internal", "OwnerPass!2345")
    client.put(
        f"/api/tenant/availability/{owner_a.id}", json={"windows": [{"day_of_week": 0, "start_time": "09:00:00", "end_time": "10:00:00"}]}
    )
    client.post("/api/tenant/appointment-types", json={"name": "A-only type", "duration_minutes": 30})
    client.post("/api/auth/logout")

    login(client, "ownerb@test.internal", "OwnerPass!2345")
    types = client.get("/api/tenant/appointment-types").json()
    assert types == []
    appointments = client.get("/api/tenant/appointments").json()
    assert appointments == []
