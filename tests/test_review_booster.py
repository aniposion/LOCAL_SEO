from datetime import date

from app.models.analytics import Analytics
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.review_booster import BoosterRequest, CampaignStatus, PrivateFeedback, ReviewCampaign
from app.services.review_booster import ReviewBoosterService


def _create_campaign(db, location_id, name="Spring Push"):
    campaign = ReviewCampaign(
        location_id=location_id,
        name=name,
        channels=["sms"],
        google_review_url="https://g.page/r/test-review",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def _create_request(db, campaign_id, location_id, name="Kim"):
    request = BoosterRequest(
        campaign_id=campaign_id,
        location_id=location_id,
        customer_name=name,
        customer_phone="5551234567",
        consent_given=True,
        consent_method="pos",
        channel="sms",
        status="pending",
        message_content="Please leave a review",
        google_link_included=True,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def test_create_review_campaign_success(client, auth_headers, test_location):
    response = client.post(
        f"/review-booster/campaigns?location_id={test_location.id}",
        headers=auth_headers,
        json={
            "name": "Spring Push",
            "channels": ["sms"],
            "google_review_url": "https://g.page/r/test-review",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["location_id"] == str(test_location.id)
    assert data["name"] == "Spring Push"
    assert data["status"] == "active"


def test_create_review_campaign_for_other_location_forbidden(
    client, auth_headers, other_location
):
    response = client.post(
        f"/review-booster/campaigns?location_id={other_location.id}",
        headers=auth_headers,
        json={
            "name": "Blocked",
            "channels": ["sms"],
            "google_review_url": "https://g.page/r/test-review",
        },
    )

    assert response.status_code == 404


def test_list_get_update_delete_campaign_flow(client, db, auth_headers, test_location):
    campaign = _create_campaign(db, test_location.id)

    list_response = client.get(
        f"/review-booster/campaigns?location_id={test_location.id}",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = client.get(
        f"/review-booster/campaigns/{campaign.id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()["id"] == str(campaign.id)

    update_response = client.put(
        f"/review-booster/campaigns/{campaign.id}",
        headers=auth_headers,
        json={"name": "Updated Push", "status": "paused"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Updated Push"
    assert updated["status"] == "paused"

    delete_response = client.delete(
        f"/review-booster/campaigns/{campaign.id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 200
    db.refresh(campaign)
    assert campaign.status.value == "completed"


def test_send_review_request_success(client, db, auth_headers, test_location):
    campaign = _create_campaign(db, test_location.id, name="Request Campaign")

    response = client.post(
        f"/review-booster/requests/send?location_id={test_location.id}",
        headers=auth_headers,
        json={
            "campaign_id": str(campaign.id),
            "customer_name": "Kim",
            "customer_phone": "5551234567",
            "channel": "sms",
            "consent_given": True,
            "consent_method": "pos",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["campaign_id"] == str(campaign.id)
    assert data["location_id"] == str(test_location.id)
    assert data["status"] == "pending"
    assert data["google_link_included"] is True
    db.refresh(campaign)
    assert campaign.total_sent == 0


def test_send_review_request_rejects_completed_campaign(client, db, auth_headers, test_location):
    campaign = _create_campaign(db, test_location.id, name="Completed Campaign")
    campaign.status = CampaignStatus.COMPLETED
    db.add(campaign)
    db.commit()

    response = client.post(
        f"/review-booster/requests/send?location_id={test_location.id}",
        headers=auth_headers,
        json={
            "campaign_id": str(campaign.id),
            "customer_name": "Kim",
            "customer_phone": "5551234567",
            "channel": "sms",
            "consent_given": True,
            "consent_method": "pos",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Completed campaigns cannot send new review requests"


def test_request_detail_and_optout_flow(client, db, auth_headers, test_location):
    campaign = _create_campaign(db, test_location.id)
    request = _create_request(db, campaign.id, test_location.id)

    detail_response = client.get(
        f"/review-booster/requests/{request.id}",
        headers=auth_headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == str(request.id)

    add_optout = client.post(
        f"/review-booster/optouts?location_id={test_location.id}",
        headers=auth_headers,
        json={"phone": "5551234567", "reason": "requested"},
    )
    assert add_optout.status_code == 200
    assert add_optout.json()["is_opted_out"] is True

    check_optout = client.get(
        f"/review-booster/optouts/check?location_id={test_location.id}&phone=5551234567",
        headers=auth_headers,
    )
    assert check_optout.status_code == 200
    assert check_optout.json()["is_opted_out"] is True


def test_feedback_list_get_update_flow(client, db, auth_headers, test_location):
    feedback = PrivateFeedback(
        location_id=test_location.id,
        rating=2,
        feedback_text="Service was slow",
        customer_name="Lee",
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    list_response = client.get(
        f"/review-booster/feedbacks?location_id={test_location.id}",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = client.get(
        f"/review-booster/feedbacks/{feedback.id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "new"

    update_response = client.put(
        f"/review-booster/feedbacks/{feedback.id}",
        headers=auth_headers,
        json={"status": "resolved", "notes": "Called customer back"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "resolved"
    assert updated["notes"] == "Called customer back"


def test_list_review_requests_blocks_other_location(
    client, auth_headers, other_location
):
    response = client.get(
        f"/review-booster/requests?location_id={other_location.id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_requeue_failed_request_success(client, db, auth_headers, test_location):
    campaign = _create_campaign(db, test_location.id)
    request = _create_request(db, campaign.id, test_location.id)
    request.status = "failed"
    request.retry_count = 3
    request.last_error = "provider error"
    db.commit()

    response = client.post(
        f"/review-booster/requests/{request.id}/requeue",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["retry_count"] == 0
    assert data["last_error"] is None


def test_requeue_non_failed_request_rejected(client, db, auth_headers, test_location):
    campaign = _create_campaign(db, test_location.id)
    request = _create_request(db, campaign.id, test_location.id)

    response = client.post(
        f"/review-booster/requests/{request.id}/requeue",
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_review_booster_analytics_and_templates(client, db, auth_headers, test_location):
    campaign_active = _create_campaign(db, test_location.id, name="Active")
    campaign_paused = _create_campaign(db, test_location.id, name="Paused")
    campaign_paused.status = "paused"
    db.commit()

    delivered = _create_request(db, campaign_active.id, test_location.id, name="Delivered")
    delivered.status = "delivered"
    delivered.delivered_at = delivered.created_at

    failed = _create_request(db, campaign_active.id, test_location.id, name="Failed")
    failed.status = "failed"
    failed.retry_count = 2
    failed.next_retry_at = failed.created_at
    failed.last_error = "provider error"

    opted_out = _create_request(db, campaign_paused.id, test_location.id, name="Opted out")
    opted_out.status = "opted_out"
    opted_out.opted_out_at = opted_out.created_at

    db.commit()

    analytics_response = client.get(
        f"/review-booster/analytics/{test_location.id}?days=30",
        headers=auth_headers,
    )
    assert analytics_response.status_code == 200
    analytics = analytics_response.json()
    assert analytics["total_campaigns"] == 2
    assert analytics["active_campaigns"] == 1
    assert analytics["paused_campaigns"] == 1
    assert analytics["delivered_requests"] == 1
    assert analytics["failed_requests"] == 1
    assert analytics["pending_retries"] == 1
    assert analytics["opted_out_requests"] == 1
    assert analytics["attention_requests"] == 3

    templates_response = client.get("/review-booster/templates", headers=auth_headers)
    assert templates_response.status_code == 200
    templates = templates_response.json()
    assert templates["sms_templates"][0]["template"].startswith("Hi ")
    assert "customer_name" in templates["placeholders"][0]


async def test_legacy_review_booster_analytics_uses_current_analytics_model(db, test_location):
    db.add_all(
        [
            Analytics(
                location_id=test_location.id,
                platform="GBP",
                date=date.today(),
                source_raw={"new_reviews": 3, "avg_rating": 4.5},
            ),
            Analytics(
                location_id=test_location.id,
                platform="GBP",
                date=date.today(),
                source_raw={"new_reviews": 1, "avg_rating": 3.0},
            ),
        ]
    )
    db.commit()

    analytics = await ReviewBoosterService(db).get_review_analytics(test_location.id, days=30)

    assert analytics["total_reviews"] == 4
    assert analytics["average_rating"] == 4.12
    assert sum(analytics["reviews_by_week"].values()) == 4
    assert analytics["projected_monthly"] == 4


async def test_negative_review_creates_owner_notification(db, test_location, monkeypatch):
    captured_email = {}

    async def fake_send_email(self, to_email, subject, html_body, text_body):
        captured_email["to"] = to_email
        captured_email["subject"] = subject
        return {"success": True, "provider": "test"}

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    service = ReviewBoosterService(db)
    result = await service.handle_new_review(
        test_location.id,
        {
            "rating": 2,
            "reviewer_name": "Unhappy Customer",
            "review_text": "The wait was too long and the order was wrong.",
        },
    )

    assert result["success"] is True
    assert result["action"] == "internal_handling"
    assert captured_email["to"] == "test@example.com"
    assert "Negative review needs follow-up" in captured_email["subject"]

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_location.account_id)
        .order_by(NotificationEvent.created_at.desc())
        .first()
    )
    assert event is not None
    assert event.type == "review_booster_negative_review"
    assert event.url == f"/dashboard/reviews?locationId={test_location.id}"
    assert "Unhappy Customer" in event.body
    assert "Rating: 2" in event.body

    delivery = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.account_id == test_location.account_id)
        .order_by(NotificationDeliveryLog.attempted_at.desc())
        .first()
    )
    assert delivery is not None
    assert delivery.notification_event_id == event.id
    assert delivery.delivery_status == "delivered"
