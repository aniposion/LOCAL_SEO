from datetime import date, timedelta

import pytest


def test_vapid_key_returns_503_when_unconfigured(client, auth_headers):
    """GET /notifications/vapid-key returns 503 when VAPID is not configured."""
    response = client.get("/notifications/vapid-key", headers=auth_headers)
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_preferences_put_succeeds(client, auth_headers):
    """PUT /notifications/preferences always succeeds (storage is always available)."""
    response = client.put(
        "/notifications/preferences",
        headers=auth_headers,
        json={
            "new_reviews": True,
            "content_ready": True,
            "approval_reminders": True,
            "weekly_reports": True,
            "missed_calls": True,
            "new_messages": True,
            "performance_alerts": True,
            "email_notifications": True,
            "push_notifications": True,
        },
    )
    assert response.status_code == 200


def test_notification_history_returns_real_data(client, auth_headers):
    """History endpoint returns real persisted data with storage_available=True."""
    response = client.get("/notifications/history", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["notifications"], list)
    assert isinstance(payload["unread_count"], int)
    assert payload["storage_available"] is True
    assert payload["source"] == "database"


def test_notification_history_empty_initially(client, auth_headers):
    """History is empty for a fresh account."""
    response = client.get("/notifications/history", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["notifications"] == []
    assert payload["unread_count"] == 0


def test_notification_test_endpoint_persists_to_inbox(client, auth_headers):
    """POST /notifications/test persists a notification event to the inbox."""
    response = client.post(
        "/notifications/test",
        headers=auth_headers,
        json={"type": "content_ready"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "notification_id" in data
    assert data["push_delivered"] is False  # VAPID not configured in tests

    # Verify the notification appears in history
    history = client.get("/notifications/history", headers=auth_headers)
    assert history.status_code == 200
    items = history.json()["notifications"]
    assert len(items) == 1
    assert items[0]["type"] == "content_ready"
    assert items[0]["read"] is False


def test_notification_mark_read(client, auth_headers):
    """POST /notifications/history/{id}/read marks a notification as read."""
    # Create a notification via the test endpoint
    create = client.post(
        "/notifications/test",
        headers=auth_headers,
        json={"type": "new_review"},
    )
    assert create.status_code == 200
    nid = create.json()["notification_id"]

    # Mark as read
    mark = client.post(f"/notifications/history/{nid}/read", headers=auth_headers)
    assert mark.status_code == 200
    assert mark.json()["success"] is True

    # Verify it shows as read in history
    history = client.get("/notifications/history", headers=auth_headers)
    items = history.json()["notifications"]
    item = next((n for n in items if n["id"] == nid), None)
    assert item is not None
    assert item["read"] is True
    assert history.json()["unread_count"] == 0


def test_notification_mark_read_404_for_unknown(client, auth_headers):
    """Marking a non-existent notification returns 404."""
    import uuid
    fake_id = str(uuid.uuid4())
    response = client.post(f"/notifications/history/{fake_id}/read", headers=auth_headers)
    assert response.status_code == 404


def test_notification_delete_removes_inbox_event_but_keeps_delivery_audit(client, auth_headers):
    """DELETE /notifications/history/{id} removes the inbox event and preserves audit rows."""
    create = client.post(
        "/notifications/test",
        headers=auth_headers,
        json={"type": "weekly_report"},
    )
    assert create.status_code == 200
    notification_id = create.json()["notification_id"]

    delete = client.delete(f"/notifications/history/{notification_id}", headers=auth_headers)
    assert delete.status_code == 200
    assert delete.json()["success"] is True
    assert delete.json()["id"] == notification_id

    history = client.get("/notifications/history", headers=auth_headers)
    assert history.status_code == 200
    assert history.json()["notifications"] == []
    assert history.json()["unread_count"] == 0

    audit = client.get("/notifications/delivery-audit", headers=auth_headers)
    assert audit.status_code == 200
    logs = audit.json()["logs"]
    assert len(logs) >= 1
    assert all(log["notification_event_id"] is None for log in logs)


def test_notification_delete_404_for_unknown(client, auth_headers):
    """Deleting a non-existent notification returns 404."""
    import uuid

    fake_id = str(uuid.uuid4())
    response = client.delete(f"/notifications/history/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_notification_mark_all_read(client, auth_headers):
    """POST /notifications/history/read-all marks all unread as read."""
    # Create two notifications
    for _ in range(2):
        client.post("/notifications/test", headers=auth_headers, json={"type": "content_ready"})

    history_before = client.get("/notifications/history", headers=auth_headers).json()
    assert history_before["unread_count"] == 2

    mark_all = client.post("/notifications/history/read-all", headers=auth_headers)
    assert mark_all.status_code == 200
    assert mark_all.json()["success"] is True

    history_after = client.get("/notifications/history", headers=auth_headers).json()
    assert history_after["unread_count"] == 0
    assert all(n["read"] for n in history_after["notifications"])


def test_notification_mark_all_read_empty(client, auth_headers):
    """POST /notifications/history/read-all returns 200 even when inbox is empty."""
    response = client.post("/notifications/history/read-all", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_notification_preferences_return_defaults_with_metadata(client, auth_headers):
    response = client.get("/notifications/preferences", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted"] is False
    assert payload["storage_available"] is True
    assert payload["source"] == "defaults"
    assert payload["note"]


# ---------------------------------------------------------------------------
# Push subscription storage tests
# ---------------------------------------------------------------------------


def test_push_subscribe_stores_subscription(client, auth_headers):
    """POST /notifications/subscribe persists the subscription and returns 200."""
    response = client.post(
        "/notifications/subscribe",
        headers=auth_headers,
        json={
            "endpoint": "https://push.example.com/sub/abc123",
            "p256dh_key": "BNcDeKeyBase64==",
            "auth_key": "authSecret==",
            "device_type": "web",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["created"] is True


def test_push_subscribe_upserts_on_same_endpoint(client, auth_headers):
    """Re-subscribing the same endpoint updates keys without creating a duplicate."""
    endpoint = "https://push.example.com/sub/same-endpoint"
    for i in range(2):
        resp = client.post(
            "/notifications/subscribe",
            headers=auth_headers,
            json={
                "endpoint": endpoint,
                "p256dh_key": f"key-v{i}==",
                "auth_key": f"auth-v{i}==",
            },
        )
        assert resp.status_code == 200

    # Should have exactly one subscription, not two.
    subs = client.get("/notifications/subscriptions", headers=auth_headers)
    assert subs.status_code == 200
    assert subs.json()["count"] == 1
    # Second call should report it was an update, not a new creation.
    assert resp.json()["created"] is False


def test_push_subscribe_multiple_devices(client, auth_headers):
    """Different endpoints are stored as separate subscriptions."""
    for i in range(3):
        client.post(
            "/notifications/subscribe",
            headers=auth_headers,
            json={
                "endpoint": f"https://push.example.com/sub/device-{i}",
                "p256dh_key": f"key-{i}==",
                "auth_key": f"auth-{i}==",
            },
        )

    subs = client.get("/notifications/subscriptions", headers=auth_headers)
    assert subs.status_code == 200
    data = subs.json()
    assert data["count"] == 3
    assert len(data["subscriptions"]) == 3
    for item in data["subscriptions"]:
        assert "id" in item
        assert "device_type" in item
        assert "created_at" in item


def test_push_unsubscribe_removes_subscription(client, auth_headers):
    """DELETE /notifications/subscribe removes a stored subscription."""
    endpoint = "https://push.example.com/sub/to-remove"
    client.post(
        "/notifications/subscribe",
        headers=auth_headers,
        json={"endpoint": endpoint, "p256dh_key": "key==", "auth_key": "auth=="},
    )

    resp = client.delete(
        f"/notifications/subscribe?endpoint={endpoint}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["removed"] is True

    # Verify it's gone.
    subs = client.get("/notifications/subscriptions", headers=auth_headers)
    assert subs.json()["count"] == 0


def test_push_unsubscribe_unknown_endpoint_returns_removed_false(client, auth_headers):
    """DELETE with an unknown endpoint is idempotent and returns removed=False."""
    resp = client.delete(
        "/notifications/subscribe?endpoint=https%3A%2F%2Fnothing.example.com",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["removed"] is False


def test_remove_stored_subscription_by_id(client, auth_headers):
    """DELETE /notifications/subscriptions/{id} removes a stored device by record id."""
    create = client.post(
        "/notifications/subscribe",
        headers=auth_headers,
        json={
            "endpoint": "https://push.example.com/sub/remove-by-id",
            "p256dh_key": "remove-key==",
            "auth_key": "remove-auth==",
        },
    )
    assert create.status_code == 200

    subs = client.get("/notifications/subscriptions", headers=auth_headers)
    assert subs.status_code == 200
    subscription_id = subs.json()["subscriptions"][0]["id"]

    remove = client.delete(f"/notifications/subscriptions/{subscription_id}", headers=auth_headers)
    assert remove.status_code == 200
    assert remove.json()["removed"] is True

    after = client.get("/notifications/subscriptions", headers=auth_headers)
    assert after.json()["count"] == 0


def test_remove_stored_subscription_isolated_per_account(client, auth_headers, other_auth_headers):
    """One account cannot remove another account's stored push subscription by id."""
    client.post(
        "/notifications/subscribe",
        headers=auth_headers,
        json={
            "endpoint": "https://push.example.com/sub/owned-by-primary",
            "p256dh_key": "primary-key==",
            "auth_key": "primary-auth==",
        },
    )
    subs = client.get("/notifications/subscriptions", headers=auth_headers).json()
    subscription_id = subs["subscriptions"][0]["id"]

    remove = client.delete(f"/notifications/subscriptions/{subscription_id}", headers=other_auth_headers)
    assert remove.status_code == 200
    assert remove.json()["removed"] is False


def test_push_subscriptions_isolated_per_account(client, auth_headers, other_auth_headers):
    """Each account only sees its own push subscriptions."""
    client.post(
        "/notifications/subscribe",
        headers=auth_headers,
        json={"endpoint": "https://push.example.com/sub/acc1", "p256dh_key": "k==", "auth_key": "a=="},
    )

    other_subs = client.get("/notifications/subscriptions", headers=other_auth_headers)
    assert other_subs.status_code == 200
    assert other_subs.json()["count"] == 0


def test_push_subscriptions_empty_initially(client, auth_headers):
    """GET /notifications/subscriptions returns empty list for a fresh account."""
    resp = client.get("/notifications/subscriptions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["subscriptions"] == []


def test_notification_health_summary_empty_initially(client, auth_headers):
    """Health summary is honest for a fresh account with no subscriptions or audit data."""
    response = client.get("/notifications/health-summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["subscription_count"] == 0
    assert data["unread_count"] == 0
    assert data["last_delivery_status"] is None
    assert data["recent_delivered_count"] == 0
    assert data["source"] == "database"


def test_notification_health_summary_reflects_subscriptions_and_delivery(client, auth_headers):
    """Health summary includes stored subscriptions and recent delivery counts."""
    client.post(
        "/notifications/subscribe",
        headers=auth_headers,
        json={
            "endpoint": "https://push.example.com/sub/health",
            "p256dh_key": "health-key==",
            "auth_key": "health-auth==",
        },
    )
    client.post("/notifications/test", headers=auth_headers, json={"type": "content_ready"})

    response = client.get("/notifications/health-summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["subscription_count"] == 1
    assert data["last_delivery_channel"] in {"push", "inbox"}
    assert data["recent_delivered_count"] >= 1
    assert data["recent_unavailable_count"] >= 1 or data["recent_skipped_count"] >= 1


def test_notification_health_summary_isolated_per_account(client, auth_headers, other_auth_headers):
    """Each account only sees its own notification health summary."""
    client.post(
        "/notifications/subscribe",
        headers=auth_headers,
        json={
            "endpoint": "https://push.example.com/sub/primary",
            "p256dh_key": "primary-key==",
            "auth_key": "primary-auth==",
        },
    )
    client.post("/notifications/test", headers=auth_headers, json={"type": "new_review"})

    response = client.get("/notifications/health-summary", headers=other_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["subscription_count"] == 0
    assert data["unread_count"] == 0


# ---------------------------------------------------------------------------
# Delivery audit tests
# ---------------------------------------------------------------------------


def test_delivery_audit_empty_initially(client, auth_headers):
    """GET /notifications/delivery-audit returns empty list for a fresh account."""
    response = client.get("/notifications/delivery-audit", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["logs"] == []
    assert data["total"] == 0
    assert data["source"] == "database"


def test_delivery_audit_records_after_test_send(client, auth_headers):
    """POST /notifications/test creates delivery log entries for inbox and push channels."""
    send = client.post(
        "/notifications/test",
        headers=auth_headers,
        json={"type": "content_ready"},
    )
    assert send.status_code == 200
    nid = send.json()["notification_id"]

    audit = client.get("/notifications/delivery-audit", headers=auth_headers)
    assert audit.status_code == 200
    data = audit.json()

    # Must have at least 2 records: inbox (delivered) + push (unavailable/failed in tests)
    assert data["total"] >= 2
    assert len(data["logs"]) >= 2

    channels = {log["channel"] for log in data["logs"]}
    assert "inbox" in channels
    assert "push" in channels

    inbox_log = next(log for log in data["logs"] if log["channel"] == "inbox")
    assert inbox_log["delivery_status"] == "delivered"
    assert inbox_log["notification_event_id"] == nid
    assert inbox_log["failure_reason"] is None

    push_log = next(log for log in data["logs"] if log["channel"] == "push")
    # VAPID not configured in tests — must be unavailable/skipped, not fabricated success
    assert push_log["delivery_status"] in {"unavailable", "failed", "skipped"}
    assert push_log["notification_event_id"] == nid


def test_delivery_audit_push_never_reports_delivered_without_vapid(client, auth_headers):
    """Push channel must not report delivered when VAPID is unconfigured."""
    client.post("/notifications/test", headers=auth_headers, json={"type": "new_review"})
    audit = client.get("/notifications/delivery-audit", headers=auth_headers)
    data = audit.json()

    push_logs = [log for log in data["logs"] if log["channel"] == "push"]
    assert push_logs, "Expected at least one push delivery log"
    for log in push_logs:
        assert log["delivery_status"] in {"unavailable", "failed", "skipped"}, (
            f"Push reported delivered without VAPID: {log}"
        )


def test_delivery_audit_filter_by_channel(client, auth_headers):
    """GET /notifications/delivery-audit?channel=inbox returns only inbox logs."""
    client.post("/notifications/test", headers=auth_headers, json={"type": "weekly_report"})

    inbox_only = client.get(
        "/notifications/delivery-audit?channel=inbox", headers=auth_headers
    )
    assert inbox_only.status_code == 200
    data = inbox_only.json()
    assert data["total"] >= 1
    assert all(log["channel"] == "inbox" for log in data["logs"])


def test_delivery_audit_filter_by_status(client, auth_headers):
    """GET /notifications/delivery-audit?delivery_status=delivered returns only delivered logs."""
    client.post("/notifications/test", headers=auth_headers, json={"type": "content_ready"})

    delivered = client.get(
        "/notifications/delivery-audit?delivery_status=delivered", headers=auth_headers
    )
    assert delivered.status_code == 200
    data = delivered.json()
    assert all(log["delivery_status"] == "delivered" for log in data["logs"])


def test_delivery_audit_log_fields(client, auth_headers):
    """Each delivery log item has all required fields."""
    client.post("/notifications/test", headers=auth_headers, json={"type": "content_ready"})
    audit = client.get("/notifications/delivery-audit", headers=auth_headers)
    data = audit.json()

    for log in data["logs"]:
        assert "id" in log
        assert "channel" in log
        assert "delivery_status" in log
        assert "attempted_at" in log
        assert "created_at" in log
        # failure_reason and delivered_at may be None but must be present
        assert "failure_reason" in log
        assert "delivered_at" in log
        assert "notification_event_id" in log


def test_delivery_audit_isolated_per_account(client, auth_headers, other_auth_headers):
    """Each account only sees its own delivery logs."""
    client.post("/notifications/test", headers=auth_headers, json={"type": "content_ready"})

    other_audit = client.get("/notifications/delivery-audit", headers=other_auth_headers)
    assert other_audit.status_code == 200
    assert other_audit.json()["total"] == 0


def test_delivery_audit_filter_by_date_range(client, auth_headers):
    """A future date range returns no delivery logs for the current account."""
    client.post("/notifications/test", headers=auth_headers, json={"type": "content_ready"})
    future_day = (date.today() + timedelta(days=30)).isoformat()
    response = client.get(
        f"/notifications/delivery-audit?start_date={future_day}&end_date={future_day}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["logs"] == []


def test_delivery_audit_export_csv(client, auth_headers):
    """Export returns CSV output and includes at least one recorded notification row."""
    client.post("/notifications/test", headers=auth_headers, json={"type": "weekly_report"})

    response = client.get("/notifications/delivery-audit/export", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "notification-delivery-audit.csv" in response.headers["content-disposition"]
    body = response.text
    assert "account_email" in body
    assert "notification_type" in body
    assert "location_context" in body
    assert "inbox" in body or "push" in body
    assert "weekly_report" in body


def test_notification_preferences_can_be_persisted(client, db, test_user, auth_headers):
    response = client.put(
        "/notifications/preferences",
        headers=auth_headers,
        json={
            "new_reviews": False,
            "content_ready": True,
            "approval_reminders": False,
            "weekly_reports": True,
            "missed_calls": False,
            "new_messages": True,
            "performance_alerts": False,
            "email_notifications": False,
            "push_notifications": False,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted"] is True
    assert payload["storage_available"] is True
    assert payload["source"] == "account.settings"
    assert payload["new_reviews"] is False
    assert payload["quiet_hours_start"] == "22:00"
    assert payload["quiet_hours_end"] == "08:00"

    db.refresh(test_user)
    assert test_user.settings is not None
    assert test_user.settings["notification_preferences"]["new_reviews"] is False
    assert test_user.settings["notification_preferences"]["quiet_hours_start"] == "22:00"

    follow_up = client.get("/notifications/preferences", headers=auth_headers)
    assert follow_up.status_code == 200
    follow_up_payload = follow_up.json()
    assert follow_up_payload["persisted"] is True
    assert follow_up_payload["source"] == "account.settings"
    assert follow_up_payload["new_reviews"] is False


def test_delivery_audit_presets_can_be_persisted(client, auth_headers):
    """Delivery audit presets are stored in account settings rather than local-only state."""
    payload = [
        {
            "id": "recent-failures",
            "name": "Recent failures",
            "channel": "all",
            "delivery_status": "failed",
            "start_date": "2026-03-01",
            "end_date": "2026-03-28",
        }
    ]
    save = client.put("/notifications/delivery-audit/presets", headers=auth_headers, json=payload)
    assert save.status_code == 200
    assert save.json()["presets"][0]["name"] == "Recent failures"

    load = client.get("/notifications/delivery-audit/presets", headers=auth_headers)
    assert load.status_code == 200
    data = load.json()
    assert data["source"] == "account.settings"
    assert len(data["presets"]) == 1
    assert data["presets"][0]["delivery_status"] == "failed"
