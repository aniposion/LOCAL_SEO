"""Review Booster Program - Automated review collection and management."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


def _analytics_review_value(analytics, key: str) -> float:
    """Read review metrics from current columns or legacy source payloads."""
    source_raw = analytics.source_raw if isinstance(getattr(analytics, "source_raw", None), dict) else {}
    if key == "new_reviews":
        value = getattr(analytics, "new_reviews", None)
        if value is None:
            value = source_raw.get("new_reviews", source_raw.get("reviews", 0))
    elif key == "avg_rating":
        value = getattr(analytics, "avg_rating", None)
        if value is None:
            value = source_raw.get("avg_rating", source_raw.get("rating", 0))
    else:
        value = source_raw.get(key, 0)

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class ReviewSentiment(str, Enum):
    """Review sentiment classification."""
    POSITIVE = "positive"  # 4-5 stars
    NEUTRAL = "neutral"    # 3 stars
    NEGATIVE = "negative"  # 1-2 stars


class ReviewRequestChannel(str, Enum):
    """Channels for sending review requests."""
    SMS = "sms"
    EMAIL = "email"
    BOTH = "both"


class ReviewBoosterService:
    """
    Service for automated review collection and management.
    
    Features:
    - SMS/Email로 리뷰 요청 자동 발송
    - 부정 리뷰 내부 처리 / 긍정 리뷰 Google 유도
    - 리뷰 증가 추세 분석
    """

    # Review request templates by business category
    REQUEST_TEMPLATES = {
        "restaurant": {
            "sms": """Hi {customer_name}! Thank you for dining at {business_name}. We'd love to hear about your experience! 

Leave a quick review: {review_link}

Reply STOP to opt out.""",
            "email_subject": "How was your experience at {business_name}?",
            "email_body": """
Hi {customer_name},

Thank you for visiting {business_name}! We hope you enjoyed your meal.

Your feedback helps us serve you better and helps other customers find us.

<a href="{review_link}" style="background:#4285f4;color:white;padding:12px 24px;text-decoration:none;border-radius:4px;">Leave a Review on Google</a>

It only takes 30 seconds and means the world to us!

Thank you,
{business_name} Team
""",
        },
        "spa": {
            "sms": """Hi {customer_name}! Thank you for visiting {business_name}. We hope you feel refreshed! 

Share your experience: {review_link}

Reply STOP to opt out.""",
            "email_subject": "How was your visit to {business_name}?",
            "email_body": """
Hi {customer_name},

Thank you for choosing {business_name} for your wellness journey!

We'd love to hear about your experience. Your review helps others discover our services.

<a href="{review_link}" style="background:#4285f4;color:white;padding:12px 24px;text-decoration:none;border-radius:4px;">Leave a Review on Google</a>

Thank you for your support!

{business_name} Team
""",
        },
        "default": {
            "sms": """Hi {customer_name}! Thank you for choosing {business_name}. We'd appreciate your feedback!

Leave a review: {review_link}

Reply STOP to opt out.""",
            "email_subject": "We'd love your feedback - {business_name}",
            "email_body": """
Hi {customer_name},

Thank you for your recent visit to {business_name}!

Your feedback is incredibly valuable to us. Would you mind taking a moment to share your experience?

<a href="{review_link}" style="background:#4285f4;color:white;padding:12px 24px;text-decoration:none;border-radius:4px;">Leave a Review on Google</a>

Thank you!

{business_name} Team
""",
        },
    }

    # Negative review internal handling template
    NEGATIVE_REVIEW_INTERNAL_TEMPLATE = """
Hi {customer_name},

We're sorry to hear that your experience at {business_name} didn't meet your expectations.

Your feedback is important to us, and we'd like to make things right. Please reply to this message or call us at {phone} so we can address your concerns directly.

We appreciate you giving us the opportunity to improve.

Sincerely,
{business_name} Management
"""

    def __init__(self, db: Session):
        self.db = db

    async def send_review_request(
        self,
        location_id: UUID,
        customer_name: str,
        customer_email: str | None = None,
        customer_phone: str | None = None,
        channel: ReviewRequestChannel = ReviewRequestChannel.BOTH,
        delay_hours: int = 2,  # Delay after service
    ) -> dict[str, Any]:
        """
        Send a review request to a customer.
        
        Args:
            location_id: Business location ID
            customer_name: Customer's name
            customer_email: Customer's email (required for email channel)
            customer_phone: Customer's phone (required for SMS channel)
            channel: Which channel(s) to use
            delay_hours: Hours to wait before sending (allows time for service completion)
        """
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return {"success": False, "error": "Location not found"}

        # Get Google review link
        review_link = self._get_google_review_link(location)

        # Get template based on category
        category = getattr(location, 'category', 'default') or 'default'
        templates = self.REQUEST_TEMPLATES.get(category, self.REQUEST_TEMPLATES['default'])

        results = {"sms": None, "email": None}

        # Prepare template variables
        template_vars = {
            "customer_name": customer_name.split()[0] if customer_name else "there",
            "business_name": location.name,
            "review_link": review_link,
            "phone": location.phone or "",
        }

        # Send SMS
        if channel in [ReviewRequestChannel.SMS, ReviewRequestChannel.BOTH] and customer_phone:
            sms_message = templates["sms"].format(**template_vars)
            results["sms"] = await self._send_sms(customer_phone, sms_message)

        # Send Email
        if channel in [ReviewRequestChannel.EMAIL, ReviewRequestChannel.BOTH] and customer_email:
            email_subject = templates["email_subject"].format(**template_vars)
            email_body = templates["email_body"].format(**template_vars)
            results["email"] = await self._send_email(
                customer_email,
                email_subject,
                email_body,
            )

        # Log the request
        await self._log_review_request(
            location_id=location_id,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            channel=channel,
            results=results,
        )

        return {
            "success": any(r and r.get("success") for r in results.values() if r),
            "results": results,
        }

    async def send_bulk_review_requests(
        self,
        location_id: UUID,
        customers: list[dict],
        channel: ReviewRequestChannel = ReviewRequestChannel.BOTH,
    ) -> dict[str, Any]:
        """
        Send review requests to multiple customers.
        
        Args:
            location_id: Business location ID
            customers: List of {"name": str, "email": str, "phone": str}
            channel: Which channel(s) to use
        """
        results = []
        success_count = 0
        fail_count = 0

        for customer in customers:
            result = await self.send_review_request(
                location_id=location_id,
                customer_name=customer.get("name", ""),
                customer_email=customer.get("email"),
                customer_phone=customer.get("phone"),
                channel=channel,
            )

            if result.get("success"):
                success_count += 1
            else:
                fail_count += 1

            results.append({
                "customer": customer.get("name"),
                "result": result,
            })

        return {
            "total": len(customers),
            "success": success_count,
            "failed": fail_count,
            "details": results,
        }

    async def handle_new_review(
        self,
        location_id: UUID,
        review_data: dict,
    ) -> dict[str, Any]:
        """
        Handle a new review - route positive to Google, handle negative internally.
        
        Args:
            location_id: Business location ID
            review_data: Review data from webhook
        """
        rating = review_data.get("rating", 0)
        reviewer_name = review_data.get("reviewer_name", "Customer")

        # Classify sentiment
        if rating >= 4:
            sentiment = ReviewSentiment.POSITIVE
        elif rating == 3:
            sentiment = ReviewSentiment.NEUTRAL
        else:
            sentiment = ReviewSentiment.NEGATIVE

        # Handle based on sentiment
        if sentiment == ReviewSentiment.NEGATIVE:
            # Send internal follow-up to address concerns
            return await self._handle_negative_review(
                location_id=location_id,
                review_data=review_data,
            )
        else:
            # Thank the customer and encourage sharing
            return await self._handle_positive_review(
                location_id=location_id,
                review_data=review_data,
            )

    async def get_review_analytics(
        self,
        location_id: UUID,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Get review analytics and trends.
        """
        from app.models.analytics import Analytics
        from datetime import date

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Get analytics data
        analytics = self.db.query(Analytics).filter(
            Analytics.location_id == location_id,
            Analytics.date >= start_date,
            Analytics.date <= end_date,
        ).all()

        # Calculate trends
        total_reviews = 0
        total_rating = 0
        reviews_by_week = {}
        sentiment_breakdown = {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
        }

        for a in analytics:
            reviews = int(_analytics_review_value(a, "new_reviews"))
            avg_rating = _analytics_review_value(a, "avg_rating")
            total_reviews += reviews
            total_rating += avg_rating * reviews if reviews else 0

            # Weekly breakdown
            week = a.date.isocalendar()[1]
            if week not in reviews_by_week:
                reviews_by_week[week] = 0
            reviews_by_week[week] += reviews

        avg_rating = total_rating / total_reviews if total_reviews else 0

        # Calculate growth rate
        weeks = sorted(reviews_by_week.keys())
        growth_rate = 0
        if len(weeks) >= 2:
            first_week = reviews_by_week[weeks[0]]
            last_week = reviews_by_week[weeks[-1]]
            if first_week > 0:
                growth_rate = ((last_week - first_week) / first_week) * 100

        return {
            "period_days": days,
            "total_reviews": total_reviews,
            "average_rating": round(avg_rating, 2),
            "reviews_by_week": reviews_by_week,
            "sentiment_breakdown": sentiment_breakdown,
            "growth_rate": round(growth_rate, 1),
            "projected_monthly": int(total_reviews * (30 / days)) if days < 30 else total_reviews,
        }

    def _get_google_review_link(self, location) -> str:
        """Generate Google review link for a location."""
        # If we have place_id, use it
        place_id = getattr(location, 'google_place_id', None)
        if place_id:
            return f"https://search.google.com/local/writereview?placeid={place_id}"

        # Fallback to search-based link
        name = location.name.replace(" ", "+")
        address = (location.address or "").replace(" ", "+")
        return f"https://www.google.com/search?q={name}+{address}"

    async def _send_sms(self, phone: str, message: str) -> dict:
        """Send SMS via Twilio."""
        from app.services.notification import NotificationService
        service = NotificationService(self.db)
        return await service.send_sms(phone, message)

    async def _send_email(self, email: str, subject: str, body: str) -> dict:
        """Send email."""
        from app.services.notification import NotificationService
        service = NotificationService(self.db)
        
        # Wrap body in HTML template
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                {body}
            </div>
        </body>
        </html>
        """
        
        return await service.send_email(email, subject, html_body, body)

    async def _handle_negative_review(
        self,
        location_id: UUID,
        review_data: dict,
    ) -> dict[str, Any]:
        """Handle negative review with internal follow-up."""
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return {"success": False, "error": "Location not found"}

        # Log for internal handling
        logger.warning(
            f"Negative review received for {location.name}: "
            f"Rating {review_data.get('rating')}, "
            f"Reviewer: {review_data.get('reviewer_name')}"
        )

        await self._notify_negative_review(location, review_data)

        return {
            "success": True,
            "action": "internal_handling",
            "message": "Negative review flagged for internal follow-up",
        }

    async def _handle_positive_review(
        self,
        location_id: UUID,
        review_data: dict,
    ) -> dict[str, Any]:
        """Handle positive review - thank and encourage."""
        return {
            "success": True,
            "action": "positive_acknowledged",
            "message": "Positive review received",
        }

    async def _notify_negative_review(self, location, review_data: dict[str, Any]) -> None:
        """Create an actionable owner alert for negative review follow-up."""
        from app.services.notification import NotificationService

        rating = review_data.get("rating")
        reviewer_name = review_data.get("reviewer_name") or "Customer"
        review_text = (review_data.get("review_text") or "").strip()
        preview = review_text[:160]
        if review_text and len(review_text) > 160:
            preview = f"{preview}..."

        title = f"Negative review needs follow-up for {location.name}"
        message_lines = [
            f"Reviewer: {reviewer_name}",
            f"Rating: {rating if rating is not None else 'Not recorded'}",
        ]
        if preview:
            message_lines.append(f"Review: {preview}")
        message_lines.append("Open the reviews workflow and follow up with the customer.")

        await NotificationService(self.db).send_notification(
            account_id=location.account_id,
            title=title,
            message="\n".join(message_lines),
            notification_type="review_booster_negative_review",
            data={
                "location_id": str(location.id),
                "url": f"/dashboard/reviews?locationId={location.id}",
                "rating": rating,
                "reviewer_name": reviewer_name,
            },
        )

    async def _log_review_request(
        self,
        location_id: UUID,
        customer_name: str,
        customer_email: str | None,
        customer_phone: str | None,
        channel: ReviewRequestChannel,
        results: dict,
    ) -> None:
        """Log review request for analytics."""
        logger.info(
            f"Review request sent: location={location_id}, "
            f"customer={customer_name}, channel={channel.value}, "
            f"results={results}"
        )
