"""ROI calculation and analytics service."""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.calls import CallLog
from app.models.competitor import CompetitorAnalysis
from app.models.metrics import MetricSnapshot
from app.models.post import Post
from app.models.revenue import RevenueProfile
from app.models.review_response import ReviewResponse, ResponseStatus
from app.models.social_proof import SocialProofCard, SocialProofStatus
from app.models.subscription import PLAN_PRICES, Subscription, SubscriptionStatus
from app.schemas.analytics import ROIReport, TimeSeriesData

logger = logging.getLogger(__name__)


class ROIService:
    """Service for calculating ROI and business impact."""

    # Assumptions for ROI calculations
    HOURLY_RATE = 50.0  # Owner's time value per hour
    MINUTES_PER_REVIEW_RESPONSE = 5  # Manual response time
    MINUTES_PER_POST = 20  # Manual post creation time
    MINUTES_PER_COMPETITOR_ANALYSIS = 30  # Manual analysis time
    MINUTES_PER_SOCIAL_CARD = 15  # Manual card creation time

    def __init__(self, db: Session):
        """Initialize ROI service."""
        self.db = db

    def _safe_count(self, query_builder, label: str) -> int:
        """Return zero instead of breaking ROI when a partial model is inconsistent."""
        try:
            return query_builder() or 0
        except Exception as exc:
            self.db.rollback()
            logger.warning("ROI count skipped for %s: %s", label, exc)
            return 0

    def calculate_time_saved(
        self, location_id: UUID, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> dict[str, Any]:
        """
        Calculate time saved by automation.

        Args:
            location_id: Location ID
            start_date: Start date for calculation
            end_date: End date for calculation

        Returns:
            Time saved breakdown
        """
        # Default to current month
        if not end_date:
            end_date = utc_now_naive()
        if not start_date:
            start_date = datetime(end_date.year, end_date.month, 1)

        # Count automated review responses
        review_responses = self._safe_count(
            lambda: self.db.query(func.count(ReviewResponse.id))
            .filter(
                and_(
                    ReviewResponse.location_id == location_id,
                    ReviewResponse.status == ResponseStatus.PUBLISHED,
                    ReviewResponse.created_at >= start_date,
                    ReviewResponse.created_at <= end_date,
                )
            )
            .scalar(),
            "review_responses",
        )

        # Count automated posts
        automated_posts = self._safe_count(
            lambda: self.db.query(func.count(Post.id))
            .filter(
                and_(
                    Post.location_id == location_id,
                    Post.created_at >= start_date,
                    Post.created_at <= end_date,
                )
            )
            .scalar(),
            "posts",
        )

        # Count competitor analyses
        competitor_analyses = self._safe_count(
            lambda: self.db.query(func.count(CompetitorAnalysis.id))
            .filter(
                and_(
                    CompetitorAnalysis.location_id == location_id,
                    CompetitorAnalysis.created_at >= start_date,
                    CompetitorAnalysis.created_at <= end_date,
                )
            )
            .scalar(),
            "competitor_analyses",
        )

        # Count social proof cards
        social_cards = self._safe_count(
            lambda: self.db.query(func.count(SocialProofCard.id))
            .filter(
                and_(
                    SocialProofCard.location_id == location_id,
                    SocialProofCard.status.in_(
                        [SocialProofStatus.APPROVED, SocialProofStatus.PUBLISHED]
                    ),
                    SocialProofCard.created_at >= start_date,
                    SocialProofCard.created_at <= end_date,
                )
            )
            .scalar(),
            "social_cards",
        )

        # Calculate time saved
        review_time_saved = review_responses * self.MINUTES_PER_REVIEW_RESPONSE
        post_time_saved = automated_posts * self.MINUTES_PER_POST
        analysis_time_saved = competitor_analyses * self.MINUTES_PER_COMPETITOR_ANALYSIS
        social_card_time_saved = social_cards * self.MINUTES_PER_SOCIAL_CARD

        total_minutes_saved = (
            review_time_saved + post_time_saved + analysis_time_saved + social_card_time_saved
        )
        total_hours_saved = total_minutes_saved / 60

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "activities": {
                "review_responses": {
                    "count": review_responses,
                    "minutes_saved": review_time_saved,
                },
                "automated_posts": {
                    "count": automated_posts,
                    "minutes_saved": post_time_saved,
                },
                "competitor_analyses": {
                    "count": competitor_analyses,
                    "minutes_saved": analysis_time_saved,
                },
                "social_cards": {
                    "count": social_cards,
                    "minutes_saved": social_card_time_saved,
                },
            },
            "total_minutes_saved": total_minutes_saved,
            "total_hours_saved": round(total_hours_saved, 1),
        }

    def calculate_money_saved(self, time_saved_data: dict[str, Any]) -> dict[str, Any]:
        """
        Calculate money saved based on time saved.

        Args:
            time_saved_data: Time saved data from calculate_time_saved

        Returns:
            Money saved breakdown
        """
        hourly_rate = time_saved_data.get("hourly_value", self.HOURLY_RATE)
        total_hours = time_saved_data["total_hours_saved"]
        money_saved = total_hours * hourly_rate

        # Calculate per-activity value
        activities_value = {}
        for activity, data in time_saved_data["activities"].items():
            minutes = data["minutes_saved"]
            hours = minutes / 60
            value = hours * hourly_rate
            activities_value[activity] = {
                "count": data["count"],
                "hours_saved": round(hours, 1),
                "money_saved": round(value, 2),
            }

        return {
            "period": time_saved_data["period"],
            "hourly_rate": hourly_rate,
            "total_hours_saved": total_hours,
            "total_money_saved": round(money_saved, 2),
            "activities": activities_value,
        }

    def _get_revenue_profile(self, location_id: UUID) -> RevenueProfile | None:
        return (
            self.db.query(RevenueProfile)
            .filter(RevenueProfile.location_id == location_id)
            .first()
        )

    def _get_metric_totals(
        self,
        location_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, int]:
        """Aggregate metric snapshot totals for a reporting window."""
        row = (
            self.db.query(
                func.coalesce(func.sum(MetricSnapshot.calls), 0),
                func.coalesce(func.sum(MetricSnapshot.directions), 0),
                func.coalesce(func.sum(MetricSnapshot.website_clicks), 0),
                func.coalesce(func.sum(MetricSnapshot.new_reviews), 0),
            )
            .filter(
                and_(
                    MetricSnapshot.location_id == location_id,
                    MetricSnapshot.snapshot_date >= start_date.date(),
                    MetricSnapshot.snapshot_date <= end_date.date(),
                )
            )
            .first()
        )

        return {
            "calls": int(row[0] or 0),
            "directions": int(row[1] or 0),
            "website_clicks": int(row[2] or 0),
            "new_reviews": int(row[3] or 0),
        }

    def calculate_revenue_projection(
        self,
        location_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Estimate revenue contribution from calls using RevenueProfile inputs."""
        if not end_date:
            end_date = utc_now_naive()
        if not start_date:
            start_date = datetime(end_date.year, end_date.month, 1)

        profile = self._get_revenue_profile(location_id)
        average_order_value = float(profile.average_order_value) if profile else 150.0
        gross_margin_percent = float(profile.gross_margin_percent) if profile else 30.0
        call_to_booking_rate = float(profile.call_to_booking_rate) if profile else 35.0
        booking_to_visit_rate = float(profile.booking_to_visit_rate) if profile else 80.0
        visit_to_sale_rate = float(profile.visit_to_sale_rate) if profile else 90.0
        missed_call_recovery_rate = float(profile.missed_call_recovery_rate) if profile else 20.0
        review_to_conversion_lift_percent = (
            float(profile.review_to_conversion_lift_percent) if profile else 3.0
        )

        metric_totals = self._get_metric_totals(location_id, start_date, end_date)

        call_log_total = self._safe_count(
            lambda: self.db.query(func.count(CallLog.id))
            .filter(
                and_(
                    CallLog.location_id == location_id,
                    CallLog.created_at >= start_date,
                    CallLog.created_at <= end_date,
                )
            )
            .scalar(),
            "roi_total_calls",
        )
        total_calls = metric_totals["calls"] or call_log_total

        missed_calls = self._safe_count(
            lambda: self.db.query(func.count(CallLog.id))
            .filter(
                and_(
                    CallLog.location_id == location_id,
                    CallLog.call_status.in_(["no-answer", "busy"]),
                    CallLog.created_at >= start_date,
                    CallLog.created_at <= end_date,
                )
            )
            .scalar(),
            "roi_missed_calls",
        )
        directions = metric_totals["directions"]
        website_clicks = metric_totals["website_clicks"]
        new_reviews = metric_totals["new_reviews"]
        published_review_responses = self._safe_count(
            lambda: self.db.query(func.count(ReviewResponse.id))
            .filter(
                and_(
                    ReviewResponse.location_id == location_id,
                    ReviewResponse.status == ResponseStatus.PUBLISHED,
                    ReviewResponse.created_at >= start_date,
                    ReviewResponse.created_at <= end_date,
                )
            )
            .scalar(),
            "roi_published_review_responses",
        )

        estimated_bookings = round(total_calls * (call_to_booking_rate / 100))
        estimated_visits = round(estimated_bookings * (booking_to_visit_rate / 100))
        estimated_sales = round(estimated_visits * (visit_to_sale_rate / 100))
        estimated_revenue = round(estimated_sales * average_order_value, 2)
        estimated_gross_profit = round(estimated_revenue * (gross_margin_percent / 100), 2)

        recovered_calls = round(missed_calls * (missed_call_recovery_rate / 100))
        recovered_bookings = round(recovered_calls * (call_to_booking_rate / 100))
        recovered_visits = round(recovered_bookings * (booking_to_visit_rate / 100))
        recovered_sales = round(recovered_visits * (visit_to_sale_rate / 100))
        recovery_revenue = round(recovered_sales * average_order_value, 2)
        recovery_gross_profit = round(recovery_revenue * (gross_margin_percent / 100), 2)

        digital_intent_events = directions + website_clicks
        estimated_digital_visits = round(
            directions + (website_clicks * (booking_to_visit_rate / 100))
        )
        estimated_digital_sales = round(estimated_digital_visits * (visit_to_sale_rate / 100))
        estimated_digital_revenue = round(estimated_digital_sales * average_order_value, 2)

        review_activity_count = max(new_reviews, published_review_responses)
        review_uplift_revenue = 0.0
        review_uplift_gross_profit = 0.0
        if review_activity_count > 0 and review_to_conversion_lift_percent > 0:
            baseline_review_sensitive_revenue = estimated_revenue + estimated_digital_revenue
            review_uplift_revenue = round(
                baseline_review_sensitive_revenue * (review_to_conversion_lift_percent / 100),
                2,
            )
            review_uplift_gross_profit = round(
                review_uplift_revenue * (gross_margin_percent / 100), 2
            )

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "inputs": {
                "average_order_value": average_order_value,
                "gross_margin_percent": gross_margin_percent,
                "call_to_booking_rate": call_to_booking_rate,
                "booking_to_visit_rate": booking_to_visit_rate,
                "visit_to_sale_rate": visit_to_sale_rate,
                "missed_call_recovery_rate": missed_call_recovery_rate,
                "review_to_conversion_lift_percent": review_to_conversion_lift_percent,
            },
            "calls": {
                "total_calls": total_calls,
                "call_log_total": call_log_total,
                "missed_calls": missed_calls,
                "recovered_calls": recovered_calls,
            },
            "digital_intent": {
                "directions": directions,
                "website_clicks": website_clicks,
                "digital_intent_events": digital_intent_events,
                "estimated_digital_visits": estimated_digital_visits,
                "estimated_digital_sales": estimated_digital_sales,
                "estimated_digital_revenue": estimated_digital_revenue,
            },
            "reviews": {
                "new_reviews": new_reviews,
                "published_review_responses": published_review_responses,
                "review_activity_count": review_activity_count,
            },
            "estimated_bookings_from_calls": estimated_bookings,
            "estimated_visits_from_calls": estimated_visits,
            "estimated_sales_from_calls": estimated_sales,
            "estimated_revenue_from_calls": estimated_revenue,
            "estimated_gross_profit_from_calls": estimated_gross_profit,
            "missed_call_recovery_revenue": recovery_revenue,
            "missed_call_recovery_gross_profit": recovery_gross_profit,
            "review_uplift_revenue": review_uplift_revenue,
            "review_uplift_gross_profit": review_uplift_gross_profit,
        }

    def calculate_engagement_boost(
        self, location_id: UUID, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> dict[str, Any]:
        """
        Calculate engagement boost from AI features.

        Args:
            location_id: Location ID
            start_date: Start date for calculation
            end_date: End date for calculation

        Returns:
            Engagement metrics
        """
        # Default to current month
        if not end_date:
            end_date = utc_now_naive()
        if not start_date:
            start_date = datetime(end_date.year, end_date.month, 1)

        # Calculate previous period for comparison
        period_length = (end_date - start_date).days
        prev_start = start_date - timedelta(days=period_length)
        prev_end = start_date

        # Current period metrics
        current_reviews = self._safe_count(
            lambda: self.db.query(func.count(ReviewResponse.id))
            .filter(
                and_(
                    ReviewResponse.location_id == location_id,
                    ReviewResponse.created_at >= start_date,
                    ReviewResponse.created_at <= end_date,
                )
            )
            .scalar(),
            "current_reviews",
        )

        current_posts = self._safe_count(
            lambda: self.db.query(func.count(Post.id))
            .filter(
                and_(
                    Post.location_id == location_id,
                    Post.created_at >= start_date,
                    Post.created_at <= end_date,
                )
            )
            .scalar(),
            "current_posts",
        )

        # Previous period metrics
        prev_reviews = self._safe_count(
            lambda: self.db.query(func.count(ReviewResponse.id))
            .filter(
                and_(
                    ReviewResponse.location_id == location_id,
                    ReviewResponse.created_at >= prev_start,
                    ReviewResponse.created_at < prev_end,
                )
            )
            .scalar(),
            "previous_reviews",
        )

        prev_posts = self._safe_count(
            lambda: self.db.query(func.count(Post.id))
            .filter(
                and_(
                    Post.location_id == location_id,
                    Post.created_at >= prev_start,
                    Post.created_at < prev_end,
                )
            )
            .scalar(),
            "previous_posts",
        )

        # Calculate changes
        review_change = current_reviews - prev_reviews
        post_change = current_posts - prev_posts

        review_change_pct = (
            (review_change / prev_reviews * 100) if prev_reviews > 0 else 0
        )
        post_change_pct = (post_change / prev_posts * 100) if prev_posts > 0 else 0

        return {
            "period": {
                "current": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "previous": {
                    "start_date": prev_start.isoformat(),
                    "end_date": prev_end.isoformat(),
                },
            },
            "metrics": {
                "reviews": {
                    "current": current_reviews,
                    "previous": prev_reviews,
                    "change": review_change,
                    "change_percentage": round(review_change_pct, 1),
                },
                "posts": {
                    "current": current_posts,
                    "previous": prev_posts,
                    "change": post_change,
                    "change_percentage": round(post_change_pct, 1),
                },
            },
            "total_engagement_boost": round((review_change_pct + post_change_pct) / 2, 1),
        }

    def generate_roi_report(
        self, location_id: UUID, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> ROIReport:
        """
        Generate comprehensive ROI report.

        Args:
            location_id: Location ID
            start_date: Start date for report
            end_date: End date for report

        Returns:
            ROI report
        """
        # Calculate metrics
        time_saved = self.calculate_time_saved(location_id, start_date, end_date)
        profile = self._get_revenue_profile(location_id)
        hourly_value = float(profile.owner_hourly_value) if profile else self.HOURLY_RATE
        time_saved["hourly_value"] = hourly_value
        money_saved = self.calculate_money_saved(time_saved)
        engagement = self.calculate_engagement_boost(location_id, start_date, end_date)
        revenue_projection = self.calculate_revenue_projection(location_id, start_date, end_date)

        # Get location info
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == location_id).first()
        business_name = location.business_name if location else "Your Business"

        # Generate summary message
        hours_saved = time_saved["total_hours_saved"]
        money_value = money_saved["total_money_saved"]

        summary_message = (
            f"This month, {business_name} saved {hours_saved} hours "
            f"(worth ${money_value:,.2f}) using AI automation "
            f"and generated an estimated ${revenue_projection['estimated_revenue_from_calls']:,.2f} in call-driven revenue. "
        )

        if revenue_projection["review_uplift_revenue"] > 0:
            summary_message += (
                f"Review-driven conversion uplift added about "
                f"${revenue_projection['review_uplift_revenue']:,.2f} in incremental revenue. "
            )

        if engagement["total_engagement_boost"] > 0:
            summary_message += (
                f"Engagement increased by {engagement['total_engagement_boost']}% "
                f"compared to last month."
            )

        # Build detailed breakdown
        breakdown = {
            "time_saved": time_saved,
            "money_saved": money_saved,
            "engagement_boost": engagement,
        }
        

        subscription = (
            self.db.query(Subscription)
            .filter(
                and_(
                    Subscription.account_id == location.account_id,
                    Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]),
                )
            )
            .first()
        )

        subscription_cost = 0
        if subscription:
            subscription_cost = PLAN_PRICES.get(subscription.plan_type, 0)

        roi_percentage = (
            (
                (
                    money_value
                    + revenue_projection["estimated_gross_profit_from_calls"]
                    + revenue_projection["missed_call_recovery_gross_profit"]
                    + revenue_projection["review_uplift_gross_profit"]
                )
                - subscription_cost
            )
            / subscription_cost
            * 100
            if subscription_cost > 0
            else 0
        )

        return ROIReport(
            location_id=location_id,
            business_name=business_name,
            period_start=start_date or datetime(utc_now_naive().year, utc_now_naive().month, 1),
            period_end=end_date or utc_now_naive(),
            summary_message=summary_message,
            total_hours_saved=hours_saved,
            total_money_saved=money_value,
            hourly_value=hourly_value,
            subscription_cost=subscription_cost,
            roi_percentage=round(roi_percentage, 1),
            engagement_boost_percentage=engagement["total_engagement_boost"],
            breakdown=breakdown,
            revenue_projection=revenue_projection,
        )

    def get_time_series_data(
        self,
        location_id: UUID,
        metric: str,
        days_back: int = 30,
    ) -> TimeSeriesData:
        """
        Get time series data for a specific metric.

        Args:
            location_id: Location ID
            metric: Metric name (e.g., 'review_responses', 'posts', 'time_saved')
            days_back: Number of days to look back

        Returns:
            Time series data
        """
        end_date = utc_now_naive()
        start_date = end_date - timedelta(days=days_back)

        # Generate daily data points
        dates = []
        values = []

        current_date = start_date
        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)

            if metric == "review_responses":
                count = self._safe_count(
                    lambda: self.db.query(func.count(ReviewResponse.id))
                    .filter(
                        and_(
                            ReviewResponse.location_id == location_id,
                            ReviewResponse.created_at >= current_date,
                            ReviewResponse.created_at < next_date,
                        )
                    )
                    .scalar(),
                    "time_series_review_responses",
                )
            elif metric == "posts":
                count = self._safe_count(
                    lambda: self.db.query(func.count(Post.id))
                    .filter(
                        and_(
                            Post.location_id == location_id,
                            Post.created_at >= current_date,
                            Post.created_at < next_date,
                        )
                    )
                    .scalar(),
                    "time_series_posts",
                )
            elif metric == "time_saved":
                # Calculate daily time saved
                review_count = self._safe_count(
                    lambda: self.db.query(func.count(ReviewResponse.id))
                    .filter(
                        and_(
                            ReviewResponse.location_id == location_id,
                            ReviewResponse.status == ResponseStatus.PUBLISHED,
                            ReviewResponse.created_at >= current_date,
                            ReviewResponse.created_at < next_date,
                        )
                    )
                    .scalar(),
                    "time_series_time_saved_reviews",
                )
                post_count = self._safe_count(
                    lambda: self.db.query(func.count(Post.id))
                    .filter(
                        and_(
                            Post.location_id == location_id,
                            Post.created_at >= current_date,
                            Post.created_at < next_date,
                        )
                    )
                    .scalar(),
                    "time_series_time_saved_posts",
                )
                minutes_saved = (
                    review_count * self.MINUTES_PER_REVIEW_RESPONSE
                    + post_count * self.MINUTES_PER_POST
                )
                count = round(minutes_saved / 60, 1)  # Convert to hours
            else:
                count = 0

            dates.append(current_date.isoformat())
            values.append(count)

            current_date = next_date

        return TimeSeriesData(
            metric=metric,
            dates=dates,
            values=values,
            total=sum(values),
            average=round(sum(values) / len(values), 1) if values else 0,
        )
