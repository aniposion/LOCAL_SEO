from datetime import date, timedelta
import importlib
from contextlib import AbstractContextManager

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time import utc_now_aware
from app.core.security import get_password_hash
from app.jobs import metric_jobs, token_jobs
from app.jobs import review_booster_jobs
from app.models.account import Account, AccountRole
from app.models.credits import UsageRecord
from app.models.metrics import MetricSnapshot, SnapshotType, WeeklyReport
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.oauth import OAuthEvent, OAuthEventType, OAuthProvider, OAuthStatus, OAuthToken
from app.models.review_booster import BoosterRequest, RequestChannel, RequestStatus, ReviewCampaign

jobs_scheduler_module = importlib.import_module("app.jobs.scheduler")


def _job_session(db):
    return Session(bind=db.get_bind())


def _admin_account(db):
    admin = Account(
        email="jobs-admin@example.com",
        password_hash=get_password_hash("Adminpassword123!"),
        role=AccountRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


class _ExplodingSessionContext(AbstractContextManager):
    def __init__(self, message: str):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args, **kwargs):
        raise RuntimeError(self.message)


async def test_configure_jobs_registers_metric_and_token_jobs():
    jobs_scheduler_module.scheduler.remove_all_jobs()

    try:
        jobs_scheduler_module.configure_jobs()
        job_ids = {job.id for job in jobs_scheduler_module.scheduler.get_jobs()}
        assert "daily_snapshots" in job_ids
        assert "weekly_reports" in job_ids
        assert "token_refresh_check" in job_ids
    finally:
        jobs_scheduler_module.scheduler.remove_all_jobs()


async def test_enqueue_daily_snapshots_smoke(db, test_location, monkeypatch):
    monkeypatch.setattr(metric_jobs, "_session", lambda: _job_session(db))

    async def fake_fetch_gbp_metrics(_location_id):
        return {
            "calls": 12,
            "directions": 4,
            "website_clicks": 8,
            "profile_views": 33,
            "photo_views": 5,
            "total_reviews": 20,
            "new_reviews": 2,
            "avg_rating": 4.8,
            "call_value": "65.00",
        }

    monkeypatch.setattr(metric_jobs, "fetch_gbp_metrics", fake_fetch_gbp_metrics)

    await metric_jobs.enqueue_daily_snapshots()

    snapshots = (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.location_id == test_location.id)
        .all()
    )
    assert len(snapshots) == 1
    assert snapshots[0].snapshot_type == SnapshotType.DAILY
    assert snapshots[0].snapshot_date == date.today()
    assert snapshots[0].calls == 12
    assert snapshots[0].directions == 4
    assert snapshots[0].raw_data["source"] == "gbp_api"
    assert snapshots[0].raw_data["source_kind"] == "metric_jobs"
    assert snapshots[0].raw_data["payload"]["call_value"] == "65.00"


async def test_enqueue_daily_snapshots_carries_forward_last_snapshot_when_gbp_unavailable(
    db, test_location, monkeypatch
):
    monkeypatch.setattr(metric_jobs, "_session", lambda: _job_session(db))

    previous_date = date.today() - timedelta(days=1)
    previous_snapshot = MetricSnapshot(
        location_id=test_location.id,
        snapshot_date=previous_date,
        snapshot_type=SnapshotType.DAILY,
        calls=7,
        directions=3,
        website_clicks=11,
        profile_views=19,
        photo_views=2,
        total_reviews=8,
        new_reviews=1,
        call_value=55,
    )
    db.add(previous_snapshot)
    db.commit()

    async def fake_fetch_gbp_metrics(_location_id):
        return None

    monkeypatch.setattr(metric_jobs, "fetch_gbp_metrics", fake_fetch_gbp_metrics)

    await metric_jobs.enqueue_daily_snapshots()

    snapshots = (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.location_id == test_location.id)
        .order_by(MetricSnapshot.snapshot_date.asc())
        .all()
    )
    assert len(snapshots) == 2
    carried = snapshots[-1]
    assert carried.snapshot_date == date.today()
    assert carried.calls == previous_snapshot.calls
    assert carried.directions == previous_snapshot.directions
    assert carried.raw_data["source"] == "carry_forward"
    assert carried.raw_data["source_snapshot_id"] == str(previous_snapshot.id)
    assert carried.raw_data["source_snapshot_date"] == previous_date.isoformat()
    assert carried.raw_data["reason"] == "gbp_metrics_unavailable"


async def test_enqueue_daily_snapshots_skips_without_data_or_previous_snapshot(
    db, test_location, monkeypatch
):
    monkeypatch.setattr(metric_jobs, "_session", lambda: _job_session(db))

    async def fake_fetch_gbp_metrics(_location_id):
        return None

    monkeypatch.setattr(metric_jobs, "fetch_gbp_metrics", fake_fetch_gbp_metrics)

    await metric_jobs.enqueue_daily_snapshots()

    snapshots = (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.location_id == test_location.id)
        .all()
    )
    assert snapshots == []

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_location.account_id,
            NotificationEvent.type == "daily_snapshot_unavailable",
        )
        .one()
    )
    assert event.url == f"/dashboard/analytics?locationId={test_location.id}"
    assert "could not be created" in event.body.lower()
    assert "no previous snapshot to carry forward" in event.body.lower()


async def test_enqueue_daily_snapshots_unavailable_warning_is_throttled_per_week(
    db, test_location, monkeypatch
):
    monkeypatch.setattr(metric_jobs, "_session", lambda: _job_session(db))

    async def fake_fetch_gbp_metrics(_location_id):
        return None

    monkeypatch.setattr(metric_jobs, "fetch_gbp_metrics", fake_fetch_gbp_metrics)

    await metric_jobs.enqueue_daily_snapshots()
    await metric_jobs.enqueue_daily_snapshots()

    notifications = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_location.account_id,
            NotificationEvent.type == "daily_snapshot_unavailable",
        )
        .all()
    )
    assert len(notifications) == 1


async def test_enqueue_daily_snapshots_notifies_on_collection_failure(
    db, test_location, monkeypatch
):
    monkeypatch.setattr(metric_jobs, "_session", lambda: _job_session(db))

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    async def fake_process_daily_snapshot(_location_id):
        raise RuntimeError("gbp oauth unavailable")

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)
    monkeypatch.setattr(metric_jobs, "process_daily_snapshot", fake_process_daily_snapshot)

    await metric_jobs.enqueue_daily_snapshots()

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_location.account_id,
            NotificationEvent.type == "daily_snapshot_failed",
        )
        .one()
    )
    assert "Daily metrics collection failed" in event.title
    assert "gbp oauth unavailable" in event.body
    assert event.url == "/dashboard/analytics"

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"


async def test_enqueue_daily_snapshots_notifies_admin_on_top_level_failure(
    db, monkeypatch
):
    admin = _admin_account(db)
    sessions = [_ExplodingSessionContext("location scan failed"), _job_session(db)]

    monkeypatch.setattr(metric_jobs, "_session", lambda: sessions.pop(0))

    await metric_jobs.enqueue_daily_snapshots()

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == admin.id,
            NotificationEvent.type == "daily_snapshot_job_failed",
        )
        .one()
    )
    assert event.url == "/admin"
    assert "location scan failed" in event.body.lower()

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


async def test_enqueue_weekly_reports_smoke(db, test_location, monkeypatch):
    monkeypatch.setattr(metric_jobs, "_session", lambda: _job_session(db))

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 7)

    for offset in range(7):
        db.add(
            MetricSnapshot(
                location_id=test_location.id,
                snapshot_date=week_start + timedelta(days=offset),
                snapshot_type=SnapshotType.DAILY,
                calls=offset + 1,
                directions=offset,
                website_clicks=offset,
                profile_views=10 + offset,
                photo_views=5,
                total_reviews=20,
                new_reviews=1,
                call_value=50,
            )
        )
    db.commit()

    await metric_jobs.enqueue_weekly_reports()

    reports = (
        db.query(WeeklyReport)
        .filter(WeeklyReport.location_id == test_location.id)
        .all()
    )
    assert len(reports) == 1
    assert reports[0].report_week == week_start

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_location.account_id,
            NotificationEvent.type == "weekly_report_ready",
        )
        .one()
    )
    assert "Weekly report ready" in event.title
    assert event.url == f"/dashboard/reports?locationId={test_location.id}"

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"


async def test_enqueue_weekly_reports_skips_without_metric_snapshots(
    db, test_location, monkeypatch
):
    monkeypatch.setattr(metric_jobs, "_session", lambda: _job_session(db))

    await metric_jobs.enqueue_weekly_reports()

    reports = (
        db.query(WeeklyReport)
        .filter(WeeklyReport.location_id == test_location.id)
        .all()
    )
    assert reports == []


async def test_enqueue_weekly_reports_notifies_on_generation_failure(
    db, test_location, monkeypatch
):
    monkeypatch.setattr(metric_jobs, "_session", lambda: _job_session(db))

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    async def fake_process_weekly_report(location_id, account_id, report_week):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)
    monkeypatch.setattr(metric_jobs, "process_weekly_report", fake_process_weekly_report)

    await metric_jobs.enqueue_weekly_reports()

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_location.account_id,
            NotificationEvent.type == "weekly_report_failed",
        )
        .one()
    )
    assert "Weekly report generation failed" in event.title
    assert "storage unavailable" in event.body
    assert event.url == f"/dashboard/reports?locationId={test_location.id}"

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"


async def test_enqueue_weekly_reports_notifies_admin_on_top_level_failure(
    db, monkeypatch
):
    admin = _admin_account(db)
    sessions = [_ExplodingSessionContext("weekly report location scan failed"), _job_session(db)]

    monkeypatch.setattr(metric_jobs, "_session", lambda: sessions.pop(0))

    await metric_jobs.enqueue_weekly_reports()

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == admin.id,
            NotificationEvent.type == "weekly_report_job_failed",
        )
        .one()
    )
    assert event.url == "/admin"
    assert "weekly report location scan failed" in event.body.lower()

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


async def test_check_expiring_tokens_refreshes_token(db, test_user, test_location, monkeypatch):
    monkeypatch.setattr(token_jobs, "_session", lambda: _job_session(db))

    token = OAuthToken(
        account_id=test_user.id,
        location_id=test_location.id,
        provider=OAuthProvider.GOOGLE,
        access_token_ref="secret://old-access",
        refresh_token_ref="secret://old-refresh",
        expires_at=utc_now_aware() + timedelta(minutes=30),
        status=OAuthStatus.HEALTHY,
    )
    db.add(token)
    db.commit()

    async def fake_refresh_google_token(_token):
        return {
            "access_token_ref": "secret://new-access",
            "refresh_token_ref": "secret://new-refresh",
            "expires_at": utc_now_aware() + timedelta(days=30),
        }

    monkeypatch.setattr(token_jobs, "refresh_google_token", fake_refresh_google_token)

    await token_jobs.check_expiring_tokens()

    db.refresh(token)
    assert token.access_token_ref == "secret://new-access"
    assert token.refresh_token_ref == "secret://new-refresh"
    assert token.status == OAuthStatus.HEALTHY
    assert token.refresh_failure_count == 0

    event = (
        db.query(OAuthEvent)
        .filter(
            OAuthEvent.token_id == token.id,
            OAuthEvent.event_type == OAuthEventType.REFRESHED,
        )
        .one()
    )
    assert event.event_data["expires_at"]


async def test_check_expiring_tokens_marks_token_degraded_on_failure(
    db, test_user, test_location, monkeypatch
):
    monkeypatch.setattr(token_jobs, "_session", lambda: _job_session(db))

    token = OAuthToken(
        account_id=test_user.id,
        location_id=test_location.id,
        provider=OAuthProvider.GOOGLE,
        access_token_ref="secret://old-access",
        refresh_token_ref="secret://old-refresh",
        expires_at=utc_now_aware() + timedelta(minutes=30),
        status=OAuthStatus.HEALTHY,
    )
    db.add(token)
    db.commit()

    async def fake_refresh_google_token(_token):
        raise RuntimeError("refresh failed")

    monkeypatch.setattr(token_jobs, "refresh_google_token", fake_refresh_google_token)

    await token_jobs.check_expiring_tokens()

    db.refresh(token)
    assert token.status == OAuthStatus.DEGRADED
    assert token.refresh_failure_count == 1
    assert token.last_error == "refresh failed"

    event = (
        db.query(OAuthEvent)
        .filter(
            OAuthEvent.token_id == token.id,
            OAuthEvent.event_type == OAuthEventType.REFRESH_FAILED,
        )
        .one()
    )
    assert event.error_message == "refresh failed"


async def test_check_expiring_tokens_marks_token_needs_reauth_when_refresh_token_missing(
    db, test_user, test_location, monkeypatch
):
    monkeypatch.setattr(token_jobs, "_session", lambda: _job_session(db))
    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    token = OAuthToken(
        account_id=test_user.id,
        location_id=test_location.id,
        provider=OAuthProvider.GOOGLE,
        access_token_ref="secret://old-access",
        refresh_token_ref=None,
        expires_at=utc_now_aware() + timedelta(minutes=30),
        status=OAuthStatus.HEALTHY,
    )
    db.add(token)
    db.commit()

    await token_jobs.check_expiring_tokens()

    db.refresh(token)
    assert token.status == OAuthStatus.NEEDS_REAUTH
    assert token.refresh_failure_count == 1
    assert token.last_error_code == "REAUTH_REQUIRED"
    assert "reconnect required" in token.last_error.lower()

    event = (
        db.query(OAuthEvent)
        .filter(
            OAuthEvent.token_id == token.id,
            OAuthEvent.event_type == OAuthEventType.REFRESH_FAILED,
        )
        .one()
    )
    assert event.error_message == token.last_error

    notification_event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_user.id,
            NotificationEvent.type == "oauth_reauth_required",
        )
        .one()
    )
    assert "Reconnect Google integration" in notification_event.title
    assert notification_event.url == "/dashboard/integrations"

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == notification_event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"


async def test_check_expiring_tokens_notifies_admin_on_top_level_failure(
    db, monkeypatch
):
    admin = _admin_account(db)
    sessions = [_ExplodingSessionContext("oauth token query failed"), _job_session(db)]

    monkeypatch.setattr(token_jobs, "_session", lambda: sessions.pop(0))

    await token_jobs.check_expiring_tokens()

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == admin.id,
            NotificationEvent.type == "oauth_token_refresh_job_failed",
        )
        .one()
    )
    assert event.url == "/admin"
    assert "oauth token query failed" in event.body.lower()

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


async def test_check_expiring_tokens_notifies_admin_when_reauth_notification_fails(
    db, test_user, test_location, monkeypatch
):
    admin = _admin_account(db)
    monkeypatch.setattr(token_jobs, "_session", lambda: _job_session(db))

    async def fake_send_notification(self, **_kwargs):
        raise RuntimeError("notification provider offline")

    monkeypatch.setattr(
        "app.services.notification.NotificationService.send_notification",
        fake_send_notification,
    )

    token = OAuthToken(
        account_id=test_user.id,
        location_id=test_location.id,
        provider=OAuthProvider.GOOGLE,
        access_token_ref="secret://old-access",
        refresh_token_ref=None,
        expires_at=utc_now_aware() + timedelta(minutes=30),
        status=OAuthStatus.HEALTHY,
    )
    db.add(token)
    db.commit()

    await token_jobs.check_expiring_tokens()

    admin_event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == admin.id,
            NotificationEvent.type == "oauth_reauth_notification_failed",
        )
        .one()
    )
    assert admin_event.url == "/admin"
    assert "oauth reauth notification failed" in admin_event.title.lower()
    assert "notification provider offline" in admin_event.body.lower()
    assert test_user.email in admin_event.body

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == admin_event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


async def test_revoke_token_marks_revoked_and_logs_event(db, test_user, test_location, monkeypatch):
    monkeypatch.setattr(token_jobs, "_session", lambda: _job_session(db))

    token = OAuthToken(
        account_id=test_user.id,
        location_id=test_location.id,
        provider=OAuthProvider.GOOGLE,
        access_token_ref="secret://old-access",
        refresh_token_ref="secret://old-refresh",
        expires_at=utc_now_aware() + timedelta(days=1),
        status=OAuthStatus.HEALTHY,
    )
    db.add(token)
    db.commit()

    job_db = _job_session(db)
    try:
        await token_jobs.revoke_token(job_db, token.id)
    finally:
        job_db.close()

    db.refresh(token)
    assert token.status == OAuthStatus.REVOKED

    event = (
        db.query(OAuthEvent)
        .filter(
            OAuthEvent.token_id == token.id,
            OAuthEvent.event_type == OAuthEventType.REVOKED,
        )
        .one()
    )
    assert event.token_id == token.id


async def test_check_expiring_tokens_escalates_to_needs_reauth_after_three_failures(
    db, test_user, test_location, monkeypatch
):
    monkeypatch.setattr(token_jobs, "_session", lambda: _job_session(db))

    token = OAuthToken(
        account_id=test_user.id,
        location_id=test_location.id,
        provider=OAuthProvider.GOOGLE,
        access_token_ref="secret://old-access",
        refresh_token_ref="secret://old-refresh",
        expires_at=utc_now_aware() + timedelta(minutes=30),
        status=OAuthStatus.HEALTHY,
    )
    db.add(token)
    db.commit()

    async def fake_refresh_google_token(_token):
        raise RuntimeError("refresh failed")

    monkeypatch.setattr(token_jobs, "refresh_google_token", fake_refresh_google_token)

    await token_jobs.check_expiring_tokens()
    await token_jobs.check_expiring_tokens()
    await token_jobs.check_expiring_tokens()

    db.refresh(token)
    assert token.refresh_failure_count == 3
    assert token.status == OAuthStatus.NEEDS_REAUTH


def _create_review_campaign(db, location_id):
    campaign = ReviewCampaign(
        location_id=location_id,
        name="Job Campaign",
        channels=["sms"],
        google_review_url="https://g.page/r/test-review",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def _create_booster_request(db, campaign_id, location_id, customer_phone, status=RequestStatus.PENDING):
    request = BoosterRequest(
        campaign_id=campaign_id,
        location_id=location_id,
        customer_name="Customer",
        customer_phone=customer_phone,
        consent_given=True,
        consent_method="pos",
        channel=RequestChannel.SMS,
        status=status,
        message_content="Please leave a review",
        google_link_included=True,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


async def test_process_pending_review_requests_marks_failed_and_continues(
    db, test_location, monkeypatch
):
    monkeypatch.setattr(review_booster_jobs, "_session", lambda: _job_session(db))

    campaign = _create_review_campaign(db, test_location.id)
    first_request = _create_booster_request(db, campaign.id, test_location.id, "5551112222")
    second_request = _create_booster_request(db, campaign.id, test_location.id, "5553334444")

    async def fake_send_review_request(session, request):
        if request.id == first_request.id:
            raise RuntimeError("twilio send failed")
        request.status = RequestStatus.SENT
        request.sent_at = utc_now_aware()
        session.commit()

    monkeypatch.setattr(review_booster_jobs, "send_review_request", fake_send_review_request)

    await review_booster_jobs.process_pending_review_requests()

    db.refresh(first_request)
    db.refresh(second_request)
    assert first_request.status == RequestStatus.FAILED
    assert second_request.status == RequestStatus.SENT
    assert second_request.sent_at is not None
    assert first_request.retry_count == 1
    assert first_request.next_retry_at is not None
    assert first_request.last_error == "twilio send failed"


async def test_process_pending_review_requests_skips_failed_requests(
    db, test_location, monkeypatch
):
    monkeypatch.setattr(review_booster_jobs, "_session", lambda: _job_session(db))

    campaign = _create_review_campaign(db, test_location.id)
    failed_request = _create_booster_request(
        db, campaign.id, test_location.id, "5551112222", status=RequestStatus.FAILED
    )
    pending_request = _create_booster_request(
        db, campaign.id, test_location.id, "5553334444", status=RequestStatus.PENDING
    )
    processed_ids = []

    async def fake_send_review_request(session, request):
        processed_ids.append(request.id)
        request.status = RequestStatus.SENT
        request.sent_at = utc_now_aware()
        session.commit()

    monkeypatch.setattr(review_booster_jobs, "send_review_request", fake_send_review_request)

    await review_booster_jobs.process_pending_review_requests()

    db.refresh(failed_request)
    db.refresh(pending_request)
    assert failed_request.status == RequestStatus.FAILED
    assert pending_request.status == RequestStatus.SENT
    assert processed_ids == [pending_request.id]


async def test_process_pending_review_requests_requeues_eligible_failed_request(
    db, test_location, monkeypatch
):
    monkeypatch.setattr(review_booster_jobs, "_session", lambda: _job_session(db))

    campaign = _create_review_campaign(db, test_location.id)
    eligible_failed = _create_booster_request(
        db, campaign.id, test_location.id, "5551112222", status=RequestStatus.FAILED
    )
    eligible_failed.retry_count = 1
    eligible_failed.next_retry_at = utc_now_aware() - timedelta(minutes=1)
    db.commit()

    processed_ids = []

    async def fake_send_review_request(session, request):
        processed_ids.append(request.id)
        request.status = RequestStatus.SENT
        request.sent_at = utc_now_aware()
        request.next_retry_at = None
        session.commit()

    monkeypatch.setattr(review_booster_jobs, "send_review_request", fake_send_review_request)

    await review_booster_jobs.process_pending_review_requests()

    db.refresh(eligible_failed)
    assert eligible_failed.status == RequestStatus.SENT
    assert eligible_failed.id in processed_ids


async def test_process_pending_review_requests_notifies_on_terminal_failure(
    db, test_location, monkeypatch
):
    monkeypatch.setattr(review_booster_jobs, "_session", lambda: _job_session(db))

    campaign = _create_review_campaign(db, test_location.id)
    request = _create_booster_request(
        db, campaign.id, test_location.id, "5551112222", status=RequestStatus.FAILED
    )
    request.retry_count = review_booster_jobs.MAX_RETRY_ATTEMPTS - 1
    request.next_retry_at = utc_now_aware() - timedelta(minutes=1)
    db.commit()

    captured = {}

    async def fake_send_review_request(session, review_request):
        raise RuntimeError("provider hard failure")

    async def fake_send_notification(self, account_id, title, message, notification_type, data=None):
        captured["account_id"] = str(account_id)
        captured["title"] = title
        captured["message"] = message
        captured["notification_type"] = notification_type
        captured["data"] = data or {}
        return {"success": True}

    monkeypatch.setattr(review_booster_jobs, "send_review_request", fake_send_review_request)
    monkeypatch.setattr("app.services.notification.NotificationService.send_notification", fake_send_notification)

    await review_booster_jobs.process_pending_review_requests()

    db.refresh(request)
    assert request.status == RequestStatus.FAILED
    assert request.retry_count == review_booster_jobs.MAX_RETRY_ATTEMPTS
    assert request.next_retry_at is None
    assert request.last_error == "provider hard failure"
    assert captured["notification_type"] == "review_booster_delivery_failed"
    assert captured["data"]["request_id"] == str(request.id)


async def test_send_sms_request_records_sms_usage_on_success(
    db, test_location, monkeypatch
):
    campaign = _create_review_campaign(db, test_location.id)
    request = _create_booster_request(db, campaign.id, test_location.id, "5551112222")

    class DummyTwilio:
        async def send_sms(self, to, body, status_callback):
            return {"sid": "SM123"}

    monkeypatch.setattr(review_booster_jobs, "get_twilio_service", lambda: DummyTwilio())

    await review_booster_jobs.send_sms_request(db, request)

    db.refresh(request)
    db.refresh(campaign)
    assert request.status == RequestStatus.SENT
    assert campaign.total_sent == 1
    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_location.account_id,
            UsageRecord.usage_type == "sms",
        )
        .scalar()
    )
    assert int(total or 0) == 1


async def test_mark_request_sent_only_increments_campaign_once(
    db, test_location
):
    campaign = _create_review_campaign(db, test_location.id)
    request = _create_booster_request(db, campaign.id, test_location.id, "5551112222")

    review_booster_jobs._mark_request_sent(db, request, twilio_message_sid="SM123")
    review_booster_jobs._mark_request_sent(db, request, twilio_message_sid="SM123")

    db.refresh(campaign)
    db.refresh(request)
    assert campaign.total_sent == 1
    assert request.status == RequestStatus.SENT
    assert request.twilio_message_sid == "SM123"


async def test_process_pending_review_requests_stops_retry_on_sms_limit_failure(
    db, test_location, monkeypatch
):
    monkeypatch.setattr(review_booster_jobs, "_session", lambda: _job_session(db))

    campaign = _create_review_campaign(db, test_location.id)
    request = _create_booster_request(db, campaign.id, test_location.id, "5551112222")
    db.add(
        UsageRecord(
            account_id=test_location.account_id,
            usage_type="sms",
            date=utc_now_aware(),
            daily_count=10,
            monthly_count=10,
            last_used_at=utc_now_aware() - timedelta(minutes=5),
        )
    )
    db.commit()

    called = {"twilio": 0, "notify": 0}

    class DummyTwilio:
        async def send_sms(self, to, body, status_callback):
            called["twilio"] += 1
            return {"sid": "SM123"}

    async def fake_send_notification(self, account_id, title, message, notification_type, data=None):
        called["notify"] += 1
        return {"success": True}

    monkeypatch.setattr(review_booster_jobs, "get_twilio_service", lambda: DummyTwilio())
    monkeypatch.setattr("app.services.notification.NotificationService.send_notification", fake_send_notification)

    await review_booster_jobs.process_pending_review_requests()

    db.refresh(request)
    assert called["twilio"] == 0
    assert called["notify"] == 1
    assert request.status == RequestStatus.FAILED
    assert request.next_retry_at is None
    assert request.retry_count == review_booster_jobs.MAX_RETRY_ATTEMPTS
    assert "Daily limit reached" in (request.last_error or "")


async def test_process_pending_review_requests_notifies_admin_on_top_level_failure(
    db, monkeypatch
):
    admin = _admin_account(db)
    sessions = [_ExplodingSessionContext("review queue query failed"), _job_session(db)]

    monkeypatch.setattr(review_booster_jobs, "_session", lambda: sessions.pop(0))

    await review_booster_jobs.process_pending_review_requests()

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == admin.id,
            NotificationEvent.type == "review_booster_job_failed",
        )
        .one()
    )
    assert event.url == "/admin"
    assert "review queue query failed" in event.body.lower()

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"
