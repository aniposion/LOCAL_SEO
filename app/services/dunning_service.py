"""Dunning service for handling payment failures and retries."""

import logging
from datetime import timedelta
from uuid import UUID

import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now_naive
from app.models.account import Account, AccountRole
from app.models.subscription import DunningStatus, Subscription, SubscriptionStatus

logger = logging.getLogger(__name__)

# Dunning configuration
DUNNING_CONFIG = {
    "retry_schedule_days": [1, 3, 5],  # Retry on day 1, 3, and 5 after initial failure
    "grace_period_days": 7,  # After retries, 7 days grace period
    "suspension_days": 14,  # After grace period, account suspended
    "data_retention_days": 90,  # Data retained for 90 days after suspension
}


class DunningService:
    """Service for handling payment failure dunning workflow."""

    def __init__(self, db: Session):
        self.db = db

    def _get_account(self, subscription: Subscription) -> Account | None:
        """Resolve the owning account for a subscription."""
        account = getattr(subscription, "account", None)
        if account:
            return account
        return self.db.get(Account, subscription.account_id)

    def _track_account_event(
        self,
        subscription: Subscription,
        *,
        event_name: str,
        properties: dict,
    ) -> None:
        """Track a dunning lifecycle event when the owning account exists."""
        account = self._get_account(subscription)
        if not account:
            logger.warning(
                "Unable to track %s event: account missing for %s",
                event_name,
                subscription.id,
            )
            return

        from app.services.analytics_service import track_event

        track_event(
            user_id=account.id,
            account_id=subscription.account_id,
            event_name=event_name,
            properties=properties,
            db=self.db,
        )

    async def _send_billing_notification(
        self,
        subscription: Subscription,
        *,
        notification_type: str,
        title: str,
        message: str,
        extra_data: dict | None = None,
    ) -> None:
        """Persist an inbox/audit billing alert for the subscription owner."""
        from app.services.notification import NotificationService

        account = self._get_account(subscription)
        if not account:
            logger.warning(
                "Skipping %s notification because account is missing for %s",
                notification_type,
                subscription.id,
            )
            return

        data = {
            "url": "/dashboard/billing",
            "subscription_id": str(subscription.id),
            "dunning_status": subscription.dunning_status.value,
            "access_state": subscription.access_state,
            "portal_url": self._get_customer_portal_url(subscription),
        }
        if extra_data:
            data.update(extra_data)

        try:
            await NotificationService(self.db).send_notification(
                account_id=account.id,
                title=title,
                message=message,
                notification_type=notification_type,
                data=data,
            )
        except Exception as exc:
            logger.warning(
                "Failed to persist %s notification for subscription %s: %s",
                notification_type,
                subscription.id,
                exc,
            )

    def _notify_admin_billing_email_failure(
        self,
        subscription: Subscription,
        *,
        stage_label: str,
        error_message: str,
    ) -> None:
        """Persist an operator-facing inbox alert when a billing lifecycle email fails."""
        from app.services.notification import NotificationService

        admins = (
            self.db.query(Account)
            .filter(
                Account.role == AccountRole.ADMIN,
                Account.is_active == True,  # noqa: E712
            )
            .all()
        )
        if not admins:
            logger.warning(
                "No active admin accounts available for billing email failure alert %s",
                stage_label,
            )
            return

        account = self._get_account(subscription)
        account_email = account.email if account and account.email else "Not recorded"
        title = f"Billing {stage_label} email failed"
        message = (
            f"The billing {stage_label} email could not be sent.\n\n"
            f"Account: {account_email}\n"
            f"Subscription ID: {subscription.id}\n"
            f"Plan: {subscription.plan_type.value.upper()}\n"
            f"Dunning status: {subscription.dunning_status.value}\n"
            f"Access state: {subscription.access_state}\n"
            f"Reason: {error_message}"
        )
        notification_service = NotificationService(self.db)
        for admin in admins:
            notification_service.send_inbox_notification(
                account_id=admin.id,
                title=title,
                message=message,
                notification_type="billing_lifecycle_email_failed",
                url="/admin",
            )

    @staticmethod
    def _resolve_attempt_count(subscription: Subscription, attempt_count: int | None) -> int:
        """Normalize the Stripe attempt counter for retry scheduling."""
        if attempt_count is None or attempt_count <= 0:
            return max(subscription.payment_retry_count + 1, 1)
        return attempt_count

    def _apply_active_state(self, subscription: Subscription) -> None:
        """Reset subscription fields after payment recovery."""
        subscription.access_state = "active"
        subscription.dunning_status = DunningStatus.NONE
        subscription.dunning_started_at = None
        subscription.payment_retry_count = 0
        subscription.last_payment_error = None
        subscription.next_payment_retry_at = None
        subscription.grace_period_ends_at = None
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.ended_at = None

    async def handle_payment_failure(
        self,
        subscription: Subscription,
        failure_message: str | None = None,
        attempt_count: int | None = None,
    ) -> None:
        """Enter or advance the dunning workflow after a failed payment."""
        now = utc_now_naive()
        retry_schedule = DUNNING_CONFIG["retry_schedule_days"]
        normalized_attempt = self._resolve_attempt_count(subscription, attempt_count)

        if subscription.dunning_started_at is None:
            subscription.dunning_started_at = now

        subscription.access_state = "warning"
        subscription.status = SubscriptionStatus.PAST_DUE
        subscription.last_payment_error = failure_message
        subscription.payment_retry_count = normalized_attempt

        if normalized_attempt <= len(retry_schedule):
            subscription.dunning_status = DunningStatus.RETRYING
            subscription.next_payment_retry_at = (
                subscription.dunning_started_at
                + timedelta(days=retry_schedule[normalized_attempt - 1])
            )
            subscription.grace_period_ends_at = None
        else:
            subscription.dunning_status = DunningStatus.GRACE_PERIOD
            subscription.next_payment_retry_at = None
            subscription.grace_period_ends_at = now + timedelta(
                days=DUNNING_CONFIG["grace_period_days"]
            )

        self.db.add(subscription)
        self.db.flush()

        self._track_account_event(
            subscription,
            event_name="payment_failed",
            properties={
                "subscription_id": str(subscription.id),
                "plan_type": subscription.plan_type.value,
                "retry_count": subscription.payment_retry_count,
                "access_state": subscription.access_state,
                "dunning_status": subscription.dunning_status.value,
            },
        )

        if subscription.dunning_status == DunningStatus.GRACE_PERIOD:
            await self._send_grace_period_email(subscription)
            grace_end = (
                subscription.grace_period_ends_at.strftime("%Y-%m-%d")
                if subscription.grace_period_ends_at
                else "soon"
            )
            await self._send_billing_notification(
                subscription,
                notification_type="billing_grace_period_started",
                title="Payment still failing - grace period active",
                message=(
                    "We could not recover your payment after multiple retry attempts.\n\n"
                    f"Your account is now in a grace period until {grace_end}. "
                    "Update your billing method to avoid restricted access."
                ),
                extra_data={"grace_period_ends_at": grace_end},
            )
        else:
            await self._send_dunning_email(subscription, attempt=subscription.payment_retry_count)
            await self._send_billing_notification(
                subscription,
                notification_type="billing_payment_failed",
                title="Payment failed - retry scheduled",
                message=(
                    "We could not process your subscription payment.\n\n"
                    f"Retry attempt {subscription.payment_retry_count} is now in progress. "
                    "Update your billing method to avoid service interruption."
                ),
                extra_data={"retry_count": subscription.payment_retry_count},
            )

        logger.warning(
            "Subscription %s entered dunning state=%s attempt=%s account=%s",
            subscription.id,
            subscription.dunning_status.value,
            subscription.payment_retry_count,
            subscription.account_id,
        )

    async def enter_dunning(self, subscription: Subscription) -> None:
        """Compatibility wrapper for payment-failed webhook flows."""
        await self.handle_payment_failure(subscription)

    async def handle_payment_success(self, subscription: Subscription) -> None:
        """Reset dunning state after a successful payment."""
        previous_state = subscription.access_state
        was_in_dunning = (
            subscription.access_state != "active"
            or subscription.dunning_status != DunningStatus.NONE
            or subscription.payment_retry_count > 0
            or bool(subscription.last_payment_error)
        )

        self._apply_active_state(subscription)
        self.db.add(subscription)
        self.db.flush()

        if was_in_dunning:
            self._track_account_event(
                subscription,
                event_name="payment_recovered",
                properties={
                    "subscription_id": str(subscription.id),
                    "previous_state": previous_state,
                    "plan_type": subscription.plan_type.value,
                },
            )
            await self._send_recovery_email(subscription, previous_state)
            await self._send_billing_notification(
                subscription,
                notification_type="billing_payment_recovered",
                title="Payment received - account restored",
                message=(
                    "Your latest payment succeeded and full access has been restored.\n\n"
                    f"Previous state: {previous_state.upper()}"
                ),
                extra_data={"previous_state": previous_state},
            )

            logger.info(
                "Subscription %s recovered from %s. Account: %s",
                subscription.id,
                previous_state,
                subscription.account_id,
            )

    async def recover_from_dunning(self, subscription: Subscription) -> None:
        """Compatibility wrapper for successful payment webhook flows."""
        await self.handle_payment_success(subscription)

    async def check_grace_period_expiry(
        self,
        account_id: UUID | None = None,
    ) -> list[UUID] | bool:
        """Move expired grace-period subscriptions into restricted warning state."""
        now = utc_now_naive()
        query = self.db.query(Subscription).filter(
            Subscription.dunning_status == DunningStatus.GRACE_PERIOD,
            Subscription.grace_period_ends_at.is_not(None),
            Subscription.grace_period_ends_at <= now,
        )
        if account_id is not None:
            query = query.filter(Subscription.account_id == account_id)

        expired_subscriptions = query.all()
        restricted_ids: list[UUID] = []

        for subscription in expired_subscriptions:
            subscription.dunning_status = DunningStatus.RESTRICTED
            subscription.access_state = "warning"
            subscription.status = SubscriptionStatus.PAST_DUE
            subscription.next_payment_retry_at = None
            self.db.add(subscription)
            restricted_ids.append(subscription.id)

            self._track_account_event(
                subscription,
                event_name="payment_failed",
                properties={
                    "subscription_id": str(subscription.id),
                    "plan_type": subscription.plan_type.value,
                    "retry_count": subscription.payment_retry_count,
                    "access_state": subscription.access_state,
                    "dunning_status": subscription.dunning_status.value,
                    "transition": "grace_period_expired",
                },
            )
            await self._send_restriction_email(subscription)
            await self._send_billing_notification(
                subscription,
                notification_type="billing_access_restricted",
                title="Account access restricted until billing is updated",
                message=(
                    "Your payment is still overdue and account access is now restricted.\n\n"
                    "Update your billing method to restore full access."
                ),
            )

        if restricted_ids:
            self.db.flush()

        if account_id is not None:
            return bool(restricted_ids)
        return restricted_ids

    async def check_suspension(
        self,
        account_id: UUID | None = None,
    ) -> list[UUID] | bool:
        """Suspend subscriptions that have remained delinquent beyond the threshold."""
        now = utc_now_naive()
        cutoff_date = now - timedelta(days=DUNNING_CONFIG["suspension_days"])
        query = self.db.query(Subscription).filter(
            Subscription.dunning_status.notin_([DunningStatus.NONE, DunningStatus.SUSPENDED]),
            Subscription.dunning_started_at.is_not(None),
            Subscription.dunning_started_at <= cutoff_date,
        )
        if account_id is not None:
            query = query.filter(Subscription.account_id == account_id)

        overdue_subscriptions = query.all()
        suspended_ids: list[UUID] = []

        for subscription in overdue_subscriptions:
            subscription.access_state = "suspended"
            subscription.dunning_status = DunningStatus.SUSPENDED
            subscription.status = SubscriptionStatus.CANCELED
            subscription.next_payment_retry_at = None
            subscription.grace_period_ends_at = None
            subscription.ended_at = now
            self.db.add(subscription)
            suspended_ids.append(subscription.id)

            self._track_account_event(
                subscription,
                event_name="subscription_suspended",
                properties={
                    "subscription_id": str(subscription.id),
                    "reason": "payment_overdue",
                    "days_overdue": (
                        (now - subscription.dunning_started_at).days
                        if subscription.dunning_started_at
                        else DUNNING_CONFIG["suspension_days"]
                    ),
                    "dunning_status": subscription.dunning_status.value,
                },
            )
            await self._send_suspension_email(subscription)
            await self._send_billing_notification(
                subscription,
                notification_type="billing_subscription_suspended",
                title="Subscription suspended due to payment failure",
                message=(
                    "Your subscription has been suspended because payment is still overdue.\n\n"
                    "Update your billing method to restore access."
                ),
            )

        if suspended_ids:
            self.db.flush()

        if account_id is not None:
            return bool(suspended_ids)
        return suspended_ids

    async def suspend_overdue_subscriptions(self) -> int:
        """Compatibility helper for older worker code paths."""
        suspended = await self.check_suspension()
        return len(suspended)

    async def _send_dunning_email(self, subscription: Subscription, attempt: int) -> None:
        """Send dunning warning email with a real billing destination."""
        from app.services.email_service import EmailService

        account = self._get_account(subscription)
        if not account or not account.email:
            logger.warning("Skipping dunning email because the account has no email")
            return

        portal_info = self._get_customer_portal_info(subscription)
        email_service = EmailService()

        subject = "Payment Failed - Action Required"
        body = f"""
<p>Hi {account.display_name or "there"},</p>
<p>We had trouble processing your payment for Local SEO Optimizer.</p>
<p>Your account is currently in <strong>WARNING</strong> status. Please update your payment method within 7 days to avoid service interruption.</p>
<p><strong>Update payment method:</strong> <a href="{portal_info["portal_url"]}">{portal_info["portal_url"]}</a></p>
<p><strong>Current plan:</strong> {subscription.plan_type.value.upper()}</p>
<p><strong>Monthly price:</strong> ${subscription.get_monthly_price()}</p>
<p>Need help? Reply to this email.</p>
<p>Thanks,<br/>Local SEO Optimizer Team</p>
"""

        try:
            await email_service.send_email(
                to=account.email,
                subject=subject,
                html_content=body,
                text_body=(
                    f"Payment failed for Local SEO Optimizer.\n\n"
                    f"Update payment method: {portal_info['portal_url']}\n"
                    f"Current plan: {subscription.plan_type.value.upper()}\n"
                    f"Monthly price: ${subscription.get_monthly_price()}\n"
                ),
            )
            logger.info("Dunning email sent to %s", account.email)
        except Exception as exc:
            logger.error("Failed to send dunning email: %s", exc)
            self._notify_admin_billing_email_failure(
                subscription,
                stage_label="dunning",
                error_message=str(exc),
            )

    async def _send_recovery_email(self, subscription: Subscription, previous_state: str) -> None:
        """Send recovery confirmation email."""
        from app.services.email_service import EmailService

        account = self._get_account(subscription)
        if not account or not account.email:
            logger.warning("Skipping recovery email because the account has no email")
            return

        email_service = EmailService()
        subject = "Payment Successful - Account Restored"
        body = f"""
<p>Hi {account.display_name or "there"},</p>
<p>Great news! Your payment was successful and your account has been fully restored.</p>
<p><strong>Previous status:</strong> {previous_state.upper()}</p>
<p><strong>Current status:</strong> ACTIVE</p>
<p>You now have full access to all features.</p>
<p>Thanks for being a valued customer!</p>
<p>Local SEO Optimizer Team</p>
"""

        try:
            await email_service.send_email(
                to=account.email,
                subject=subject,
                html_content=body,
                text_body=(
                    f"Your payment was successful and your account has been restored.\n\n"
                    f"Previous status: {previous_state.upper()}\n"
                    f"Current status: ACTIVE\n"
                ),
            )
            logger.info("Recovery email sent to %s", account.email)
        except Exception as exc:
            logger.error("Failed to send recovery email: %s", exc)
            self._notify_admin_billing_email_failure(
                subscription,
                stage_label="recovery",
                error_message=str(exc),
            )

    async def _send_grace_period_email(self, subscription: Subscription) -> None:
        """Send an escalated warning once retries are exhausted."""
        from app.services.email_service import EmailService

        account = self._get_account(subscription)
        if not account or not account.email:
            logger.warning("Skipping grace-period email because the account has no email")
            return

        email_service = EmailService()
        grace_end = (
            subscription.grace_period_ends_at.strftime("%Y-%m-%d")
            if subscription.grace_period_ends_at
            else "soon"
        )
        body = f"""
<p>Hi {account.display_name or "there"},</p>
<p>We could not recover your payment after multiple retry attempts.</p>
<p>Your account is in a grace period until <strong>{grace_end}</strong>. Update the billing method before then to avoid restricted access.</p>
<p><strong>Update payment method:</strong> <a href="{self._get_customer_portal_url(subscription)}">{self._get_customer_portal_url(subscription)}</a></p>
<p>Thanks,<br/>Local SEO Optimizer Team</p>
"""
        try:
            await email_service.send_email(
                to=account.email,
                subject="Payment Still Failing - Grace Period Active",
                html_content=body,
                text_body=(
                    f"Your account is in a grace period until {grace_end}. "
                    f"Update payment method: {self._get_customer_portal_url(subscription)}"
                ),
            )
        except Exception as exc:
            logger.error("Failed to send grace-period email: %s", exc)
            self._notify_admin_billing_email_failure(
                subscription,
                stage_label="grace-period",
                error_message=str(exc),
            )

    async def _send_restriction_email(self, subscription: Subscription) -> None:
        """Notify the user that billing access is now restricted."""
        from app.services.email_service import EmailService

        account = self._get_account(subscription)
        if not account or not account.email:
            logger.warning("Skipping restricted-access email because the account has no email")
            return

        email_service = EmailService()
        portal_url = self._get_customer_portal_url(subscription)
        body = f"""
<p>Hi {account.display_name or "there"},</p>
<p>Your account access is now restricted because payment is still overdue.</p>
<p>Update your billing method to restore full product access.</p>
<p><strong>Billing:</strong> <a href="{portal_url}">{portal_url}</a></p>
<p>Thanks,<br/>Local SEO Optimizer Team</p>
"""
        try:
            await email_service.send_email(
                to=account.email,
                subject="Account Access Restricted Until Payment Is Updated",
                html_content=body,
                text_body=f"Your account access is restricted. Update billing: {portal_url}",
            )
        except Exception as exc:
            logger.error("Failed to send restricted-access email: %s", exc)
            self._notify_admin_billing_email_failure(
                subscription,
                stage_label="restricted-access",
                error_message=str(exc),
            )

    async def _send_suspension_email(self, subscription: Subscription) -> None:
        """Notify the user that the subscription has been suspended."""
        from app.services.email_service import EmailService

        account = self._get_account(subscription)
        if not account or not account.email:
            logger.warning("Skipping suspension email because the account has no email")
            return

        email_service = EmailService()
        portal_url = self._get_customer_portal_url(subscription)
        body = f"""
<p>Hi {account.display_name or "there"},</p>
<p>Your Local SEO Optimizer subscription has been suspended because payment is still overdue.</p>
<p>Update your billing method to restore access.</p>
<p><strong>Billing:</strong> <a href="{portal_url}">{portal_url}</a></p>
<p>Thanks,<br/>Local SEO Optimizer Team</p>
"""
        try:
            await email_service.send_email(
                to=account.email,
                subject="Subscription Suspended Due To Payment Failure",
                html_content=body,
                text_body=f"Your subscription is suspended. Update billing: {portal_url}",
            )
        except Exception as exc:
            logger.error("Failed to send suspension email: %s", exc)
            self._notify_admin_billing_email_failure(
                subscription,
                stage_label="suspension",
                error_message=str(exc),
            )

    def _get_customer_portal_info(self, subscription: Subscription) -> dict[str, str | bool | None]:
        """Return the best available billing destination without placeholders."""
        billing_url = f"{settings.app_url.rstrip('/')}/dashboard/billing"

        if not subscription.stripe_customer_id:
            logger.warning(
                "Stripe customer portal unavailable for subscription %s: missing customer id",
                subscription.id,
            )
            return {
                "portal_url": billing_url,
                "portal_available": False,
                "portal_source": "billing_page",
                "portal_error": "Stripe customer id is missing",
            }

        if not settings.stripe_secret_key:
            logger.warning(
                "Stripe customer portal unavailable for subscription %s: Stripe secret key missing",
                subscription.id,
            )
            return {
                "portal_url": billing_url,
                "portal_available": False,
                "portal_source": "billing_page",
                "portal_error": "Stripe secret key is not configured",
            }

        try:
            stripe.api_key = settings.stripe_secret_key
            session = stripe.billing_portal.Session.create(
                customer=subscription.stripe_customer_id,
                return_url=billing_url,
            )
            return {
                "portal_url": session.url,
                "portal_available": True,
                "portal_source": "stripe_portal",
                "portal_error": None,
            }
        except Exception as exc:
            logger.warning(
                "Stripe customer portal unavailable for subscription %s: %s",
                subscription.id,
                exc,
            )
            return {
                "portal_url": billing_url,
                "portal_available": False,
                "portal_source": "billing_page",
                "portal_error": str(exc),
            }

    def _get_customer_portal_url(self, subscription: Subscription) -> str:
        """Get the best available payment method update URL."""
        return self._get_customer_portal_info(subscription)["portal_url"]

    def get_dunning_status(self, subscription: Subscription) -> dict:
        """Get dunning status for UI display."""
        portal = self._get_customer_portal_info(subscription)

        if (
            subscription.access_state == "active"
            and subscription.dunning_status == DunningStatus.NONE
        ):
            return {
                "in_dunning": False,
                "state": "active",
                "message": None,
            }

        if subscription.access_state == "suspended" or subscription.dunning_status == DunningStatus.SUSPENDED:
            return {
                "in_dunning": True,
                "state": "suspended",
                "message": "Account suspended due to payment failure. Update payment method to restore access.",
                "portal_url": portal["portal_url"],
                "portal_available": portal["portal_available"],
                "portal_source": portal["portal_source"],
                "portal_error": portal["portal_error"],
            }

        if subscription.dunning_status == DunningStatus.GRACE_PERIOD:
            grace_days_remaining = None
            if subscription.grace_period_ends_at:
                grace_days_remaining = max(
                    0,
                    (subscription.grace_period_ends_at - utc_now_naive()).days,
                )
            return {
                "in_dunning": True,
                "state": "warning",
                "days_remaining": grace_days_remaining,
                "message": (
                    "Payment retries failed. Update your payment method now to avoid suspension."
                ),
                "portal_url": portal["portal_url"],
                "portal_available": portal["portal_available"],
                "portal_source": portal["portal_source"],
                "portal_error": portal["portal_error"],
            }

        if subscription.dunning_status == DunningStatus.RESTRICTED:
            return {
                "in_dunning": True,
                "state": "warning",
                "days_remaining": 0,
                "message": "Billing is overdue and access is restricted until payment is updated.",
                "portal_url": portal["portal_url"],
                "portal_available": portal["portal_available"],
                "portal_source": portal["portal_source"],
                "portal_error": portal["portal_error"],
            }

        days_in_dunning = None
        if subscription.dunning_started_at:
            days_in_dunning = (utc_now_naive() - subscription.dunning_started_at).days

        if subscription.access_state == "warning" or subscription.dunning_status == DunningStatus.RETRYING:
            days_remaining = max(0, DUNNING_CONFIG["grace_period_days"] - (days_in_dunning or 0))
            return {
                "in_dunning": True,
                "state": "warning",
                "days_remaining": days_remaining,
                "message": f"Payment failed. Update your payment method within {days_remaining} days.",
                "portal_url": portal["portal_url"],
                "portal_available": portal["portal_available"],
                "portal_source": portal["portal_source"],
                "portal_error": portal["portal_error"],
            }

        return {
            "in_dunning": False,
            "state": subscription.access_state,
            "message": None,
        }


def get_dunning_service(db: Session) -> DunningService:
    """Factory function to get DunningService instance."""
    return DunningService(db)
