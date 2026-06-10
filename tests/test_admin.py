from io import BytesIO
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.core.security import create_access_token, get_password_hash
from app.models.analytics import Analytics
from app.models.account import Account, AccountRole
from app.models.billing import (
    BillingAuditAction,
    BillingAuditLog,
    Dispute as DisputeModel,
    DisputeReason,
    DisputeStatus,
    Payment,
    PaymentStatus,
)
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.oauth import OAuthEvent, OAuthEventType, OAuthProvider, OAuthStatus, OAuthToken
from app.models.post import Platform, Post, PostStatus
from app.models.credits import (
    CreditBalance,
    CreditPurchaseOrder,
    CreditPurchaseStatus,
    CreditTransaction,
    CreditTransactionType,
    UsageRecord,
)
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.review_booster import BoosterRequest, RequestChannel, RequestStatus, ReviewCampaign
from app.models.subscription import DunningStatus, PlanType, Subscription, SubscriptionStatus
from app.models.upload import UploadAsset
from app.services.credits import PLAN_CREDITS, SUBSCRIPTION_PLAN_TO_CREDITS_TIER


def _admin_headers(db):
    admin = Account(
        id=uuid4(),
        email="admin@example.com",
        password_hash=get_password_hash("adminpassword123"),
        role=AccountRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    token = create_access_token(subject=str(admin.id))
    return admin, {"Authorization": f"Bearer {token}"}


def test_admin_users_requires_admin_role(client, auth_headers):
    response = client.get("/admin/users", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_admin_users_list_and_detail_use_real_db(client, db, test_user):
    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.PRO,
        status=SubscriptionStatus.ACTIVE,
        locations_limit=1,
        posts_per_month=60,
        api_calls_per_day=20000,
    )
    db.add(subscription)
    db.commit()

    _admin, admin_headers = _admin_headers(db)

    response = client.get("/admin/users", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 2
    assert all(user["id"] != "user1" for user in payload["users"])

    detail = client.get(f"/admin/users/{test_user.id}", headers=admin_headers)
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["email"] == test_user.email
    assert detail_payload["plan"] == "pro"
    assert detail_payload["usage"]["sms"]["daily_limit"] > 0
    assert detail_payload["custom_limits"]["plan_type"] == "pro"


def test_admin_stats_and_plans_are_db_driven(client, db, test_user):
    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.PRO,
        status=SubscriptionStatus.ACTIVE,
        locations_limit=1,
        posts_per_month=60,
        api_calls_per_day=20000,
    )
    db.add(subscription)
    db.add(
        CreditBalance(
            account_id=test_user.id,
            balance=125,
            bonus_balance=0,
            total_credits_received=180,
            total_credits_used=55,
        )
    )
    now = datetime.now(UTC)
    db.add_all(
        [
            UsageRecord(
                account_id=test_user.id,
                usage_type="sms",
                date=now,
                daily_count=7,
                monthly_count=7,
            ),
            UsageRecord(
                account_id=test_user.id,
                usage_type="ai_content",
                date=now,
                daily_count=4,
                monthly_count=4,
            ),
            UsageRecord(
                account_id=test_user.id,
                usage_type="ai_image",
                date=now,
                daily_count=2,
                monthly_count=2,
            ),
        ]
    )
    db.commit()

    _admin, admin_headers = _admin_headers(db)

    stats = client.get("/admin/stats", headers=admin_headers)
    assert stats.status_code == 200
    stats_payload = stats.json()
    assert stats_payload["total_users"] >= 2
    assert stats_payload["active_users"] >= 2
    assert stats_payload["total_credits_issued"] == 180
    assert stats_payload["total_credits_used"] == 55
    assert stats_payload["total_sms_sent"] == 7
    assert stats_payload["total_ai_content"] == 4
    assert stats_payload["total_ai_images"] == 2
    assert stats_payload["revenue_this_month"] >= 149

    plans = client.get("/admin/plans", headers=admin_headers)
    assert plans.status_code == 200
    plans_payload = plans.json()
    assert "pro" in plans_payload["plans"]
    pro_credit_config = PLAN_CREDITS[SUBSCRIPTION_PLAN_TO_CREDITS_TIER[PlanType.PRO]]
    assert plans_payload["plans"]["pro"]["price_monthly"] == 149
    assert plans_payload["plans"]["pro"]["monthly_credits"] == pro_credit_config["monthly_credits"]
    assert plans_payload["plans"]["pro"]["sms_daily"] == pro_credit_config["sms_daily"]
    assert plans_payload["plans"]["pro"]["ai_content_daily"] == pro_credit_config["ai_content_daily"]


def test_admin_update_user_credits_persists_bonus_balance_and_transaction(client, db, test_user):
    admin, admin_headers = _admin_headers(db)

    response = client.post(
        f"/admin/users/{test_user.id}/credits",
        headers=admin_headers,
        json={"credits": 75, "reason": "Support goodwill credit"},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["success"] is True
    assert payload["amount"] == 75
    assert payload["is_bonus"] is True
    assert payload["bonus_balance"] == 75
    assert payload["user_email"] == test_user.email

    balance = db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
    assert balance is not None
    assert balance.bonus_balance == 75
    assert balance.total_credits_received == 75

    transaction = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.account_id == test_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .first()
    )
    assert transaction is not None
    assert transaction.type == CreditTransactionType.ADMIN_GRANT
    assert transaction.amount == 75
    assert transaction.description == "Support goodwill credit"
    assert transaction.admin_id == admin.id

    detail = client.get(f"/admin/users/{test_user.id}", headers=admin_headers)
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["credits"] == 75
    assert detail_payload["bonus_credits"] == 75

    users = client.get("/admin/users", headers=admin_headers)
    assert users.status_code == 200
    user_summary = next(item for item in users.json()["users"] if item["id"] == str(test_user.id))
    assert user_summary["credits"] == 75


def test_admin_suspend_user_disables_account_and_logs_operator_action(client, db, test_user):
    admin, admin_headers = _admin_headers(db)

    response = client.post(f"/admin/users/{test_user.id}/suspend", headers=admin_headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["account_id"] == str(test_user.id)
    assert payload["email"] == test_user.email
    assert payload["is_active"] is False
    assert payload["status"] == "suspended"
    assert payload["changed"] is True
    assert payload["operator_action"] == "account_suspended"

    db.refresh(test_user)
    assert test_user.is_active is False

    audit = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.account_id == test_user.id,
            BillingAuditLog.action == BillingAuditAction.SUBSCRIPTION_UPDATED,
            BillingAuditLog.entity_type == "account",
            BillingAuditLog.entity_id == str(test_user.id),
        )
        .order_by(BillingAuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.extra_data["operator_action"] == "account_suspended"
    assert audit.extra_data["operator_id"] == str(admin.id)
    assert audit.new_value["is_active"] is False
    assert audit.new_value["status"] == "suspended"


def test_admin_activate_user_reenables_account_and_logs_operator_action(client, db, test_user):
    test_user.is_active = False
    db.add(test_user)
    db.commit()

    admin, admin_headers = _admin_headers(db)

    response = client.post(f"/admin/users/{test_user.id}/activate", headers=admin_headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["account_id"] == str(test_user.id)
    assert payload["is_active"] is True
    assert payload["status"] == "active"
    assert payload["changed"] is True
    assert payload["operator_action"] == "account_reactivated"

    db.refresh(test_user)
    assert test_user.is_active is True

    audit = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.account_id == test_user.id,
            BillingAuditLog.action == BillingAuditAction.SUBSCRIPTION_UPDATED,
            BillingAuditLog.entity_type == "account",
            BillingAuditLog.entity_id == str(test_user.id),
        )
        .order_by(BillingAuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.extra_data["operator_action"] == "account_reactivated"
    assert audit.extra_data["operator_id"] == str(admin.id)
    assert audit.new_value["is_active"] is True
    assert audit.new_value["status"] == "active"


def test_admin_cannot_suspend_their_own_account(client, db):
    admin, admin_headers = _admin_headers(db)

    response = client.post(f"/admin/users/{admin.id}/suspend", headers=admin_headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Admins cannot suspend their own account."

    db.refresh(admin)
    assert admin.is_active is True


def test_admin_monthly_credit_distribution_processes_due_accounts_only(
    client, db, test_user, other_user
):
    now = datetime.now(UTC)
    db.add_all(
        [
            Subscription(
                account_id=test_user.id,
                plan_type=PlanType.STARTER,
                status=SubscriptionStatus.ACTIVE,
                locations_limit=1,
                posts_per_month=30,
                api_calls_per_day=5000,
            ),
            Subscription(
                account_id=other_user.id,
                plan_type=PlanType.PRO,
                status=SubscriptionStatus.ACTIVE,
                locations_limit=1,
                posts_per_month=60,
                api_calls_per_day=20000,
            ),
        ]
    )
    db.add_all(
        [
            CreditBalance(
                account_id=test_user.id,
                balance=12,
                bonus_balance=5,
                monthly_allocation=100,
                total_credits_received=100,
                last_allocation_date=now - timedelta(days=31),
                next_allocation_date=now - timedelta(days=1),
            ),
            CreditBalance(
                account_id=other_user.id,
                balance=42,
                bonus_balance=0,
                monthly_allocation=300,
                total_credits_received=300,
                last_allocation_date=now - timedelta(days=10),
                next_allocation_date=now + timedelta(days=20),
            ),
        ]
    )
    db.commit()

    admin, admin_headers = _admin_headers(db)

    response = client.post("/admin/monthly-credits", headers=admin_headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["considered"] == 2
    assert payload["processed"] == 1
    assert payload["skipped"] == 1
    assert payload["distributed_accounts"][0]["account_id"] == str(test_user.id)
    assert payload["distributed_accounts"][0]["credits_allocated"] == 100
    assert payload["distributed_accounts"][0]["reason"] == "distributed"
    assert payload["skipped_accounts"][0]["account_id"] == str(other_user.id)
    assert payload["skipped_accounts"][0]["reason"] == "not_due"

    due_balance = db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
    assert due_balance is not None
    assert due_balance.balance == 100
    assert due_balance.bonus_balance == 5
    assert due_balance.next_allocation_date is not None
    due_next_allocation = due_balance.next_allocation_date
    if due_next_allocation.tzinfo is None:
        due_next_allocation = due_next_allocation.replace(tzinfo=UTC)
    assert due_next_allocation > now

    skipped_balance = db.query(CreditBalance).filter(CreditBalance.account_id == other_user.id).first()
    assert skipped_balance is not None
    assert skipped_balance.balance == 42
    assert skipped_balance.next_allocation_date is not None
    skipped_next_allocation = skipped_balance.next_allocation_date
    if skipped_next_allocation.tzinfo is None:
        skipped_next_allocation = skipped_next_allocation.replace(tzinfo=UTC)
    assert skipped_next_allocation > now

    audit = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.account_id == test_user.id,
            BillingAuditLog.action == BillingAuditAction.SUBSCRIPTION_UPDATED,
            BillingAuditLog.entity_type == "subscription",
        )
        .order_by(BillingAuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.extra_data["operator_action"] == "monthly_credits_distributed"
    assert audit.extra_data["operator_id"] == str(admin.id)
    assert audit.extra_data["credits_allocated"] == 100


def test_admin_bulk_grant_and_transaction_history_use_real_credit_data(client, db, test_user, other_user):
    admin, admin_headers = _admin_headers(db)

    response = client.post(
        "/admin/credits/bulk-grant",
        headers=admin_headers,
        json={
            "user_ids": [str(test_user.id), str(other_user.id)],
            "amount": 40,
            "reason": "Migration support pack",
            "is_bonus": False,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["processed"] == 2
    assert all(item["is_bonus"] is False for item in payload["results"])

    history = client.get(
        "/admin/credits/transactions",
        headers=admin_headers,
        params={"user_id": str(test_user.id), "type": "admin_grant"},
    )
    assert history.status_code == 200, history.text
    history_payload = history.json()
    assert history_payload["total"] >= 1
    assert history_payload["transactions"][0]["user_email"] == test_user.email
    assert history_payload["transactions"][0]["type"] == "admin_grant"
    assert history_payload["transactions"][0]["amount"] == 40
    assert history_payload["transactions"][0]["admin_id"] == str(admin.id)


def test_admin_recovery_queue_uses_real_db_state(client, db, test_user, other_user):
    warning_subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.PRO,
        status=SubscriptionStatus.PAST_DUE,
        access_state="warning",
        dunning_status=DunningStatus.RETRYING,
        payment_retry_count=2,
        last_payment_error="card_declined",
        locations_limit=1,
        posts_per_month=60,
        api_calls_per_day=20000,
    )
    healthy_subscription = Subscription(
        account_id=other_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.ACTIVE,
        access_state="active",
        dunning_status=DunningStatus.NONE,
        locations_limit=1,
        posts_per_month=30,
        api_calls_per_day=500,
    )
    db.add_all([warning_subscription, healthy_subscription])
    db.flush()

    dispute = DisputeModel(
        account_id=test_user.id,
        stripe_dispute_id="dp_admin_queue",
        stripe_charge_id="ch_admin_queue",
        stripe_payment_intent_id="pi_admin_queue",
        amount=9900,
        currency="usd",
        status=DisputeStatus.NEEDS_RESPONSE,
        reason=DisputeReason.SUBSCRIPTION_CANCELED,
    )
    refund_order = CreditPurchaseOrder(
        account_id=test_user.id,
        stripe_session_id="cs_admin_queue_refund",
        package_id="credits_100",
        credits_amount=100,
        price_cents=899,
        status=CreditPurchaseStatus.REFUNDED,
        stripe_payment_intent_id="pi_admin_queue_refund",
        completed_at=datetime.now(UTC),
        refunded_at=datetime.now(UTC),
    )
    db.add_all([dispute, refund_order])
    db.commit()

    _admin, admin_headers = _admin_headers(db)

    response = client.get("/admin/recovery-queue", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()

    assert payload["dunning_total"] == 1
    assert payload["dispute_total"] == 1
    assert payload["urgent_dispute_total"] == 1
    assert payload["refunded_total"] == 1
    assert payload["action_required_total"] == 2

    dunning_account = payload["dunning_accounts"][0]
    assert dunning_account["email"] == test_user.email
    assert dunning_account["access_state"] == "warning"
    assert dunning_account["dunning_status"] == "retrying"
    assert dunning_account["payment_retry_count"] == 2
    assert "billing update" in dunning_account["action_plan"]["headline"].lower()
    assert test_user.email in dunning_account["action_plan"]["operator_note"]

    dispute_item = payload["disputes"][0]
    assert dispute_item["dispute_id"] == "dp_admin_queue"
    assert dispute_item["user_email"] == test_user.email
    assert dispute_item["status"] == "needs_response"
    assert dispute_item["amount"] == 99.0
    assert "stripe evidence response" in dispute_item["action_plan"]["headline"].lower()
    assert "payment dispute" in dispute_item["action_plan"]["customer_message"].lower()

    refund_item = payload["recent_refunds"][0]
    assert refund_item["payment_id"] == "pi_admin_queue_refund"
    assert refund_item["user_email"] == test_user.email
    assert refund_item["status"] == "refunded"
    assert "refund" in refund_item["action_plan"]["headline"].lower()
    assert "credits" in refund_item["action_plan"]["customer_message"].lower()
    assert {item["id"] for item in payload["runbook_items"]} == {
        "dunning-follow-up",
        "dispute-response",
        "refund-support-loop",
    }
    assert payload["recent_operator_actions"] == []


def test_admin_recovery_queue_surfaces_recent_operator_actions(client, db, test_user):
    _admin, admin_headers = _admin_headers(db)

    audit = BillingAuditLog(
        account_id=test_user.id,
        user_id=_admin.id,
        action=BillingAuditAction.REFUND_CREATED,
        entity_type="credit_purchase_order",
        entity_id="order_support_followup",
        description="Admin refund processed with manual Stripe follow-up required.",
        extra_data={
            "operator_action": "refund_processed",
            "operator_id": str(_admin.id),
        },
    )
    db.add(audit)
    db.commit()

    response = client.get("/admin/recovery-queue", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()

    recent = payload["recent_operator_actions"][0]
    assert recent["operator_action"] == "refund_processed"
    assert recent["account_email"] == test_user.email
    assert recent["entity_id"] == "order_support_followup"


def test_admin_create_dunning_recovery_link_returns_live_plan_and_logs_action(
    client, db, test_user, monkeypatch
):
    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.PRO,
        status=SubscriptionStatus.PAST_DUE,
        access_state="warning",
        dunning_status=DunningStatus.RETRYING,
        payment_retry_count=1,
        last_payment_error="insufficient_funds",
        locations_limit=1,
        posts_per_month=60,
        api_calls_per_day=20000,
    )
    db.add(subscription)
    db.commit()

    _admin, admin_headers = _admin_headers(db)
    monkeypatch.setattr("app.services.dunning_service.settings.app_url", "https://app.example.com", raising=False)
    monkeypatch.setattr("app.services.dunning_service.settings.stripe_secret_key", None, raising=False)

    response = client.post(f"/admin/dunning/{test_user.id}/recovery-link", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()

    assert payload["account_id"] == str(test_user.id)
    assert payload["email"] == test_user.email
    assert payload["portal_url"] == "https://app.example.com/dashboard/billing"
    assert payload["portal_available"] is False
    assert payload["portal_source"] == "billing_page"
    assert "Billing update link" in payload["action_plan"]["customer_message"]
    assert "Portal source: billing_page" in payload["action_plan"]["operator_note"]

    audit = (
        db.query(BillingAuditLog)
        .filter(BillingAuditLog.account_id == test_user.id)
        .order_by(BillingAuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.action == BillingAuditAction.SUBSCRIPTION_UPDATED
    assert audit.entity_type == "subscription"
    assert audit.extra_data["operator_action"] == "dunning_recovery_link_generated"
    assert audit.extra_data["portal_url"] == "https://app.example.com/dashboard/billing"


def test_admin_recovery_queue_surfaces_dunning_operator_actions(client, db, test_user):
    _admin, admin_headers = _admin_headers(db)

    audit = BillingAuditLog(
        account_id=test_user.id,
        user_id=_admin.id,
        action=BillingAuditAction.SUBSCRIPTION_UPDATED,
        entity_type="subscription",
        entity_id="sub_dunning_followup",
        description="Admin prepared a dunning recovery link for operator follow-up.",
        extra_data={
            "operator_action": "dunning_recovery_link_generated",
            "operator_id": str(_admin.id),
            "portal_source": "billing_page",
        },
    )
    db.add(audit)
    db.commit()

    response = client.get("/admin/recovery-queue", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()

    recent = payload["recent_operator_actions"][0]
    assert recent["operator_action"] == "dunning_recovery_link_generated"
    assert recent["account_email"] == test_user.email
    assert recent["action"] == "subscription_updated"
    assert recent["entity_id"] == "sub_dunning_followup"


def test_admin_recovery_queue_enriches_refund_action_plan_from_audit(client, db, test_user):
    now = datetime.now(UTC)
    order = CreditPurchaseOrder(
        account_id=test_user.id,
        stripe_session_id="cs_admin_refund_plan",
        package_id="credits_50",
        credits_amount=50,
        price_cents=499,
        status=CreditPurchaseStatus.REFUNDED,
        stripe_payment_intent_id="pi_admin_refund_plan",
        completed_at=now,
        refunded_at=now,
    )
    db.add(order)
    db.flush()

    _admin, admin_headers = _admin_headers(db)

    audit = BillingAuditLog(
        account_id=test_user.id,
        user_id=_admin.id,
        action=BillingAuditAction.REFUND_CREATED,
        entity_type="credit_purchase_order",
        entity_id=str(order.id),
        description="Admin refund processed with manual Stripe follow-up required.",
        extra_data={
            "operator_action": "refund_processed",
            "operator_id": str(_admin.id),
            "support_reason": "customer request",
            "stripe_error": "Stripe not configured; payment refund must be issued manually.",
        },
    )
    db.add(audit)
    db.commit()

    response = client.get("/admin/recovery-queue", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()

    refund_item = payload["recent_refunds"][0]
    assert "manual payment-side refund" in refund_item["action_plan"]["headline"].lower()
    assert "customer request" in refund_item["action_plan"]["operator_note"].lower()
    assert "tracking that manually" in refund_item["action_plan"]["customer_message"].lower()


def test_admin_recovery_queue_requires_admin(client, auth_headers):
    response = client.get("/admin/recovery-queue", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_admin_operations_feed_aggregates_cross_domain_events(client, db, test_user, test_location):
    _admin, admin_headers = _admin_headers(db)
    now = datetime.now(UTC)

    post = Post(
        location_id=test_location.id,
        platform=Platform.GBP,
        status=PostStatus.FAILED,
        title="Spring promotion",
        body="Promo body",
        error_message="publish failed",
    )
    db.add(post)
    db.flush()

    publish_job = PublishJob(
        post_id=post.id,
        platform="gbp",
        status=PublishJobStatus.FAILED,
        tries=3,
        max_tries=5,
        last_error="token expired",
        updated_at=now,
    )
    oauth_token = OAuthToken(
        account_id=test_user.id,
        location_id=test_location.id,
        provider=OAuthProvider.GOOGLE,
        access_token_ref="sm://google/access",
        refresh_token_ref="sm://google/refresh",
        expires_at=now,
        status=OAuthStatus.NEEDS_REAUTH,
        last_error="invalid_grant",
    )
    db.add_all([publish_job, oauth_token])
    db.flush()

    oauth_event = OAuthEvent(
        token_id=oauth_token.id,
        event_type=OAuthEventType.REFRESH_FAILED,
        error_message="invalid_grant",
    )
    notification_log = NotificationDeliveryLog(
        account_id=test_user.id,
        channel="sms",
        delivery_status="failed",
        failure_reason="Twilio unavailable",
        attempted_at=now,
    )
    worker_alert = NotificationEvent(
        account_id=test_user.id,
        type="analytics_collection_failed",
        title="Analytics collection failed",
        body="The scheduled analytics collection for Test Business could not finish.\n\nReason: GBP token expired",
        url=f"/dashboard/analytics?locationId={test_location.id}",
        read=False,
    )
    campaign = ReviewCampaign(
        location_id=test_location.id,
        name="Post-service follow-up",
        google_review_url="https://example.com/review",
    )
    stripe_webhook_alert = NotificationEvent(
        account_id=_admin.id,
        type="stripe_webhook_processing_failed",
        title="Stripe webhook processing failed",
        body="Stripe webhook invoice.payment_failed (evt_ops_feed) was recorded but could not be fully applied.\n\nReason: billing projector crashed",
        url="/admin",
        read=False,
    )
    stripe_refund_unmatched_alert = NotificationEvent(
        account_id=_admin.id,
        type="stripe_refund_unmatched",
        title="Stripe refund unmatched",
        body="A Stripe charge.refunded event did not match a local credit purchase or billing payment record.\n\nCharge ID: ch_ops_refund\nPayment intent ID: pi_ops_refund\nRefund IDs: re_ops_refund\nCredit refund reason: order_not_found",
        url="/admin",
        read=False,
    )
    stripe_credit_purchase_alert = NotificationEvent(
        account_id=_admin.id,
        type="stripe_credit_purchase_apply_failed",
        title="Stripe credit purchase apply failed",
        body="A Stripe checkout.session.completed event for a credit purchase could not be applied to the local credit balance.\n\nSession ID: cs_ops_credit\nPayment intent ID: pi_ops_credit\nAccount ID: acct_ops_credit\nPackage ID: credits_100\nCredits amount: 100\nReason: order_not_found",
        url="/admin",
        read=False,
    )
    stripe_credit_purchase_close_alert = NotificationEvent(
        account_id=_admin.id,
        type="stripe_credit_purchase_close_failed",
        title="Stripe credit purchase close failed",
        body="A Stripe checkout session could not expire the local credit purchase order.\n\nSession ID: cs_ops_credit_expired\nTarget status: expired\nAccount ID: acct_ops_credit\nPackage ID: credits_100\nCredits amount: 100\nOrder ID: Not recorded\nCurrent status: Not recorded\nReason: order_not_found",
        url="/admin",
        read=False,
    )
    content_generation_alert = NotificationEvent(
        account_id=_admin.id,
        type="content_generation_job_failed",
        title="Scheduled content generation worker failed",
        body="The scheduled content generation worker could not complete its run.\n\nReason: approval workflow bootstrap failed",
        url="/admin",
        read=False,
    )
    billing_email_alert = NotificationEvent(
        account_id=_admin.id,
        type="billing_lifecycle_email_failed",
        title="Billing recovery email failed",
        body="The billing recovery email could not be sent.\n\nAccount: owner@example.com\nSubscription ID: sub_ops_feed\nPlan: STARTER\nDunning status: retrying\nAccess state: warning\nReason: smtp offline",
        url="/admin",
        read=False,
    )
    billing_receipt_alert = NotificationEvent(
        account_id=_admin.id,
        type="billing_receipt_email_failed",
        title="Billing receipt email failed",
        body="The payment receipt email could not be sent.\n\nAccount: owner@example.com\nSubscription ID: sub_ops_receipt\nInvoice ID: in_ops_receipt\nReason: receipt smtp offline",
        url="/admin",
        read=False,
    )
    billing_trial_ending_alert = NotificationEvent(
        account_id=_admin.id,
        type="billing_trial_ending_email_failed",
        title="Billing trial ending email failed",
        body="The trial ending reminder email could not be sent.\n\nAccount: owner@example.com\nSubscription ID: sub_ops_trial\nStripe subscription ID: sub_ops_trial_stripe\nReason: trial smtp offline",
        url="/admin",
        read=False,
    )
    oauth_reauth_notification_alert = NotificationEvent(
        account_id=_admin.id,
        type="oauth_reauth_notification_failed",
        title="OAuth reauth notification failed",
        body="The account could not be notified that the Google connection needs reconnect.\n\nAccount: owner@example.com\nToken ID: tok_ops_feed\nLocation ID: loc_ops_feed\nReason: notification provider offline\nLast token error: reconnect required",
        url="/admin",
        read=False,
    )
    usage_warning_alert = NotificationEvent(
        account_id=test_user.id,
        type="usage_warning_ai_content_80",
        title="Ai Content usage at 80%",
        body="You've used 4 of 5 monthly ai content generations (80.0%). Review usage or upgrade before work is blocked.",
        url="/dashboard/usage",
        read=False,
    )
    snapshot_unavailable_alert = NotificationEvent(
        account_id=test_user.id,
        type="daily_snapshot_unavailable",
        title="Daily snapshot unavailable",
        body="The daily metric snapshot for Test Business could not be created because Google Business Profile metrics are unavailable and there is no previous snapshot to carry forward yet.",
        url=f"/dashboard/analytics?locationId={test_location.id}",
        read=False,
    )
    payment_failed_alert = NotificationEvent(
        account_id=test_user.id,
        type="billing_payment_failed",
        title="Payment failed",
        body="A billing payment failed and the account entered the retrying dunning state.",
        url="/dashboard/billing",
        read=False,
    )
    missed_call_alert = NotificationEvent(
        account_id=test_user.id,
        type="missed_call_text_back_failed",
        title="Missed call text-back failed",
        body="A missed-call text-back could not be delivered because Twilio was unavailable.",
        url=f"/dashboard/calls?locationId={test_location.id}",
        read=False,
    )
    negative_review_alert = NotificationEvent(
        account_id=test_user.id,
        type="review_booster_negative_review",
        title="Negative review needs follow-up",
        body="A customer left negative private feedback and needs a follow-up response.",
        url=f"/dashboard/reviews?locationId={test_location.id}",
        read=False,
    )
    db.add_all(
        [
            oauth_event,
            notification_log,
            worker_alert,
            stripe_webhook_alert,
            stripe_refund_unmatched_alert,
            stripe_credit_purchase_alert,
            stripe_credit_purchase_close_alert,
            content_generation_alert,
            billing_email_alert,
            billing_receipt_alert,
            billing_trial_ending_alert,
            oauth_reauth_notification_alert,
            usage_warning_alert,
            snapshot_unavailable_alert,
            payment_failed_alert,
            missed_call_alert,
            negative_review_alert,
            campaign,
        ]
    )
    db.flush()

    booster_request = BoosterRequest(
        campaign_id=campaign.id,
        location_id=test_location.id,
        customer_name="Jamie",
        customer_phone="5551234567",
        consent_given=True,
        consent_timestamp=now,
        consent_method="sms",
        channel=RequestChannel.SMS,
        status=RequestStatus.FAILED,
        message_content="Thanks for visiting. Please leave a review.",
        google_link_included=True,
        last_error="invalid phone",
        last_attempt_at=now,
    )
    db.add(booster_request)
    db.commit()

    response = client.get("/admin/operations-feed?limit=30", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()

    domains = {item["domain"] for item in payload["items"]}
    assert {"publish", "oauth", "notifications", "review_booster", "worker_ops"}.issubset(domains)
    assert payload["domain_totals"]["publish"] >= 1
    assert payload["domain_totals"]["oauth"] >= 1
    assert payload["domain_totals"]["notifications"] >= 1
    assert payload["domain_totals"]["review_booster"] >= 1
    assert payload["domain_totals"]["worker_ops"] >= 1
    assert payload["actionable_total"] >= 5

    publish_item = next(item for item in payload["items"] if item["domain"] == "publish")
    assert publish_item["account_email"] == test_user.email
    assert publish_item["location_name"] == test_location.name
    assert publish_item["action_href"] == f"/dashboard/content/{post.id}"

    oauth_item = next(item for item in payload["items"] if item["domain"] == "oauth")
    assert oauth_item["status"] == "needs_reauth"
    assert oauth_item["actionable"] is True

    notification_item = next(item for item in payload["items"] if item["domain"] == "notifications")
    assert notification_item["summary"].lower().find("twilio unavailable") != -1

    booster_item = next(item for item in payload["items"] if item["domain"] == "review_booster")
    assert booster_item["summary"].lower().find("invalid phone") != -1

    worker_item = next(item for item in payload["items"] if item["domain"] == "worker_ops")
    worker_titles = {item["title"] for item in payload["items"] if item["domain"] == "worker_ops"}
    assert "Analytics collection failed" in worker_titles
    assert "Billing recovery email failed" in worker_titles
    assert "Billing receipt email failed" in worker_titles
    assert "Billing trial ending email failed" in worker_titles
    assert "OAuth reauth notification failed" in worker_titles
    assert "Ai Content usage at 80%" in worker_titles
    assert "Daily snapshot unavailable" in worker_titles
    assert "Payment failed" in worker_titles
    assert "Missed call text-back failed" in worker_titles
    assert "Negative review needs follow-up" in worker_titles
    assert "Scheduled content generation worker failed" in worker_titles
    assert "Stripe credit purchase apply failed" in worker_titles
    assert "Stripe credit purchase close failed" in worker_titles
    assert "Stripe refund unmatched" in worker_titles
    assert "Stripe webhook processing failed" in worker_titles

    analytics_worker_item = next(
        item
        for item in payload["items"]
        if item["domain"] == "worker_ops" and item["title"] == "Analytics collection failed"
    )
    stripe_worker_item = next(
        item
        for item in payload["items"]
        if item["domain"] == "worker_ops" and item["title"] == "Stripe webhook processing failed"
    )
    missed_call_item = next(
        item
        for item in payload["items"]
        if item["domain"] == "worker_ops" and item["title"] == "Missed call text-back failed"
    )
    usage_warning_item = next(
        item
        for item in payload["items"]
        if item["domain"] == "worker_ops" and item["title"] == "Ai Content usage at 80%"
    )
    snapshot_unavailable_item = next(
        item
        for item in payload["items"]
        if item["domain"] == "worker_ops" and item["title"] == "Daily snapshot unavailable"
    )
    assert analytics_worker_item["action_href"] == f"/dashboard/analytics?locationId={test_location.id}"
    assert stripe_worker_item["action_href"] == "/admin"
    assert missed_call_item["action_href"] == f"/dashboard/calls?locationId={test_location.id}"
    assert usage_warning_item["action_href"] == "/dashboard/usage"
    assert snapshot_unavailable_item["action_href"] == f"/dashboard/analytics?locationId={test_location.id}"


def test_admin_operations_feed_requires_admin(client, auth_headers):
    response = client.get("/admin/operations-feed", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_admin_upload_migration_audit_reports_legacy_local_uploads(client, db, test_user, test_location):
    _admin, admin_headers = _admin_headers(db)
    now = datetime.now(UTC)

    upload_asset = UploadAsset(
        account_id=test_user.id,
        file_type="image",
        filename="legacy-hero.png",
        original_filename="legacy-hero.png",
        mime_type="image/png",
        size_bytes=2048,
        url="http://localhost:8000/uploads/images/legacy-hero.png",
        storage_key="uploads/images/legacy-hero.png",
        created_at=now - timedelta(hours=1),
    )
    post = Post(
        location_id=test_location.id,
        platform=Platform.GBP,
        status=PostStatus.DRAFT,
        title="Legacy image draft",
        body="Body",
        image_url="http://localhost:8000/uploads/images/post-image.png",
        ai_image_url="/uploads/images/generated-image.png",
        created_at=now - timedelta(hours=2),
    )
    billing_audit = BillingAuditLog(
        account_id=test_user.id,
        action=BillingAuditAction.DISPUTE_UPDATED,
        entity_type="dispute",
        entity_id="dp_upload_audit",
        description="Stored attachment references for dispute evidence.",
        extra_data={
            "attachment_urls": [
                "http://localhost:8000/uploads/documents/evidence.pdf",
                "https://storage.googleapis.com/test-bucket/uploads/documents/cloud-evidence.pdf",
            ]
        },
        created_at=now - timedelta(hours=3),
    )
    db.add_all([upload_asset, post, billing_audit])
    db.commit()

    response = client.get("/admin/upload-migration-audit?sample_limit=10", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()

    assert payload["upload_asset_total"] >= 1
    assert payload["upload_asset_local_total"] >= 1
    assert payload["legacy_post_image_total"] >= 1
    assert payload["legacy_post_ai_image_total"] >= 1
    assert payload["legacy_billing_attachment_total"] >= 1
    assert payload["affected_account_total"] >= 1
    assert payload["actionable_total"] >= 4
    assert payload["batch_summaries"][0]["recommended_action"] == "replace_billing_attachment_reference"
    assert payload["batch_summaries"][0]["priority"] == "high"
    assert payload["runbook_steps"][0].lower().find("csv manifest") != -1

    fields = {(item["source_type"], item["field_name"]) for item in payload["items"]}
    assert ("upload_asset", "url") in fields
    assert ("post", "image_url") in fields
    assert ("post", "ai_image_url") in fields
    assert ("billing_attachment", "attachment_urls") in fields

    billing_item = next(item for item in payload["items"] if item["source_type"] == "billing_attachment")
    assert billing_item["account_email"] == test_user.email
    assert billing_item["url"].startswith("http://localhost:8000/uploads/documents/")
    assert billing_item["recommended_action"] == "replace_billing_attachment_reference"


def test_admin_upload_migration_audit_export_returns_csv(client, db, test_user):
    _admin, admin_headers = _admin_headers(db)

    asset = UploadAsset(
        account_id=test_user.id,
        file_type="document",
        filename="legacy-proof.pdf",
        original_filename="legacy-proof.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        url="http://localhost:8000/uploads/documents/legacy-proof.pdf",
        storage_key="uploads/documents/legacy-proof.pdf",
    )
    db.add(asset)
    db.commit()

    response = client.get("/admin/upload-migration-audit/export?limit=10", headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=\"upload-migration-audit.csv\"" == response.headers["content-disposition"]
    body = response.text
    assert "recommended_action" in body
    assert "reupload_asset_to_cloud" in body
    assert "http://localhost:8000/uploads/documents/legacy-proof.pdf" in body


def test_admin_upload_migration_audit_requires_admin(client, auth_headers):
    response = client.get("/admin/upload-migration-audit", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_admin_upload_migration_batch_preview_returns_dry_run_batch(client, db, test_user, test_location):
    _admin, admin_headers = _admin_headers(db)
    now = datetime.now(UTC)
    upload_dir = Path("uploads/images")
    upload_dir.mkdir(parents=True, exist_ok=True)
    created_files = [
        upload_dir / "legacy-one.png",
        upload_dir / "legacy-two.png",
        upload_dir / "legacy-two-ai.png",
    ]
    for file_path, content in zip(
        created_files,
        [b"legacy-one", b"legacy-two", b"legacy-two-ai"],
    ):
        file_path.write_bytes(content)

    try:
        first_post = Post(
            location_id=test_location.id,
            platform=Platform.GBP,
            title="Legacy image one",
            body="Body",
            image_url="http://localhost:8000/uploads/images/legacy-one.png",
            status=PostStatus.DRAFT,
            created_at=now - timedelta(hours=2),
        )
        second_post = Post(
            location_id=test_location.id,
            platform=Platform.GBP,
            title="Legacy image two",
            body="Body",
            image_url="http://localhost:8000/uploads/images/legacy-two.png",
            ai_image_url="http://localhost:8000/uploads/images/legacy-two-ai.png",
            status=PostStatus.DRAFT,
            created_at=now - timedelta(hours=1),
        )
        db.add_all([first_post, second_post])
        db.commit()

        response = client.get(
            "/admin/upload-migration-batch-preview?source_type=post&limit=1&offset=0",
            headers=admin_headers,
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["source_type_filter"] == "post"
        assert payload["batch_offset"] == 0
        assert payload["batch_limit"] == 1
        assert payload["matching_total"] >= 3
        assert payload["candidate_total"] == 1
        assert payload["planned_total"] == 1
        assert payload["has_more"] is True
        assert payload["next_offset"] == 1
        assert payload["source_totals"]["post"] >= 3
        assert payload["cleanup_candidate_total"] == 1
        assert "--source-type post" in payload["apply_command"]
        assert "--offset 0" in payload["apply_command"]
        assert "--offset 1" in payload["next_apply_command"]

        preview_item = payload["items"][0]
        assert preview_item["source_type"] == "post"
        assert preview_item["field_name"] in {"image_url", "ai_image_url"}
        assert preview_item["status"] == "planned"
        assert preview_item["local_path"].lower().find("uploads") != -1

        cleanup_item = payload["cleanup_candidates"][0]
        assert cleanup_item["relative_path"] in {"images/legacy-one.png", "images/legacy-two.png", "images/legacy-two-ai.png"}
        assert cleanup_item["reference_count"] == 1
        assert cleanup_item["reason"].lower().find("after this batch applies") != -1
    finally:
        for file_path in created_files:
            if file_path.exists():
                file_path.unlink()


def test_admin_upload_migration_batch_preview_requires_admin(client, auth_headers):
    response = client.get("/admin/upload-migration-batch-preview", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_admin_conversions_returns_real_db_metrics(client, db, test_user, other_user, test_location):
    _admin, admin_headers = _admin_headers(db)
    now = datetime.now(UTC)
    start_date = (now - timedelta(days=29)).date()
    end_date = now.date()
    previous_date = (now - timedelta(days=45)).date()

    test_user.created_at = now - timedelta(days=20)
    other_user.created_at = now - timedelta(days=10)

    prior_account = Account(
        id=uuid4(),
        email="prior-period@example.com",
        password_hash=get_password_hash("priorpassword123"),
        role=AccountRole.OWNER,
        is_active=True,
        created_at=now - timedelta(days=40),
    )
    db.add(prior_account)
    db.flush()

    db.add_all(
        [
            Analytics(
                location_id=test_location.id,
                platform="website",
                date=start_date,
                unique_visitors=300,
                page_views=900,
            ),
            Analytics(
                location_id=test_location.id,
                platform="website",
                date=end_date,
                unique_visitors=200,
                page_views=600,
            ),
            Analytics(
                location_id=test_location.id,
                platform="website",
                date=previous_date,
                unique_visitors=250,
                page_views=700,
            ),
        ]
    )

    db.add_all(
        [
            Subscription(
                account_id=test_user.id,
                plan_type=PlanType.PRO,
                status=SubscriptionStatus.ACTIVE,
                trial_start=now - timedelta(days=18),
                trial_end=now - timedelta(days=4),
                locations_limit=1,
                posts_per_month=60,
                api_calls_per_day=20000,
            ),
            Subscription(
                account_id=other_user.id,
                plan_type=PlanType.STARTER,
                status=SubscriptionStatus.PAST_DUE,
                dunning_status=DunningStatus.RETRYING,
                access_state="warning",
                trial_start=None,
                locations_limit=1,
                posts_per_month=30,
                api_calls_per_day=5000,
            ),
            Subscription(
                account_id=prior_account.id,
                plan_type=PlanType.STARTER,
                status=SubscriptionStatus.CANCELED,
                trial_start=now - timedelta(days=39),
                trial_end=now - timedelta(days=32),
                canceled_at=now - timedelta(days=6),
                locations_limit=1,
                posts_per_month=30,
                api_calls_per_day=5000,
            ),
            Payment(
                account_id=test_user.id,
                stripe_payment_intent_id="pi_admin_conversion_current",
                stripe_invoice_id="in_admin_conversion_current",
                amount=14900,
                status=PaymentStatus.SUCCEEDED,
                created_at=now - timedelta(days=3),
            ),
            Payment(
                account_id=prior_account.id,
                stripe_payment_intent_id="pi_admin_conversion_previous",
                stripe_invoice_id="in_admin_conversion_previous",
                amount=9900,
                status=PaymentStatus.SUCCEEDED,
                created_at=now - timedelta(days=40),
            ),
        ]
    )
    db.commit()

    response = client.get(
        f"/admin/conversions?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}",
        headers=admin_headers,
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["start_date"] == start_date.isoformat()
    assert payload["end_date"] == end_date.isoformat()
    assert payload["metrics"]["visitors"] == 500
    assert payload["metrics"]["signups"] == 2
    assert payload["metrics"]["trials"] == 1
    assert payload["metrics"]["paid"] == 1
    assert payload["metrics"]["revenue_collected"] == 149.0
    assert payload["metrics"]["current_mrr"] == 248.0
    assert payload["metrics"]["payment_recovery_accounts"] == 1
    assert payload["metrics"]["canceled_subscriptions"] == 1
    assert payload["metrics"]["top_drop_off_point"] == "Website visitors -> New signups"

    assert payload["metrics"]["changes"]["visitors"] == 100.0
    assert payload["metrics"]["changes"]["signups"] == 100.0
    assert payload["metrics"]["changes"]["paid"] == 0.0
    assert payload["metrics"]["changes"]["revenue_collected"] == 50.5

    assert [step["name"] for step in payload["funnel"]] == [
        "Website visitors",
        "New signups",
        "Trial starts",
        "Paid accounts",
    ]
    assert payload["drop_off_reasons"][0]["reason"].lower().find("website visitors") != -1
    assert payload["insights"]
    assert any("invoice-backed payments" in note for note in payload["notes"])


def test_admin_conversions_requires_admin(client, auth_headers):
    response = client.get("/admin/conversions", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_admin_plan_change_updates_local_subscription_snapshot(client, db, test_user):
    _admin, admin_headers = _admin_headers(db)

    response = client.post(
        f"/admin/users/{test_user.id}/plan",
        headers=admin_headers,
        json={"plan": "starter"},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["account_id"] == str(test_user.id)
    assert payload["previous_plan"] == "free"
    assert payload["current_plan"] == "starter"
    assert payload["stripe_synced"] is False

    subscription = db.query(Subscription).filter(Subscription.account_id == test_user.id).first()
    assert subscription is not None
    assert subscription.plan_type == PlanType.STARTER
    assert subscription.locations_limit == 1
    assert subscription.posts_per_month == 30
    assert subscription.api_calls_per_day == 5000

    audit = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.account_id == test_user.id,
            BillingAuditLog.action == BillingAuditAction.PLAN_CHANGED,
            BillingAuditLog.entity_type == "subscription",
        )
        .order_by(BillingAuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.extra_data["operator_action"] == "admin_plan_changed"
    assert audit.extra_data["stripe_synced"] is False
    assert audit.new_value["plan_type"] == "starter"


def test_admin_plan_change_requires_stripe_config_for_stripe_backed_accounts(client, db, test_user, monkeypatch):
    db.add(
        Subscription(
            account_id=test_user.id,
            plan_type=PlanType.STARTER,
            status=SubscriptionStatus.ACTIVE,
            stripe_customer_id="cus_admin_plan",
            stripe_subscription_id="sub_admin_plan",
            stripe_price_id="price_starter",
            locations_limit=1,
            posts_per_month=30,
            api_calls_per_day=5000,
        )
    )
    db.commit()

    monkeypatch.setattr("app.routers.admin.settings.stripe_secret_key", None, raising=False)
    _admin, admin_headers = _admin_headers(db)

    response = client.post(
        f"/admin/users/{test_user.id}/plan",
        headers=admin_headers,
        json={"plan": "premium"},
    )
    assert response.status_code == 503
    assert "STRIPE_SECRET_KEY" in response.json()["detail"]


def test_admin_update_user_limits_persists_overrides_and_updates_usage_summary(
    client,
    db,
    test_user,
    auth_headers,
):
    db.add(
        Subscription(
            account_id=test_user.id,
            plan_type=PlanType.STARTER,
            status=SubscriptionStatus.ACTIVE,
            locations_limit=1,
            posts_per_month=30,
            api_calls_per_day=5000,
        )
    )
    db.commit()

    admin, admin_headers = _admin_headers(db)

    response = client.post(
        f"/admin/users/{test_user.id}/limits",
        headers=admin_headers,
        json={
            "sms_daily": 12,
            "sms_monthly": 220,
            "api_calls_daily": 7777,
        },
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["account_id"] == str(test_user.id)
    assert payload["email"] == test_user.email
    assert payload["plan"] == "starter"
    assert payload["usage_overrides"]["sms_daily"] == 12
    assert payload["usage_overrides"]["sms_monthly"] == 220
    assert payload["usage_overrides"]["api_calls_daily"] == 7777
    assert payload["effective_usage_limits"]["sms_daily"] == 12
    assert payload["effective_usage_limits"]["sms_monthly"] == 220
    assert payload["effective_usage_limits"]["api_calls_daily"] == 7777

    db.refresh(test_user)
    assert test_user.settings["usage_limit_overrides"]["sms_daily"] == 12
    assert test_user.settings["usage_limit_overrides"]["api_calls_daily"] == 7777

    detail = client.get(f"/admin/users/{test_user.id}", headers=admin_headers)
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["custom_limits"]["usage_overrides"]["sms_daily"] == 12
    assert detail_payload["custom_limits"]["effective_usage_limits"]["api_calls_daily"] == 7777

    summary = client.get("/usage/summary", headers=auth_headers)
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["usage"]["sms"]["daily_limit"] == 12
    assert summary_payload["usage"]["sms"]["monthly_limit"] == 220
    assert summary_payload["usage"]["api_calls"]["daily_limit"] == 7777

    audit = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.account_id == test_user.id,
            BillingAuditLog.action == BillingAuditAction.SUBSCRIPTION_UPDATED,
            BillingAuditLog.entity_type == "account",
            BillingAuditLog.entity_id == str(test_user.id),
        )
        .order_by(BillingAuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.extra_data["operator_action"] == "usage_limit_overrides_updated"
    assert audit.new_value["usage_overrides"]["sms_daily"] == 12
    assert audit.new_value["effective_usage_limits"]["api_calls_daily"] == 7777
    assert audit.user_id == admin.id


def test_admin_update_user_limits_can_clear_existing_override(client, db, test_user, auth_headers):
    db.add(
        Subscription(
            account_id=test_user.id,
            plan_type=PlanType.FREE,
            status=SubscriptionStatus.ACTIVE,
            locations_limit=1,
            posts_per_month=10,
            api_calls_per_day=1000,
        )
    )
    test_user.settings = {
        "usage_limit_overrides": {
            "sms_daily": 15,
            "sms_monthly": 75,
        }
    }
    db.add(test_user)
    db.commit()

    _admin, admin_headers = _admin_headers(db)
    response = client.post(
        f"/admin/users/{test_user.id}/limits",
        headers=admin_headers,
        json={"sms_daily": None, "sms_monthly": None},
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["usage_overrides"] == {}
    assert payload["effective_usage_limits"]["sms_daily"] == 0
    assert payload["effective_usage_limits"]["sms_monthly"] == 0

    db.refresh(test_user)
    assert (test_user.settings or {}).get("usage_limit_overrides") in (None, {})

    summary = client.get("/usage/summary", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["usage"]["sms"]["daily_limit"] == 0
    assert summary.json()["usage"]["sms"]["monthly_limit"] == 0


def test_admin_mutations_keep_honest_error_contracts(client, db, test_user):
    _admin, admin_headers = _admin_headers(db)

    limits = client.post(
        f"/admin/users/{test_user.id}/limits",
        headers=admin_headers,
        json={"sms_daily": 60},
    )
    assert limits.status_code == 400
    assert "daily limit cannot exceed the monthly limit" in limits.json()["detail"]

    # POST /admin/refunds is implemented; unknown payment_id yields 404
    refund = client.post(
        "/admin/refunds",
        headers=admin_headers,
        json={"payment_id": "pi_nonexistent", "reason": "refund"},
    )
    assert refund.status_code == 404


def test_admin_get_refunds_returns_real_db_data(client, db, test_user):
    """GET /admin/refunds returns real CreditPurchaseOrder rows (REFUNDED status)."""
    _admin, admin_headers = _admin_headers(db)

    # No refunded orders yet – should return empty list
    resp = client.get("/admin/refunds", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["refunds"] == []

    # Create a REFUNDED order
    now = datetime.now(UTC)
    order = CreditPurchaseOrder(
        account_id=test_user.id,
        stripe_session_id="cs_admin_test_refund",
        package_id="credits_100",
        credits_amount=100,
        price_cents=899,
        status=CreditPurchaseStatus.REFUNDED,
        stripe_payment_intent_id="pi_admin_test_refund",
        completed_at=now,
        refunded_at=now,
    )
    db.add(order)
    db.commit()

    resp = client.get("/admin/refunds", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["refunds"]) == 1
    r = data["refunds"][0]
    assert r["payment_id"] == "pi_admin_test_refund"
    assert r["amount"] == 8.99
    assert r["status"] == "refunded"
    assert r["user_email"] == test_user.email


def test_admin_get_refunds_status_filter(client, db, test_user):
    """GET /admin/refunds?status_filter=completed returns COMPLETED orders."""
    _admin, admin_headers = _admin_headers(db)

    completed_order = CreditPurchaseOrder(
        account_id=test_user.id,
        stripe_session_id="cs_admin_completed",
        package_id="credits_50",
        credits_amount=50,
        price_cents=499,
        status=CreditPurchaseStatus.COMPLETED,
        stripe_payment_intent_id="pi_admin_completed",
        completed_at=datetime.now(UTC),
    )
    db.add(completed_order)
    db.commit()

    # Default (no filter) → only REFUNDED → should not include the completed order
    resp_default = client.get("/admin/refunds", headers=admin_headers)
    assert resp_default.status_code == 200
    ids_default = [r["payment_id"] for r in resp_default.json()["refunds"]]
    assert "pi_admin_completed" not in ids_default

    # Filter by completed → should include it
    resp_completed = client.get("/admin/refunds?status_filter=completed", headers=admin_headers)
    assert resp_completed.status_code == 200
    ids_completed = [r["payment_id"] for r in resp_completed.json()["refunds"]]
    assert "pi_admin_completed" in ids_completed

    # Invalid status → 400
    resp_bad = client.get("/admin/refunds?status_filter=invalid_status", headers=admin_headers)
    assert resp_bad.status_code == 400


def test_admin_process_refund_claws_back_credits(client, db, test_user):
    """POST /admin/refunds claws back credits for a COMPLETED order."""
    _admin, admin_headers = _admin_headers(db)

    now = datetime.now(UTC)
    order = CreditPurchaseOrder(
        account_id=test_user.id,
        stripe_session_id="cs_admin_proc_refund",
        package_id="credits_100",
        credits_amount=100,
        price_cents=899,
        status=CreditPurchaseStatus.COMPLETED,
        stripe_payment_intent_id="pi_admin_proc_refund",
        completed_at=now,
    )
    db.add(order)
    balance = CreditBalance(
        account_id=test_user.id,
        balance=100,
        bonus_balance=0,
        total_credits_received=100,
        total_credits_purchased=100,
    )
    db.add(balance)
    db.commit()

    resp = client.post(
        "/admin/refunds",
        headers=admin_headers,
        json={"payment_id": "pi_admin_proc_refund", "reason": "customer request"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "refunded"
    assert data["credits_deducted"] == 100
    # Stripe not configured in test env – stripe_error should be set
    assert data["stripe_refund_id"] is None
    assert data["stripe_error"] is not None

    db.refresh(order)
    db.refresh(balance)
    assert order.status == CreditPurchaseStatus.REFUNDED
    assert order.refunded_at is not None
    assert balance.balance == 0

    audit = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.account_id == test_user.id,
            BillingAuditLog.action == BillingAuditAction.REFUND_CREATED,
            BillingAuditLog.entity_type == "credit_purchase_order",
            BillingAuditLog.entity_id == str(order.id),
        )
        .order_by(BillingAuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.extra_data["operator_action"] == "refund_processed"
    assert audit.extra_data["support_reason"] == "customer request"


def test_admin_process_refund_already_refunded_returns_409(client, db, test_user):
    """POST /admin/refunds on an already-refunded order returns 409."""
    _admin, admin_headers = _admin_headers(db)

    now = datetime.now(UTC)
    order = CreditPurchaseOrder(
        account_id=test_user.id,
        stripe_session_id="cs_admin_already_refunded",
        package_id="credits_50",
        credits_amount=50,
        price_cents=499,
        status=CreditPurchaseStatus.REFUNDED,
        stripe_payment_intent_id="pi_admin_already_refunded",
        completed_at=now,
        refunded_at=now,
    )
    db.add(order)
    db.commit()

    resp = client.post(
        "/admin/refunds",
        headers=admin_headers,
        json={"payment_id": "pi_admin_already_refunded", "reason": "duplicate"},
    )
    assert resp.status_code == 409


def test_admin_credit_orders_endpoint(client, db, test_user):
    """GET /admin/credit-orders returns all orders across all users."""
    _admin, admin_headers = _admin_headers(db)

    # Empty initially
    resp = client.get("/admin/credit-orders", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json()["orders"], list)

    # Create one pending order
    order = CreditPurchaseOrder(
        account_id=test_user.id,
        stripe_session_id="cs_admin_list_test",
        package_id="credits_250",
        credits_amount=250,
        price_cents=1999,
        status=CreditPurchaseStatus.PENDING,
    )
    db.add(order)
    db.commit()

    resp2 = client.get("/admin/credit-orders", headers=admin_headers)
    assert resp2.status_code == 200
    orders = resp2.json()["orders"]
    assert any(o["stripe_session_id"] == "cs_admin_list_test" for o in orders)
    found = next(o for o in orders if o["stripe_session_id"] == "cs_admin_list_test")
    assert found["status"] == "pending"
    assert found["credits_amount"] == 250


# ---------------------------------------------------------------------------
# Dispute respond / accept
# ---------------------------------------------------------------------------

def _fake_dispute(
    dispute_id: str = "dp_test123",
    dispute_status: str = "needs_response",
    payment_intent: str | None = None,
) -> MagicMock:
    d = MagicMock()
    d.id = dispute_id
    d.status = dispute_status
    d.payment_intent = payment_intent
    return d


def test_dispute_respond_no_stripe_key(client, db):
    """Without Stripe configured the endpoint returns 503."""
    _admin, admin_headers = _admin_headers(db)
    resp = client.post(
        "/admin/disputes/dp_test/respond",
        headers=admin_headers,
        json={"evidence": "customer signed up voluntarily"},
    )
    assert resp.status_code == 503
    assert "Stripe" in resp.json()["detail"]


def test_dispute_accept_no_stripe_key(client, db):
    """Without Stripe configured the endpoint returns 503."""
    _admin, admin_headers = _admin_headers(db)
    resp = client.post("/admin/disputes/dp_test/accept", headers=admin_headers)
    assert resp.status_code == 503
    assert "Stripe" in resp.json()["detail"]


def test_dispute_respond_wrong_state(client, db):
    """Submitting evidence to an under_review dispute returns 422."""
    _admin, admin_headers = _admin_headers(db)
    d = _fake_dispute(dispute_status="under_review")
    with patch("app.core.config.settings") as mock_settings, \
         patch("stripe.Dispute") as mock_sd:
        mock_settings.stripe_secret_key = "sk_test_fake"
        mock_sd.retrieve.return_value = d
        resp = client.post(
            "/admin/disputes/dp_test123/respond",
            headers=admin_headers,
            json={"evidence": "some evidence"},
        )
    assert resp.status_code == 422
    assert "under_review" in resp.json()["detail"]


def test_dispute_respond_success(client, db):
    """Evidence is submitted to Stripe and the updated status is returned."""
    _admin, admin_headers = _admin_headers(db)
    local_dispute = DisputeModel(
        account_id=_admin.id,
        stripe_dispute_id="dp_test123",
        stripe_charge_id="ch_test123",
        stripe_payment_intent_id="pi_test123",
        amount=14900,
        currency="usd",
        status=DisputeStatus.NEEDS_RESPONSE,
        reason=DisputeReason.GENERAL,
    )
    db.add(local_dispute)
    db.commit()

    d_before = _fake_dispute(dispute_status="needs_response", payment_intent="pi_test123")
    d_after = _fake_dispute(dispute_status="under_review", payment_intent="pi_test123")
    with patch("app.core.config.settings") as mock_settings, \
         patch("stripe.Dispute") as mock_sd:
        mock_settings.stripe_secret_key = "sk_test_fake"
        mock_sd.retrieve.return_value = d_before
        mock_sd.modify.return_value = d_after
        resp = client.post(
            "/admin/disputes/dp_test123/respond",
            headers=admin_headers,
            json={"evidence": "Customer signed up and actively used the service."},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "under_review"
    assert "submitted" in data["message"].lower()
    # Verify Stripe.modify was called with the evidence text
    mock_sd.modify.assert_called_once_with(
        "dp_test123",
        evidence={"uncategorized_text": "Customer signed up and actively used the service."},
        submit=True,
    )
    db.refresh(local_dispute)
    assert local_dispute.status == DisputeStatus.UNDER_REVIEW

    audit = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.account_id == _admin.id,
            BillingAuditLog.action == BillingAuditAction.DISPUTE_UPDATED,
            BillingAuditLog.entity_type == "dispute",
            BillingAuditLog.entity_id == "dp_test123",
        )
        .order_by(BillingAuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.extra_data["operator_action"] == "dispute_evidence_submitted"


def test_dispute_respond_includes_checklist_and_attachments(client, db):
    """Optional proof checklist and attachment names are appended to the dispute evidence text."""
    _admin, admin_headers = _admin_headers(db)
    d_before = _fake_dispute(dispute_status="needs_response")
    d_after = _fake_dispute(dispute_status="under_review")
    with patch("app.core.config.settings") as mock_settings, \
         patch("stripe.Dispute") as mock_sd:
        mock_settings.stripe_secret_key = "sk_test_fake"
        mock_sd.retrieve.return_value = d_before
        mock_sd.modify.return_value = d_after
        resp = client.post(
            "/admin/disputes/dp_test123/respond",
            headers=admin_headers,
            json={
                "evidence": "Customer signed up and actively used the service.",
                "proof_checklist": ["Purchase authorization", "Usage or access log"],
                "attachment_names": ["invoice.pdf", "usage-log.csv"],
                "attachment_urls": [
                    "http://localhost:8000/uploads/documents/invoice.pdf",
                    "http://localhost:8000/uploads/documents/usage-log.csv",
                ],
                "attachment_note": "Invoice and usage export are available internally.",
            },
        )
    assert resp.status_code == 200
    args, kwargs = mock_sd.modify.call_args
    assert args[0] == "dp_test123"
    combined = kwargs["evidence"]["uncategorized_text"]
    assert "Proof checklist:" in combined
    assert "Purchase authorization" in combined
    assert "Attachment references:" in combined
    assert "invoice.pdf" in combined
    assert "http://localhost:8000/uploads/documents/invoice.pdf" in combined
    assert "Invoice and usage export are available internally." in combined


def test_dispute_accept_wrong_state(client, db):
    """Accepting a lost dispute returns 422."""
    _admin, admin_headers = _admin_headers(db)
    d = _fake_dispute(dispute_status="lost")
    with patch("app.core.config.settings") as mock_settings, \
         patch("stripe.Dispute") as mock_sd:
        mock_settings.stripe_secret_key = "sk_test_fake"
        mock_sd.retrieve.return_value = d
        resp = client.post("/admin/disputes/dp_test123/accept", headers=admin_headers)
    assert resp.status_code == 422
    assert "lost" in resp.json()["detail"]


def test_dispute_accept_success(client, db):
    """Closing a needs_response dispute returns the updated status."""
    _admin, admin_headers = _admin_headers(db)
    local_dispute = DisputeModel(
        account_id=_admin.id,
        stripe_dispute_id="dp_test123",
        stripe_charge_id="ch_test123",
        stripe_payment_intent_id="pi_test123",
        amount=14900,
        currency="usd",
        status=DisputeStatus.NEEDS_RESPONSE,
        reason=DisputeReason.GENERAL,
    )
    db.add(local_dispute)
    db.commit()

    d_before = _fake_dispute(dispute_status="needs_response", payment_intent="pi_test123")
    d_after = _fake_dispute(dispute_status="lost", payment_intent="pi_test123")
    with patch("app.core.config.settings") as mock_settings, \
         patch("stripe.Dispute") as mock_sd:
        mock_settings.stripe_secret_key = "sk_test_fake"
        mock_sd.retrieve.return_value = d_before
        mock_sd.close.return_value = d_after
        resp = client.post("/admin/disputes/dp_test123/accept", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "lost"
    assert "refunded" in data["message"].lower()
    mock_sd.close.assert_called_once_with("dp_test123")
    db.refresh(local_dispute)
    assert local_dispute.status == DisputeStatus.LOST

    audit = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.account_id == _admin.id,
            BillingAuditLog.action == BillingAuditAction.DISPUTE_UPDATED,
            BillingAuditLog.entity_type == "dispute",
            BillingAuditLog.entity_id == "dp_test123",
        )
        .order_by(BillingAuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.extra_data["operator_action"] == "dispute_accepted"


def test_dispute_respond_requires_admin(client, auth_headers):
    """Non-admin users receive 403."""
    resp = client.post(
        "/admin/disputes/dp_test/respond",
        headers=auth_headers,
        json={"evidence": "test"},
    )
    assert resp.status_code == 403


def test_dispute_accept_requires_admin(client, auth_headers):
    """Non-admin users receive 403."""
    resp = client.post("/admin/disputes/dp_test/accept", headers=auth_headers)
    assert resp.status_code == 403


def test_get_disputes_falls_back_to_local_ledger_without_stripe_key(client, db):
    """When Stripe is not configured, the admin disputes screen still shows the persisted local dispute ledger."""
    owner, admin_headers = _admin_headers(db)
    dispute = DisputeModel(
        account_id=owner.id,
        stripe_dispute_id="dp_local_only",
        stripe_charge_id="ch_local_only",
        stripe_payment_intent_id="pi_local_only",
        amount=8700,
        currency="usd",
        status=DisputeStatus.WARNING_NEEDS_RESPONSE,
        reason=DisputeReason.FRAUDULENT,
        evidence_due_by=datetime.now(UTC) + timedelta(days=4),
        internal_notes="Customer claims the payment was unrecognized.",
    )
    db.add(dispute)
    db.commit()

    response = client.get("/admin/disputes", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["stripe_available"] is False
    assert payload["data_source"] == "local_cache"
    assert "local dispute ledger" in payload["warning"].lower()
    assert len(payload["disputes"]) == 1
    item = payload["disputes"][0]
    assert item["id"] == "dp_local_only"
    assert item["user_email"] == owner.email
    assert item["payment_id"] == "pi_local_only"
    assert item["status"] == "warning_needs_response"
    assert item["reason"] == "fraudulent"
    assert item["source"] == "local_cache"
    assert item["evidence"] == "Customer claims the payment was unrecognized."
    assert item["evidence_due_by"] is not None


def test_dispute_attachment_upload_uses_cloud_storage(client, db):
    """Admin dispute attachment uploads return a cloud URL rather than a local uploads path."""
    _admin, admin_headers = _admin_headers(db)

    class _StorageStub:
        def upload_file(self, file_data, filename, content_type="application/octet-stream", folder="uploads"):
            assert filename == "evidence.pdf"
            assert content_type == "application/pdf"
            assert "disputes/" in folder
            assert file_data.startswith(b"%PDF")
            return "https://storage.googleapis.com/test-bucket/disputes/evidence.pdf"

    with patch("app.routers.admin.get_storage_service", return_value=_StorageStub()):
        response = client.post(
            "/admin/disputes/attachments",
            headers=admin_headers,
            files={"file": ("evidence.pdf", BytesIO(b"%PDF-test"), "application/pdf")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "evidence.pdf"
    assert payload["url"].startswith("https://storage.googleapis.com/")
