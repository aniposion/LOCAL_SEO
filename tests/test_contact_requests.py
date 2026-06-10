from uuid import uuid4

from app.core.security import create_access_token, get_password_hash
from app.models.account import Account, AccountRole
from app.models.contact import ContactRequest
from app.models.notification import NotificationEvent


def _admin_headers(db):
    admin = Account(
        id=uuid4(),
        email="admin@example.com",
        password_hash=get_password_hash("testpassword123"),
        role=AccountRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    token = create_access_token(subject=str(admin.id))
    return {"Authorization": f"Bearer {token}"}


def test_public_contact_request_is_persisted_and_notifies_admin(client, db):
    headers = _admin_headers(db)

    response = client.post(
        "/contact/requests",
        json={
            "name": "Jane Kim",
            "email": "JANE@example.com",
            "subject": "Managed local SEO pilot",
            "message": "I want to review a pilot for my plumbing company.",
            "phone": "555-0100",
            "business_name": "Jane Plumbing",
            "audit_id": "audit-123",
            "metadata": {"utm_source": "test"},
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "jane@example.com"
    assert payload["status"] == "new"
    assert payload["recommended_package"] == "calls_growth"
    assert payload["lead_score"] >= 70

    stored = db.query(ContactRequest).filter(ContactRequest.email == "jane@example.com").one()
    assert stored.business_name == "Jane Plumbing"
    assert stored.audit_id == "audit-123"
    assert stored.extra_data == {"utm_source": "test"}
    assert stored.recommended_package == "calls_growth"

    notification = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.type == "contact_request_new")
        .one()
    )
    assert "Jane Kim" in notification.body
    assert "Lead score" in notification.body
    assert notification.url == "/admin"

    list_response = client.get("/contact/requests", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


def test_contact_request_list_requires_admin(client, auth_headers):
    response = client.get("/contact/requests", headers=auth_headers)

    assert response.status_code == 403


def test_admin_can_update_contact_request_status(client, db):
    headers = _admin_headers(db)
    create_response = client.post(
        "/contact/requests",
        json={
            "name": "Sam Lee",
            "email": "sam@example.com",
            "message": "Please tell me whether a pilot makes sense.",
        },
    )
    request_id = create_response.json()["id"]

    update_response = client.patch(
        f"/contact/requests/{request_id}",
        headers=headers,
        json={"status": "contacted", "sales_notes": "Left voicemail and sent pricing."},
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["status"] == "contacted"
    assert payload["sales_notes"] == "Left voicemail and sent pricing."
    assert payload["contacted_at"] is not None
    assert payload["closed_at"] is None


def test_admin_can_progress_contact_request_to_won(client, db):
    headers = _admin_headers(db)
    create_response = client.post(
        "/contact/requests",
        json={
            "name": "Taylor Park",
            "email": "taylor@example.com",
            "message": "We want to book a managed pilot for a competitive market.",
            "metadata": {"audit_id": "audit-won-1"},
        },
    )
    request_id = create_response.json()["id"]

    booked_response = client.patch(
        f"/contact/requests/{request_id}",
        headers=headers,
        json={"status": "booked", "sales_notes": "Discovery call booked."},
    )
    assert booked_response.status_code == 200
    assert booked_response.json()["status"] == "booked"
    assert booked_response.json()["booked_at"] is not None
    assert booked_response.json()["audit_id"] == "audit-won-1"

    won_response = client.patch(
        f"/contact/requests/{request_id}",
        headers=headers,
        json={"status": "won", "close_reason": "Signed three-month pilot."},
    )
    assert won_response.status_code == 200
    payload = won_response.json()
    assert payload["status"] == "won"
    assert payload["won_at"] is not None
    assert payload["closed_at"] is not None
    assert payload["close_reason"] == "Signed three-month pilot."


def test_admin_contact_summary_reports_conversion_and_sla(client, db):
    headers = _admin_headers(db)
    first = client.post(
        "/contact/requests",
        json={
            "name": "Won Lead",
            "email": "won@example.com",
            "message": "Ready to start a managed pilot.",
        },
    )
    second = client.post(
        "/contact/requests",
        json={
            "name": "Open Lead",
            "email": "open@example.com",
            "message": "Please review our business.",
        },
    )
    assert first.status_code == 201
    assert second.status_code == 201

    won_id = first.json()["id"]
    update = client.patch(
        f"/contact/requests/{won_id}",
        headers=headers,
        json={"status": "won"},
    )
    assert update.status_code == 200

    response = client.get("/contact/summary", headers=headers)
    assert response.status_code == 200

    summary = response.json()
    assert summary["total"] == 2
    assert summary["by_status"]["new"] == 1
    assert summary["by_status"]["won"] == 1
    assert summary["booked_conversion_rate"] == 50.0
    assert summary["won_conversion_rate"] == 50.0
    assert summary["avg_first_response_hours"] is not None
    assert summary["sla_target_hours"] == 24


def test_contact_request_validates_message_length(client):
    response = client.post(
        "/contact/requests",
        json={
            "name": "Too Short",
            "email": "short@example.com",
            "message": "hey",
        },
    )

    assert response.status_code == 422


def test_contact_request_throttles_recent_duplicate_email(client):
    payload = {
        "name": "Repeat Lead",
        "email": "repeat@example.com",
        "message": "Please review my managed pilot request.",
    }

    first = client.post("/contact/requests", json=payload)
    second = client.post("/contact/requests", json=payload)

    assert first.status_code == 201
    assert second.status_code == 429


def test_contact_requests_are_prioritized_by_lead_score(client, db):
    headers = _admin_headers(db)
    low = client.post(
        "/contact/requests",
        json={
            "name": "Low Intent",
            "email": "low@example.com",
            "message": "Just curious about the product.",
        },
    )
    high = client.post(
        "/contact/requests",
        json={
            "name": "High Intent",
            "email": "high@example.com",
            "subject": "Competitive managed pilot pricing",
            "message": (
                "We have multiple locations, a competitive market, and need to start a "
                "managed pilot after reviewing pricing and review-gap priorities."
            ),
            "phone": "555-0000",
            "business_name": "High Intent Dental",
            "source": "pricing_page",
        },
    )

    assert low.status_code == 201
    assert high.status_code == 201
    assert high.json()["recommended_package"] == "competitive_market"
    assert high.json()["lead_score"] > low.json()["lead_score"]

    response = client.get("/contact/requests", headers=headers)

    assert response.status_code == 200
    requests = response.json()["requests"]
    assert requests[0]["email"] == "high@example.com"
