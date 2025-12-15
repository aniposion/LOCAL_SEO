"""Billing service for Stripe integration."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.account import Account
from app.models.subscription import (
    PaymentHistory,
    PlanType,
    Subscription,
    SubscriptionStatus,
)
from app.services.credits import credits_service, PlanTier


# Plan limits configuration - Updated pricing v1.0
PLAN_LIMITS = {
    PlanType.FREE: {"locations": 1, "posts_per_month": 0, "api_calls_per_day": 10},
    PlanType.STARTER: {"locations": 1, "posts_per_month": 30, "api_calls_per_day": 500},
    PlanType.PRO: {"locations": 1, "posts_per_month": 60, "api_calls_per_day": 2000},
    PlanType.PREMIUM: {"locations": 1, "posts_per_month": 120, "api_calls_per_day": 5000},
    PlanType.AGENCY: {"locations": -1, "posts_per_month": -1, "api_calls_per_day": -1},
}


class BillingService:
    """Service for handling Stripe billing."""

    def __init__(self, db: Session) -> None:
        self.db = db
        stripe.api_key = settings.stripe_secret_key

    def _get_price_id(self, plan_type: PlanType, billing_cycle: str) -> str:
        """Get Stripe price ID for plan and billing cycle."""
        price_mapping = {
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
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except ValueError:
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise ValueError("Invalid signature")

        if event.type == "checkout.session.completed":
            await self._handle_checkout_completed(event.data.object)

        elif event.type == "customer.subscription.created":
            await self._handle_subscription_created(event.data.object)

        elif event.type == "customer.subscription.updated":
            await self._handle_subscription_updated(event.data.object)

        elif event.type == "customer.subscription.deleted":
            await self._handle_subscription_deleted(event.data.object)

        elif event.type == "invoice.paid":
            await self._handle_invoice_paid(event.data.object)

        elif event.type == "invoice.payment_failed":
            await self._handle_payment_failed(event.data.object)

    async def _handle_checkout_completed(self, session: Any) -> None:
        """Handle checkout.session.completed event."""
        account_id = session.metadata.get("account_id")
        if not account_id:
            return

        subscription = self.db.query(Subscription).filter(
            Subscription.account_id == account_id
        ).first()

        if subscription:
            subscription.stripe_customer_id = session.customer
            subscription.stripe_subscription_id = session.subscription
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
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"Monthly credits reset for account {subscription.account_id}: "
                f"Plan={plan_tier.value}, Credits={credit_result['credits_allocated']}"
            )

    async def _handle_payment_failed(self, invoice: Any) -> None:
        """Handle invoice.payment_failed event."""
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
