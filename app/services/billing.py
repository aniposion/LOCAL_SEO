"""Billing service for Stripe integration."""

import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.account import Account, AccountRole
from app.models.subscription import (
    AddOnType,
    DunningStatus,
    FREE_PREVIEW_DAYS,
    FREE_PREVIEW_PLAN,
    PaymentHistory,
    PlanType,
    Subscription,
    SubscriptionStatus,
    ADDON_PRICES,
    PLAN_PRICES,
)
from app.models.billing import (
    BillingAuditAction,
    BillingAuditLog,
    BillingInfo,
    Dispute,
    DisputeStatus,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentStatus,
    Refund,
    RefundReason,
    RefundStatus,
    WebhookEventLog,
    WebhookEventStatus,
)
from app.services.credits import credits_service, PlanTier
from app.services.email_service import get_email_service
from app.services.plan_limits import PLAN_LIMITS_BY_PLAN

logger = logging.getLogger(__name__)


PLAN_LIMITS = PLAN_LIMITS_BY_PLAN


class BillingService:
    """Service for handling Stripe billing."""

    def __init__(self, db: Session) -> None:
        self.db = db
        stripe.api_key = settings.stripe_secret_key

    def _notify_admin_billing_email_failure(
        self,
        *,
        notification_type: str,
        title: str,
        message: str,
    ) -> None:
        """Persist an inbox-only alert for admin operators when billing email delivery fails."""
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
            logger.warning("No active admin accounts available for billing email alert %s", notification_type)
            return

        notification_service = NotificationService(self.db)
        for admin in admins:
            notification_service.send_inbox_notification(
                account_id=admin.id,
                title=title,
                message=message,
                notification_type=notification_type,
                url="/admin",
            )

    def _get_price_id(self, plan_type: PlanType, billing_cycle: str) -> str:
        """Get Stripe price ID for plan and billing cycle."""
        price_mapping = {
            (PlanType.MAPS_STARTER, "monthly"): settings.stripe_price_maps_starter_monthly,
            (PlanType.MAPS_STARTER, "yearly"): settings.stripe_price_maps_starter_yearly,
            (PlanType.CALLS_GROWTH, "monthly"): settings.stripe_price_calls_growth_monthly,
            (PlanType.CALLS_GROWTH, "yearly"): settings.stripe_price_calls_growth_yearly,
            (PlanType.COMPETITIVE_MARKET, "monthly"): settings.stripe_price_competitive_market_monthly,
            (PlanType.COMPETITIVE_MARKET, "yearly"): settings.stripe_price_competitive_market_yearly,
            (PlanType.STARTER, "monthly"): settings.stripe_price_starter_monthly,
            (PlanType.STARTER, "yearly"): settings.stripe_price_starter_yearly,
            (PlanType.PRO, "monthly"): settings.stripe_price_pro_monthly,
            (PlanType.PRO, "yearly"): settings.stripe_price_pro_yearly,
            (PlanType.PREMIUM, "monthly"): getattr(settings, 'stripe_price_premium_monthly', ''),
            (PlanType.PREMIUM, "yearly"): getattr(settings, 'stripe_price_premium_yearly', ''),
            (PlanType.AGENCY, "monthly"): settings.stripe_price_agency_monthly,
            (PlanType.AGENCY, "yearly"): settings.stripe_price_agency_yearly,
        }
        price_id = price_mapping.get((plan_type, billing_cycle))
        if not price_id:
            raise ValueError(f"No price configured for {plan_type.value} {billing_cycle}")
        return price_id

    async def create_checkout_session(
        self,
        account_id: UUID,
        plan_type: PlanType,
        billing_cycle: str,
        success_url: str,
        cancel_url: str,
    ) -> tuple[str, str]:
        """Create a Stripe checkout session."""
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise ValueError("Account not found")

        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        # Get or create Stripe customer
        customer_id = subscription.stripe_customer_id if subscription else None
        if not customer_id:
            customer = stripe.Customer.create(
                email=account.email,
                name=account.full_name,
                metadata={"account_id": str(account_id)},
            )
            customer_id = customer.id
            if subscription:
                subscription.stripe_customer_id = customer_id
                self.db.commit()

        price_id = self._get_price_id(plan_type, billing_cycle)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "account_id": str(account_id),
                "plan_type": plan_type.value,
                "billing_cycle": billing_cycle,
            },
            subscription_data={
                "metadata": {
                    "account_id": str(account_id),
                    "plan_type": plan_type.value,
                }
            },
        )

        return session.url, session.id

    async def create_portal_session(
        self,
        account_id: UUID,
        return_url: str,
    ) -> str:
        """Create a Stripe customer portal session."""
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_customer_id:
            raise ValueError("No Stripe customer found")

        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=return_url,
        )

        return session.url

    async def handle_webhook(self, payload: bytes, sig_header: str) -> None:
        """Handle Stripe webhook events with idempotency."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except ValueError:
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise ValueError("Invalid signature")

        # Check idempotency - skip if already processed
        existing_event = self.db.query(WebhookEventLog).filter(
            WebhookEventLog.stripe_event_id == event.id
        ).first()
        
        if existing_event and existing_event.status == WebhookEventStatus.PROCESSED:
            logger.info(f"Skipping already processed webhook: {event.id}")
            return
        
        # Log webhook event
        event_log = existing_event or WebhookEventLog(
            stripe_event_id=event.id,
            event_type=event.type,
            status=WebhookEventStatus.PROCESSING,
            payload=event.data.object.to_dict() if hasattr(event.data.object, 'to_dict') else None,
        )
        if not existing_event:
            self.db.add(event_log)
            self.db.commit()
        
        try:
            handled = await self.handle_verified_event_object(
                event_type=event.type,
                event_object=event.data.object,
            )
            if not handled:
                logger.info("Unhandled Stripe event type in BillingService: %s", event.type)
            
            # Mark as processed
            event_log.status = WebhookEventStatus.PROCESSED
            event_log.processed_at = datetime.now(timezone.utc)
            self.db.commit()
            
        except Exception as e:
            # Log error and mark as failed
            event_log.status = WebhookEventStatus.FAILED
            event_log.error_message = str(e)
            self.db.commit()
            raise

    async def handle_verified_event_object(self, event_type: str, event_object: Any) -> bool:
        """Process an already verified Stripe event object.

        Shared by `/billing/webhook` and `/webhooks/stripe` so billing-side
        behavior stays on one code path.
        """
        if event_type == "checkout.session.completed":
            await self._handle_checkout_completed(event_object)
            return True
        if event_type == "customer.subscription.created":
            await self._handle_subscription_created(event_object)
            return True
        if event_type == "customer.subscription.updated":
            await self._handle_subscription_updated(event_object)
            return True
        if event_type == "customer.subscription.deleted":
            await self._handle_subscription_deleted(event_object)
            return True
        if event_type in {"invoice.paid", "invoice.payment_succeeded"}:
            await self._handle_invoice_paid(event_object)
            return True
        if event_type == "invoice.payment_failed":
            await self._handle_payment_failed(event_object)
            return True
        if event_type == "charge.dispute.created":
            await self._handle_dispute_created(event_object)
            return True
        if event_type == "charge.dispute.updated":
            await self._handle_dispute_updated(event_object)
            return True
        if event_type == "charge.refunded":
            await self._handle_refund_created(event_object)
            return True
        if event_type == "customer.subscription.trial_will_end":
            await self._handle_trial_ending(event_object)
            return True
        return False

    async def _handle_checkout_completed(self, session: Any) -> None:
        """Handle checkout.session.completed event."""
        metadata = session.get("metadata") if hasattr(session, "get") else None
        if metadata is None:
            metadata = getattr(session, "metadata", None)
        if not isinstance(metadata, dict):
            return

        account_id = metadata.get("account_id")
        if not account_id:
            return

        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if subscription:
            customer_id = session.get("customer") if hasattr(session, "get") else None
            if customer_id is None:
                customer_id = getattr(session, "customer", None)

            subscription_id = session.get("subscription") if hasattr(session, "get") else None
            if subscription_id is None:
                subscription_id = getattr(session, "subscription", None)

            subscription.stripe_customer_id = customer_id
            subscription.stripe_subscription_id = subscription_id
            self.db.commit()

    async def _handle_subscription_created(self, stripe_sub: Any) -> None:
        """Handle customer.subscription.created event."""
        account_id = stripe_sub.metadata.get("account_id")
        plan_type_str = stripe_sub.metadata.get("plan_type", "starter")

        if not account_id:
            return

        try:
            plan_type = PlanType(plan_type_str)
        except ValueError:
            plan_type = PlanType.STARTER

        limits = PLAN_LIMITS.get(plan_type, PLAN_LIMITS[PlanType.FREE])

        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if subscription:
            subscription.plan_type = plan_type
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.stripe_subscription_id = stripe_sub.id
            subscription.stripe_price_id = stripe_sub.items.data[0].price.id if stripe_sub.items.data else None
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_sub.current_period_start, tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_sub.current_period_end, tz=timezone.utc
            )
            subscription.locations_limit = limits["locations"]
            subscription.posts_per_month = limits["posts_per_month"]
            subscription.api_calls_per_day = limits["api_calls_per_day"]
            self.db.commit()

    async def _handle_subscription_updated(self, stripe_sub: Any) -> None:
        """Handle customer.subscription.updated event."""
        subscription = self.db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub.id
        ).first()

        if not subscription:
            return

        # Update status
        status_mapping = {
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "trialing": SubscriptionStatus.TRIALING,
            "paused": SubscriptionStatus.PAUSED,
        }
        subscription.status = status_mapping.get(stripe_sub.status, SubscriptionStatus.ACTIVE)
        subscription.cancel_at_period_end = stripe_sub.cancel_at_period_end
        subscription.current_period_start = datetime.fromtimestamp(
            stripe_sub.current_period_start, tz=timezone.utc
        )
        subscription.current_period_end = datetime.fromtimestamp(
            stripe_sub.current_period_end, tz=timezone.utc
        )
        self.db.commit()

    async def _handle_subscription_deleted(self, stripe_sub: Any) -> None:
        """Handle customer.subscription.deleted event."""
        subscription = self.db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub.id
        ).first()

        if subscription:
            # Downgrade to free plan
            limits = PLAN_LIMITS[PlanType.FREE]
            subscription.plan_type = PlanType.FREE
            subscription.status = SubscriptionStatus.CANCELED
            subscription.stripe_subscription_id = None
            subscription.stripe_price_id = None
            subscription.locations_limit = limits["locations"]
            subscription.posts_per_month = limits["posts_per_month"]
            subscription.api_calls_per_day = limits["api_calls_per_day"]
            self.db.commit()

    async def _handle_invoice_paid(self, invoice: Any) -> None:
        """Handle invoice.paid event - RESETS MONTHLY CREDITS."""
        customer_id = invoice.customer
        subscription = self.db.query(Subscription).filter(
            Subscription.stripe_customer_id == customer_id
        ).first()

        if subscription:
            # Record payment
            payment = PaymentHistory(
                account_id=subscription.account_id,
                stripe_payment_intent_id=invoice.payment_intent,
                stripe_invoice_id=invoice.id,
                amount=invoice.amount_paid / 100,  # Convert from cents
                currency=invoice.currency.upper(),
                status="succeeded",
                description=f"Subscription payment - {subscription.plan_type.value}",
                invoice_url=invoice.hosted_invoice_url,
                receipt_url=invoice.receipt_url if hasattr(invoice, 'receipt_url') else None,
            )
            self.db.add(payment)
            self.db.commit()
            
            # ========================================
            # MONTHLY CREDIT RESET ON PAYMENT
            # ========================================
            # Map PlanType to PlanTier for credits service
            plan_tier_map = {
                PlanType.FREE: PlanTier.FREE,
                PlanType.MAPS_STARTER: PlanTier.STARTER,
                PlanType.CALLS_GROWTH: PlanTier.PROFESSIONAL,
                PlanType.COMPETITIVE_MARKET: PlanTier.AGENCY,
                PlanType.STARTER: PlanTier.STARTER,
                PlanType.PRO: PlanTier.PROFESSIONAL,
                PlanType.PREMIUM: PlanTier.PROFESSIONAL,  # Premium uses pro limits
                PlanType.AGENCY: PlanTier.AGENCY,
            }
            plan_tier = plan_tier_map.get(subscription.plan_type, PlanTier.FREE)
            
            # Process payment: resets usage counters and allocates monthly credits
            credit_result = credits_service.process_payment(
                account_id=str(subscription.account_id),
                plan=plan_tier,
                payment_date=datetime.now(timezone.utc),
            )
            
            # Log the credit allocation
            logger.info(
                f"Monthly credits reset for account {subscription.account_id}: "
                f"Plan={plan_tier.value}, Credits={credit_result['credits_allocated']}"
            )
            
            # Reset dunning status on successful payment
            from app.services.dunning_service import get_dunning_service
            dunning_service = get_dunning_service(self.db)
            await dunning_service.handle_payment_success(subscription)

            self._log_audit(
                account_id=subscription.account_id,
                action=BillingAuditAction.PAYMENT_SUCCEEDED,
                entity_type="invoice",
                entity_id=invoice.id,
                new_value={
                    "amount": invoice.amount_paid / 100,
                    "currency": invoice.currency.upper(),
                    "payment_intent": invoice.payment_intent,
                },
            )
            
            # ========================================
            # SEND PAYMENT RECEIPT EMAIL
            # ========================================
            try:
                # Get account for email
                account = self.db.query(Account).filter(
                    Account.id == subscription.account_id
                ).first()
                
                if account and account.email:
                    email_service = get_email_service()
                    
                    # Determine billing cycle from price
                    billing_cycle = "monthly"
                    if subscription.stripe_price_id:
                        if "yearly" in subscription.stripe_price_id.lower() or "annual" in subscription.stripe_price_id.lower():
                            billing_cycle = "yearly"
                    
                    # Format next billing date
                    next_billing_date = ""
                    if subscription.current_period_end:
                        next_billing_date = subscription.current_period_end.strftime("%Y년 %m월 %d일")
                    
                    # Plan name mapping
                    plan_names = {
                        PlanType.MAPS_STARTER: "Maps Starter",
                        PlanType.CALLS_GROWTH: "Calls Growth",
                        PlanType.COMPETITIVE_MARKET: "Competitive Market",
                        PlanType.STARTER: "Starter",
                        PlanType.PRO: "Professional",
                        PlanType.PREMIUM: "Premium",
                        PlanType.AGENCY: "Agency",
                    }
                    plan_name = plan_names.get(subscription.plan_type, subscription.plan_type.value.title())
                    
                    payment_data = {
                        "customer_name": account.full_name or account.email.split('@')[0],
                        "amount": invoice.amount_paid / 100,
                        "currency": invoice.currency.upper(),
                        "plan_name": plan_name,
                        "billing_cycle": billing_cycle,
                        "invoice_url": invoice.hosted_invoice_url,
                        "receipt_url": getattr(invoice, 'receipt_url', None) or "",
                        "payment_date": datetime.now(timezone.utc).strftime("%Y년 %m월 %d일 %H:%M"),
                        "invoice_number": invoice.id,
                        "next_billing_date": next_billing_date,
                    }
                    
                    await email_service.send_payment_receipt(
                        to=account.email,
                        payment_data=payment_data,
                    )
                    logger.info(f"Payment receipt email sent to {account.email}")
                    
            except Exception as e:
                # Don't fail the webhook if email fails
                logger.error(f"Failed to send payment receipt email: {e}")
                self._notify_admin_billing_email_failure(
                    notification_type="billing_receipt_email_failed",
                    title="Billing receipt email failed",
                    message=(
                        "The payment receipt email could not be sent.\n\n"
                        f"Account: {account.email if account and account.email else 'Not recorded'}\n"
                        f"Subscription ID: {subscription.id}\n"
                        f"Invoice ID: {invoice.id}\n"
                        f"Reason: {e}"
                    ),
                )

    async def _handle_payment_failed(self, invoice: Any) -> None:
        """Handle invoice.payment_failed event with dunning workflow."""
        from app.services.dunning_service import get_dunning_service
        
        customer_id = invoice.customer
        subscription = self.db.query(Subscription).filter(
            Subscription.stripe_customer_id == customer_id
        ).first()

        if subscription:
            subscription.status = SubscriptionStatus.PAST_DUE

            # Record failed payment
            payment = PaymentHistory(
                account_id=subscription.account_id,
                stripe_invoice_id=invoice.id,
                amount=invoice.amount_due / 100,
                currency=invoice.currency.upper(),
                status="failed",
                description="Payment failed",
            )
            self.db.add(payment)
            self.db.commit()
            
            # Handle dunning workflow
            dunning_service = get_dunning_service(self.db)
            failure_message = None
            if hasattr(invoice, 'last_finalization_error') and invoice.last_finalization_error:
                failure_message = invoice.last_finalization_error.message
            
            attempt_count = invoice.attempt_count if hasattr(invoice, 'attempt_count') else 1
            
            await dunning_service.handle_payment_failure(
                subscription=subscription,
                failure_message=failure_message,
                attempt_count=attempt_count,
            )
            
            # Audit log
            self._log_audit(
                account_id=subscription.account_id,
                action=BillingAuditAction.PAYMENT_FAILED,
                entity_type="invoice",
                entity_id=invoice.id,
                new_value={
                    "attempt_count": attempt_count,
                    "failure_message": failure_message,
                },
            )

    async def _handle_dispute_created(self, dispute: Any) -> None:
        """Handle charge.dispute.created event."""
        charge_id = dispute.charge
        
        # Find the payment associated with this charge
        payment = self.db.query(Payment).filter(
            Payment.stripe_charge_id == charge_id
        ).first()
        
        if not payment:
            # Try to find by payment intent
            if dispute.payment_intent:
                payment = self.db.query(Payment).filter(
                    Payment.stripe_payment_intent_id == dispute.payment_intent
                ).first()
        
        account_id = payment.account_id if payment else None
        
        # Create dispute record with evidence snapshot
        evidence_snapshot = None
        if account_id:
            account = self.db.query(Account).filter(Account.id == account_id).first()
            subscription = self.db.query(Subscription).filter(
                Subscription.account_id == account_id
            ).first()
            
            if account and subscription:
                evidence_snapshot = {
                    "customer_email": account.email,
                    "signup_date": account.created_at.isoformat() if account.created_at else None,
                    "plan_at_dispute": subscription.plan_type.value if subscription else None,
                    "subscription_status": subscription.status.value if subscription else None,
                }
        
        dispute_record = Dispute(
            account_id=account_id,
            payment_id=payment.id if payment else None,
            stripe_dispute_id=dispute.id,
            stripe_charge_id=charge_id,
            stripe_payment_intent_id=dispute.payment_intent,
            amount=dispute.amount,
            currency=dispute.currency,
            status=DisputeStatus(dispute.status.replace("_", "_")),
            reason=dispute.reason if hasattr(dispute, 'reason') else None,
            evidence_snapshot=evidence_snapshot,
            evidence_due_by=datetime.fromtimestamp(dispute.evidence_details.due_by, tz=timezone.utc) if dispute.evidence_details else None,
        )
        self.db.add(dispute_record)
        self.db.commit()
        
        # Audit log
        if account_id:
            self._log_audit(
                account_id=account_id,
                action=BillingAuditAction.DISPUTE_CREATED,
                entity_type="dispute",
                entity_id=dispute.id,
                new_value={
                    "amount": dispute.amount,
                    "reason": dispute.reason if hasattr(dispute, 'reason') else None,
                },
            )
        
        logger.warning(f"Dispute created: {dispute.id} for charge {charge_id}")

    async def _handle_dispute_updated(self, dispute: Any) -> None:
        """Handle charge.dispute.updated event."""
        dispute_record = self.db.query(Dispute).filter(
            Dispute.stripe_dispute_id == dispute.id
        ).first()
        
        if dispute_record:
            old_status = dispute_record.status
            dispute_record.status = DisputeStatus(dispute.status.replace("_", "_"))
            self.db.commit()
            
            # Audit log
            if dispute_record.account_id:
                self._log_audit(
                    account_id=dispute_record.account_id,
                    action=BillingAuditAction.DISPUTE_UPDATED,
                    entity_type="dispute",
                    entity_id=dispute.id,
                    old_value={"status": old_status.value},
                    new_value={"status": dispute_record.status.value},
                )
            
            logger.info(f"Dispute updated: {dispute.id} status={dispute_record.status}")

    async def _handle_refund_created(self, charge: Any) -> None:
        """Handle charge.refunded event."""
        if not charge.refunds or not charge.refunds.data:
            return
        
        for refund_data in charge.refunds.data:
            # Check if refund already recorded
            existing = self.db.query(Refund).filter(
                Refund.stripe_refund_id == refund_data.id
            ).first()
            
            if existing:
                continue
            
            # Find associated payment
            payment = self.db.query(Payment).filter(
                Payment.stripe_charge_id == charge.id
            ).first()
            
            if not payment:
                if charge.payment_intent:
                    payment = self.db.query(Payment).filter(
                        Payment.stripe_payment_intent_id == charge.payment_intent
                    ).first()

            if not payment:
                logger.warning(
                    "Skipping refund %s for charge %s: no local billing payment found",
                    refund_data.id,
                    charge.id,
                )
                continue
            
            account_id = payment.account_id if payment else None
            
            refund = Refund(
                account_id=account_id,
                payment_id=payment.id if payment else None,
                stripe_refund_id=refund_data.id,
                stripe_charge_id=charge.id,
                stripe_payment_intent_id=charge.payment_intent,
                amount=refund_data.amount,
                currency=refund_data.currency,
                status=RefundStatus(refund_data.status),
                reason=RefundReason(refund_data.reason) if refund_data.reason else None,
            )
            self.db.add(refund)
            
            # Update payment status
            if payment:
                if refund_data.amount >= payment.amount:
                    payment.status = PaymentStatus.REFUNDED
                else:
                    payment.status = PaymentStatus.PARTIALLY_REFUNDED
                payment.amount_refunded += refund_data.amount
            
            self.db.commit()
            
            # Audit log
            if account_id:
                self._log_audit(
                    account_id=account_id,
                    action=BillingAuditAction.REFUND_CREATED,
                    entity_type="refund",
                    entity_id=refund_data.id,
                    new_value={
                        "amount": refund_data.amount,
                        "reason": refund_data.reason,
                    },
                )
            
            logger.info(f"Refund recorded: {refund_data.id} amount={refund_data.amount}")

    async def _handle_trial_ending(self, stripe_sub: Any) -> None:
        """Handle customer.subscription.trial_will_end event (3 days before trial ends)."""
        subscription = self.db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub.id
        ).first()
        
        if not subscription:
            return
        
        account = self.db.query(Account).filter(
            Account.id == subscription.account_id
        ).first()
        
        if not account or not account.email:
            return
        
        try:
            email_service = get_email_service()
            
            trial_end = datetime.fromtimestamp(stripe_sub.trial_end, tz=timezone.utc)
            trial_end_str = trial_end.strftime("%B %d, %Y")
            user_name = account.full_name or account.email.split("@")[0]
            subject = "[Local SEO Optimizer] Your free preview is ending soon"
            message = (
                f"<p>Hi {user_name},</p>"
                f"<p>Your free preview ends on <strong>{trial_end_str}</strong>.</p>"
                "<p>Choose a paid plan in Billing to unlock AI generation, SMS workflows, "
                "publishing, reports, and automation.</p>"
                '<p style="margin-top: 20px;">'
                '<a href="https://app.localseo.com/dashboard/billing" '
                'style="background: #0f766e; color: white; padding: 12px 24px; '
                'border-radius: 8px; text-decoration: none;">Choose a Paid Plan</a>'
                "</p>"
            )
            html_content = f"""
            <html>
            <body style="font-family: sans-serif; padding: 20px;">
                <h2>Free Preview Ending Soon</h2>
                {message}
            </body>
            </html>
            """
            await email_service.send_email(
                to=account.email,
                subject=subject,
                html_content=html_content,
            )
            logger.info(f"Preview ending email sent to {account.email}")
            return

            trial_end_str = trial_end.strftime("%Y년 %m월 %d일")
            
            # Check if payment method is set up
            has_payment_method = False
            if subscription.stripe_customer_id:
                try:
                    payment_methods = stripe.PaymentMethod.list(
                        customer=subscription.stripe_customer_id,
                        type="card",
                    )
                    has_payment_method = len(payment_methods.data) > 0
                except:
                    pass
            
            if has_payment_method:
                subject = f"[Local SEO Optimizer] 무료 체험이 3일 후 종료됩니다"
                message = f"""
                <p>안녕하세요 {account.full_name or account.email.split('@')[0]}님,</p>
                <p>무료 체험 기간이 <strong>{trial_end_str}</strong>에 종료됩니다.</p>
                <p>결제 수단이 등록되어 있으므로 자동으로 구독이 시작됩니다.</p>
                """
            else:
                subject = f"[Local SEO Optimizer] 결제 수단을 등록해주세요 - 체험 3일 남음"
                message = f"""
                <p>안녕하세요 {account.full_name or account.email.split('@')[0]}님,</p>
                <p>무료 체험 기간이 <strong>{trial_end_str}</strong>에 종료됩니다.</p>
                <p><strong>결제 수단이 등록되지 않았습니다.</strong></p>
                <p>계속 서비스를 이용하시려면 결제 수단을 등록해주세요.</p>
                <p style="margin-top: 20px;">
                    <a href="https://app.localseo.com/dashboard/billing" 
                       style="background: #6366f1; color: white; padding: 12px 24px; 
                              border-radius: 8px; text-decoration: none;">
                        결제 수단 등록하기
                    </a>
                </p>
                """
            
            html_content = f"""
            <html>
            <body style="font-family: sans-serif; padding: 20px;">
                <h2>무료 체험 종료 안내</h2>
                {message}
            </body>
            </html>
            """
            
            await email_service.send_email(
                to=account.email,
                subject=subject,
                html_content=html_content,
            )
            
            logger.info(f"Trial ending email sent to {account.email}")
            
        except Exception as e:
            logger.error(f"Failed to send trial ending email: {e}")
            self._notify_admin_billing_email_failure(
                notification_type="billing_trial_ending_email_failed",
                title="Billing trial ending email failed",
                message=(
                    "The trial ending reminder email could not be sent.\n\n"
                    f"Account: {account.email if account and account.email else 'Not recorded'}\n"
                    f"Subscription ID: {subscription.id}\n"
                    f"Stripe subscription ID: {stripe_sub.id}\n"
                    f"Reason: {e}"
                ),
            )

    async def cancel_subscription(self, account_id: UUID) -> None:
        """Cancel subscription at period end."""
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_subscription_id:
            raise ValueError("No active subscription found")

        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True,
        )

        subscription.cancel_at_period_end = True
        self.db.commit()

    async def reactivate_subscription(self, account_id: UUID) -> None:
        """Reactivate a canceled subscription."""
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_subscription_id:
            raise ValueError("No subscription found")

        if not subscription.cancel_at_period_end:
            raise ValueError("Subscription is not scheduled for cancellation")

        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        subscription.cancel_at_period_end = False
        self.db.commit()

    # ============================================
    # TRIAL MANAGEMENT
    # ============================================

    async def start_trial(
        self,
        account_id: UUID,
        plan_type: PlanType = FREE_PREVIEW_PLAN,
        trial_days: int = FREE_PREVIEW_DAYS,
    ) -> Subscription:
        """
        Start a no-card free preview.

        Public previews intentionally stay on the Free plan. Paid features can
        create external AI, SMS, publishing, or storage cost, so they require a
        paid subscription instead of a no-card preview.
        """
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise ValueError("Account not found")

        if plan_type != FREE_PREVIEW_PLAN:
            raise ValueError(
                "The no-card preview only includes the Free plan. Choose a paid plan in Billing to unlock paid features."
            )

        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if (
            subscription
            and subscription.plan_type == FREE_PREVIEW_PLAN
            and subscription.trial_start is not None
        ):
            if subscription.status == SubscriptionStatus.TRIALING and not subscription.has_trial_ended:
                return subscription
            raise ValueError(
                "The free preview has already been used for this account. Choose a paid plan in Billing to unlock paid features."
            )

        if (
            subscription
            and subscription.plan_type != FREE_PREVIEW_PLAN
            and subscription.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
            and subscription.is_active
        ):
            raise ValueError("Account already has an active subscription")

        limits = PLAN_LIMITS.get(plan_type, PLAN_LIMITS[PlanType.FREE])
        trial_start = datetime.now(timezone.utc)
        trial_end = trial_start + timedelta(days=trial_days)

        if subscription:
            subscription.plan_type = plan_type
            subscription.status = SubscriptionStatus.TRIALING
            subscription.trial_start = trial_start
            subscription.trial_end = trial_end
            subscription.current_period_end = trial_end
            subscription.locations_limit = limits["locations"]
            subscription.posts_per_month = limits["posts_per_month"]
            subscription.api_calls_per_day = limits["api_calls_per_day"]
            subscription.active_addons = []
            subscription.access_state = "active"
        else:
            subscription = Subscription(
                account_id=account_id,
                plan_type=plan_type,
                status=SubscriptionStatus.TRIALING,
                trial_start=trial_start,
                trial_end=trial_end,
                current_period_end=trial_end,
                locations_limit=limits["locations"],
                posts_per_month=limits["posts_per_month"],
                api_calls_per_day=limits["api_calls_per_day"],
            )
            self.db.add(subscription)

        self.db.commit()

        # Audit log
        self._log_audit(
            account_id=account_id,
            action=BillingAuditAction.SUBSCRIPTION_CREATED,
            entity_type="subscription",
            entity_id=f"free-preview:{subscription.id}",
            new_value={"plan_type": plan_type.value, "trial_days": trial_days},
        )

        return subscription

    # ============================================
    # SUBSCRIPTION PREVIEW (PRORATION)
    # ============================================

    async def preview_subscription_change(
        self,
        account_id: UUID,
        new_plan_type: PlanType,
        new_addons: list[str] = None,
        proration_date: datetime = None,
    ) -> dict:
        """
        Preview subscription change with proration calculation.
        Returns amount due now, next invoice amount, and line items.
        """
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_subscription_id:
            raise ValueError("No active subscription found")

        # Get current subscription from Stripe
        stripe_sub = stripe.Subscription.retrieve(
            subscription.stripe_subscription_id,
            expand=["items.data.price"]
        )

        # Build new items list
        new_price_id = self._get_price_id(new_plan_type, "monthly")
        new_items = [{"price": new_price_id, "quantity": 1}]

        # Add add-on prices
        addon_prices = self._get_addon_price_ids()
        if new_addons:
            for addon in new_addons:
                if addon in addon_prices:
                    new_items.append({"price": addon_prices[addon], "quantity": 1})

        # Create proration preview using upcoming invoice
        proration_ts = int((proration_date or datetime.now(timezone.utc)).timestamp())

        try:
            upcoming = stripe.Invoice.upcoming(
                customer=subscription.stripe_customer_id,
                subscription=subscription.stripe_subscription_id,
                subscription_items=[
                    {
                        "id": stripe_sub.items.data[0].id,
                        "price": new_price_id,
                        "quantity": 1,
                    }
                ],
                subscription_proration_date=proration_ts,
            )

            # Parse line items
            preview_items = []
            for line in upcoming.lines.data:
                preview_items.append({
                    "description": line.description,
                    "amount": line.amount,
                    "period_start": datetime.fromtimestamp(line.period.start, tz=timezone.utc).isoformat(),
                    "period_end": datetime.fromtimestamp(line.period.end, tz=timezone.utc).isoformat(),
                    "proration": line.proration,
                })

            # Calculate amounts
            amount_due_now = max(0, upcoming.amount_due)
            credit_applied = sum(
                item.amount for item in upcoming.lines.data
                if item.amount < 0
            )

            return {
                "current_plan": {
                    "name": subscription.plan_type.value.title(),
                    "price": PLAN_PRICES.get(subscription.plan_type, 0) * 100,
                    "add_ons": subscription.active_addons or [],
                },
                "new_plan": {
                    "name": new_plan_type.value.title(),
                    "price": PLAN_PRICES.get(new_plan_type, 0) * 100,
                    "add_ons": new_addons or [],
                },
                "proration": {
                    "amount_due_now": amount_due_now,
                    "credit_applied": abs(credit_applied),
                    "next_invoice_date": datetime.fromtimestamp(
                        upcoming.next_payment_attempt or upcoming.period_end, tz=timezone.utc
                    ).isoformat() if upcoming.next_payment_attempt else None,
                    "next_invoice_amount": upcoming.total,
                },
                "effective": "immediate",
                "preview_line_items": preview_items,
            }

        except stripe.error.InvalidRequestError as e:
            raise ValueError(f"Failed to preview subscription change: {str(e)}")

    async def change_subscription(
        self,
        account_id: UUID,
        new_plan_type: PlanType,
        new_addons: list[str] = None,
        prorate: bool = True,
    ) -> Subscription:
        """
        Change subscription plan and/or add-ons.
        Upgrades are immediate with proration.
        Downgrades take effect at next billing cycle.
        """
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_subscription_id:
            raise ValueError("No active subscription found")

        old_plan = subscription.plan_type
        is_upgrade = PLAN_PRICES.get(new_plan_type, 0) > PLAN_PRICES.get(old_plan, 0)

        # Get Stripe subscription
        stripe_sub = stripe.Subscription.retrieve(
            subscription.stripe_subscription_id
        )

        new_price_id = self._get_price_id(new_plan_type, "monthly")

        # Modify subscription
        if is_upgrade:
            # Immediate change with proration for upgrades
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                items=[{
                    "id": stripe_sub.items.data[0].id,
                    "price": new_price_id,
                }],
                proration_behavior="create_prorations" if prorate else "none",
            )
        else:
            # Schedule change for next billing cycle for downgrades
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                items=[{
                    "id": stripe_sub.items.data[0].id,
                    "price": new_price_id,
                }],
                proration_behavior="none",
                billing_cycle_anchor="unchanged",
            )

        # Update local subscription
        limits = PLAN_LIMITS.get(new_plan_type, PLAN_LIMITS[PlanType.FREE])
        subscription.plan_type = new_plan_type
        subscription.stripe_price_id = new_price_id
        subscription.active_addons = new_addons or []
        subscription.locations_limit = limits["locations"]
        subscription.posts_per_month = limits["posts_per_month"]
        subscription.api_calls_per_day = limits["api_calls_per_day"]
        self.db.commit()

        # Audit log
        self._log_audit(
            account_id=account_id,
            action=BillingAuditAction.PLAN_CHANGED,
            entity_type="subscription",
            entity_id=subscription.stripe_subscription_id,
            old_value={"plan_type": old_plan.value},
            new_value={"plan_type": new_plan_type.value, "is_upgrade": is_upgrade},
        )

        return subscription

    # ============================================
    # CANCEL / RESUME
    # ============================================

    async def cancel_subscription_with_reason(
        self,
        account_id: UUID,
        cancel_at_period_end: bool = True,
        reason: str = None,
        feedback: str = None,
    ) -> dict:
        """
        Cancel subscription with reason tracking.
        Returns cancellation details.
        """
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_subscription_id:
            raise ValueError("No active subscription found")

        if cancel_at_period_end:
            # Cancel at end of period (recommended)
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True,
                cancellation_details={
                    "comment": feedback[:500] if feedback else None,
                }
            )
            subscription.cancel_at_period_end = True
            subscription.cancellation_reason = reason
            subscription.cancellation_feedback = feedback
            subscription.canceled_at = datetime.now(timezone.utc)
        else:
            # Immediate cancellation
            stripe.Subscription.cancel(subscription.stripe_subscription_id)
            subscription.status = SubscriptionStatus.CANCELED
            subscription.canceled_at = datetime.now(timezone.utc)
            subscription.ended_at = datetime.now(timezone.utc)
            subscription.cancellation_reason = reason
            subscription.cancellation_feedback = feedback

        self.db.commit()

        # Audit log
        self._log_audit(
            account_id=account_id,
            action=BillingAuditAction.SUBSCRIPTION_CANCELED,
            entity_type="subscription",
            entity_id=subscription.stripe_subscription_id,
            new_value={
                "cancel_at_period_end": cancel_at_period_end,
                "reason": reason,
            },
        )

        return {
            "status": "canceled" if not cancel_at_period_end else "pending_cancellation",
            "cancel_at_period_end": cancel_at_period_end,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "message": (
                f"Your subscription will remain active until {subscription.current_period_end.strftime('%B %d, %Y')}."
                if cancel_at_period_end and subscription.current_period_end
                else "Your subscription has been canceled immediately."
            ),
        }

    async def resume_subscription(self, account_id: UUID) -> dict:
        """
        Resume a subscription that was scheduled for cancellation.
        """
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_subscription_id:
            raise ValueError("No subscription found")

        if not subscription.cancel_at_period_end:
            raise ValueError("Subscription is not scheduled for cancellation")

        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        subscription.cancel_at_period_end = False
        subscription.cancellation_reason = None
        subscription.cancellation_feedback = None
        subscription.canceled_at = None
        self.db.commit()

        # Audit log
        self._log_audit(
            account_id=account_id,
            action=BillingAuditAction.SUBSCRIPTION_RESUMED,
            entity_type="subscription",
            entity_id=subscription.stripe_subscription_id,
        )

        return {
            "status": "active",
            "cancel_at_period_end": False,
            "message": f"Your subscription has been resumed. You will be billed on {subscription.current_period_end.strftime('%B %d, %Y')}.",
        }

    # ============================================
    # INVOICES
    # ============================================

    async def list_invoices(
        self,
        account_id: UUID,
        status: str = None,
        from_date: datetime = None,
        to_date: datetime = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict:
        """List invoices with filtering."""
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_customer_id:
            return {"invoices": [], "total_count": 0, "has_more": False}

        # Query Stripe directly for invoices
        params = {
            "customer": subscription.stripe_customer_id,
            "limit": limit + 1,  # +1 to check has_more
        }

        if status:
            params["status"] = status

        try:
            stripe_invoices = stripe.Invoice.list(**params)
        except stripe.error.StripeError:
            return {"invoices": [], "total_count": 0, "has_more": False}

        invoices = []
        for inv in stripe_invoices.data[:limit]:
            # Filter by date if specified
            created_at = datetime.fromtimestamp(inv.created, tz=timezone.utc)
            if from_date and created_at < from_date:
                continue
            if to_date and created_at > to_date:
                continue

            invoices.append({
                "id": inv.id,
                "number": inv.number,
                "status": inv.status,
                "amount": inv.total,
                "amount_paid": inv.amount_paid,
                "amount_due": inv.amount_due,
                "currency": inv.currency,
                "created_at": created_at.isoformat(),
                "paid_at": datetime.fromtimestamp(inv.status_transitions.paid_at, tz=timezone.utc).isoformat() if inv.status_transitions.paid_at else None,
                "pdf_url": inv.invoice_pdf,
                "hosted_url": inv.hosted_invoice_url,
                "line_items": [
                    {
                        "description": line.description,
                        "amount": line.amount,
                        "quantity": line.quantity,
                    }
                    for line in inv.lines.data[:5]  # Limit line items
                ],
            })

        return {
            "invoices": invoices,
            "total_count": len(stripe_invoices.data),
            "has_more": len(stripe_invoices.data) > limit,
        }

    async def get_invoice_pdf_url(self, account_id: UUID, invoice_id: str) -> str:
        """Get invoice PDF download URL."""
        # Verify ownership
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_customer_id:
            raise ValueError("No subscription found")

        invoice = stripe.Invoice.retrieve(invoice_id)

        if invoice.customer != subscription.stripe_customer_id:
            raise ValueError("Invoice not found")

        return invoice.invoice_pdf

    async def resend_invoice(self, account_id: UUID, invoice_id: str) -> bool:
        """Resend invoice email via Stripe."""
        # Verify ownership
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_customer_id:
            raise ValueError("No subscription found")

        invoice = stripe.Invoice.retrieve(invoice_id)

        if invoice.customer != subscription.stripe_customer_id:
            raise ValueError("Invoice not found")

        # Stripe will send invoice to customer email
        stripe.Invoice.send_invoice(invoice_id)

        # Audit log
        self._log_audit(
            account_id=account_id,
            action=BillingAuditAction.INVOICE_SENT,
            entity_type="invoice",
            entity_id=invoice_id,
        )

        return True

    # ============================================
    # PAYMENT METHODS
    # ============================================

    async def list_payment_methods(self, account_id: UUID) -> list[dict]:
        """List customer payment methods."""
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_customer_id:
            return []

        payment_methods = stripe.PaymentMethod.list(
            customer=subscription.stripe_customer_id,
            type="card",
        )

        # Get default payment method
        customer = stripe.Customer.retrieve(subscription.stripe_customer_id)
        default_pm = customer.invoice_settings.default_payment_method

        result = []
        for pm in payment_methods.data:
            result.append({
                "id": pm.id,
                "type": pm.type,
                "card": {
                    "brand": pm.card.brand,
                    "last4": pm.card.last4,
                    "exp_month": pm.card.exp_month,
                    "exp_year": pm.card.exp_year,
                },
                "is_default": pm.id == default_pm,
                "created_at": datetime.fromtimestamp(pm.created, tz=timezone.utc).isoformat(),
            })

        return result

    async def add_payment_method(
        self,
        account_id: UUID,
        payment_method_id: str,
        set_as_default: bool = True,
    ) -> dict:
        """Attach a payment method to customer."""
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_customer_id:
            raise ValueError("No subscription found")

        # Attach payment method to customer
        stripe.PaymentMethod.attach(
            payment_method_id,
            customer=subscription.stripe_customer_id,
        )

        if set_as_default:
            stripe.Customer.modify(
                subscription.stripe_customer_id,
                invoice_settings={"default_payment_method": payment_method_id},
            )

        # Audit log
        self._log_audit(
            account_id=account_id,
            action=BillingAuditAction.PAYMENT_METHOD_ADDED,
            entity_type="payment_method",
            entity_id=payment_method_id,
        )

        return {"success": True, "payment_method_id": payment_method_id}

    async def remove_payment_method(
        self,
        account_id: UUID,
        payment_method_id: str,
    ) -> bool:
        """Detach a payment method from customer."""
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_customer_id:
            raise ValueError("No subscription found")

        # Verify ownership
        pm = stripe.PaymentMethod.retrieve(payment_method_id)
        if pm.customer != subscription.stripe_customer_id:
            raise ValueError("Payment method not found")

        stripe.PaymentMethod.detach(payment_method_id)

        # Audit log
        self._log_audit(
            account_id=account_id,
            action=BillingAuditAction.PAYMENT_METHOD_REMOVED,
            entity_type="payment_method",
            entity_id=payment_method_id,
        )

        return True

    async def set_default_payment_method(
        self,
        account_id: UUID,
        payment_method_id: str,
    ) -> bool:
        """Set default payment method."""
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_customer_id:
            raise ValueError("No subscription found")

        stripe.Customer.modify(
            subscription.stripe_customer_id,
            invoice_settings={"default_payment_method": payment_method_id},
        )

        # Also update subscription default
        if subscription.stripe_subscription_id:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                default_payment_method=payment_method_id,
            )

        # Audit log
        self._log_audit(
            account_id=account_id,
            action=BillingAuditAction.PAYMENT_METHOD_DEFAULT_CHANGED,
            entity_type="payment_method",
            entity_id=payment_method_id,
        )

        return True

    # ============================================
    # BILLING INFO
    # ============================================

    async def get_billing_info(self, account_id: UUID) -> Optional[dict]:
        """Get billing/tax info."""
        billing_info = self.db.query(BillingInfo).filter(
            BillingInfo.account_id == account_id
        ).first()

        if not billing_info:
            return None

        return {
            "company_name": billing_info.company_name,
            "tax_id": billing_info.tax_id,
            "tax_id_type": billing_info.tax_id_type,
            "address": {
                "line1": billing_info.address_line1,
                "line2": billing_info.address_line2,
                "city": billing_info.city,
                "state": billing_info.state,
                "postal_code": billing_info.postal_code,
                "country": billing_info.country,
            },
            "billing_email": billing_info.billing_email,
        }

    async def update_billing_info(
        self,
        account_id: UUID,
        company_name: str = None,
        tax_id: str = None,
        tax_id_type: str = None,
        address: dict = None,
        billing_email: str = None,
    ) -> dict:
        """Update billing/tax info and sync to Stripe."""
        billing_info = self.db.query(BillingInfo).filter(
            BillingInfo.account_id == account_id
        ).first()

        if not billing_info:
            billing_info = BillingInfo(account_id=account_id)
            self.db.add(billing_info)

        old_value = {
            "company_name": billing_info.company_name,
            "tax_id": billing_info.tax_id,
        }

        if company_name is not None:
            billing_info.company_name = company_name
        if tax_id is not None:
            billing_info.tax_id = tax_id
        if tax_id_type is not None:
            billing_info.tax_id_type = tax_id_type
        if billing_email is not None:
            billing_info.billing_email = billing_email
        if address:
            billing_info.address_line1 = address.get("line1")
            billing_info.address_line2 = address.get("line2")
            billing_info.city = address.get("city")
            billing_info.state = address.get("state")
            billing_info.postal_code = address.get("postal_code")
            billing_info.country = address.get("country")

        self.db.commit()

        # Sync to Stripe customer
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if subscription and subscription.stripe_customer_id:
            update_params = {}
            if company_name:
                update_params["name"] = company_name
            if billing_email:
                update_params["email"] = billing_email
            if address:
                update_params["address"] = {
                    "line1": address.get("line1"),
                    "line2": address.get("line2"),
                    "city": address.get("city"),
                    "state": address.get("state"),
                    "postal_code": address.get("postal_code"),
                    "country": address.get("country"),
                }

            if update_params:
                stripe.Customer.modify(
                    subscription.stripe_customer_id,
                    **update_params
                )

            # Add tax ID if provided
            if tax_id and tax_id_type:
                try:
                    stripe.Customer.create_tax_id(
                        subscription.stripe_customer_id,
                        type=tax_id_type,
                        value=tax_id,
                    )
                except stripe.error.InvalidRequestError:
                    pass  # Tax ID might already exist

        # Audit log
        self._log_audit(
            account_id=account_id,
            action=BillingAuditAction.BILLING_INFO_UPDATED,
            entity_type="billing_info",
            old_value=old_value,
            new_value={"company_name": company_name, "tax_id": tax_id},
        )

        return await self.get_billing_info(account_id)

    # ============================================
    # CSV EXPORT
    # ============================================

    async def export_payments_csv(
        self,
        account_id: UUID,
        from_date: datetime = None,
        to_date: datetime = None,
        status: str = None,
    ) -> str:
        """Export payment history as CSV."""
        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if not subscription or not subscription.stripe_customer_id:
            return ""

        # Get invoices from Stripe
        params = {
            "customer": subscription.stripe_customer_id,
            "limit": 100,
        }
        if status:
            params["status"] = status

        invoices = stripe.Invoice.list(**params)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Invoice Number",
            "Date",
            "Description",
            "Amount",
            "Currency",
            "Status",
            "Payment Method"
        ])

        for inv in invoices.data:
            created_at = datetime.fromtimestamp(inv.created, tz=timezone.utc)

            if from_date and created_at < from_date:
                continue
            if to_date and created_at > to_date:
                continue

            # Get payment method info if paid
            pm_info = "N/A"
            if inv.charge:
                try:
                    charge = stripe.Charge.retrieve(inv.charge)
                    if charge.payment_method_details and charge.payment_method_details.card:
                        pm_info = f"{charge.payment_method_details.card.brand.title()} •••• {charge.payment_method_details.card.last4}"
                except:
                    pass

            description = inv.lines.data[0].description if inv.lines.data else "Subscription"

            writer.writerow([
                inv.number or inv.id,
                created_at.strftime("%Y-%m-%d"),
                description,
                f"${inv.total / 100:.2f}",
                inv.currency.upper(),
                inv.status.title(),
                pm_info,
            ])

        return output.getvalue()

    # ============================================
    # HELPERS
    # ============================================

    def _get_addon_price_ids(self) -> dict[str, str]:
        """Get add-on price IDs from settings."""
        return {
            AddOnType.MISSED_CALL_TEXT_BACK.value: getattr(settings, 'stripe_price_addon_mcb', ''),
            AddOnType.REVIEW_BOOSTER.value: getattr(settings, 'stripe_price_addon_rb', ''),
            AddOnType.WEBSITE_SEO.value: getattr(settings, 'stripe_price_addon_seo', ''),
            AddOnType.SOCIAL_AUTO_RESPONDER.value: getattr(settings, 'stripe_price_addon_sar', ''),
            AddOnType.VIDEO_GENERATOR.value: getattr(settings, 'stripe_price_addon_video', ''),
        }

    def _log_audit(
        self,
        account_id: UUID,
        action: BillingAuditAction,
        entity_type: str = None,
        entity_id: str = None,
        old_value: dict = None,
        new_value: dict = None,
        user_id: UUID = None,
        ip_address: str = None,
    ) -> None:
        """Log billing audit event."""
        audit = BillingAuditLog(
            account_id=account_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
        )
        self.db.add(audit)
        self.db.commit()
