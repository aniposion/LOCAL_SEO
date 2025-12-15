"""Analytics collection service."""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.integrations.gbp import GBPClient
from app.integrations.instagram import InstagramClient
from app.models.analytics import Analytics
from app.models.channel import Channel, ChannelType
from app.models.location import Location


class AnalyticsService:
    """Service for collecting analytics from platforms."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def collect_all(self) -> dict:
        """Collect analytics for all active locations."""
        results = {"success": 0, "failed": 0, "errors": []}

        # Get all locations with active channels
        locations = self.db.query(Location).all()

        for location in locations:
            try:
                await self.collect_for_location(location.id)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"location_id": str(location.id), "error": str(e)})

        return results

    async def collect_for_location(self, location_id: UUID) -> None:
        """Collect analytics for a specific location."""
        channels = (
            self.db.query(Channel)
            .filter(Channel.location_id == location_id, Channel.is_active == True)
            .all()
        )

        for channel in channels:
            if not channel.credentials:
                continue

            try:
                if channel.type == ChannelType.GBP:
                    await self._collect_gbp(location_id, channel)
                elif channel.type == ChannelType.INSTAGRAM:
                    await self._collect_instagram(location_id, channel)
            except Exception as e:
                # Log error but continue with other channels
                channel.error_message = str(e)
                self.db.commit()

    async def _collect_gbp(self, location_id: UUID, channel: Channel) -> None:
        """Collect GBP analytics."""
        client = GBPClient(channel.credentials)

        # Get metrics for yesterday (most recent complete day)
        yesterday = date.today() - timedelta(days=1)
        metrics = await client.get_metrics(
            start_date=yesterday,
            end_date=yesterday,
        )

        for day_metrics in metrics:
            # Check if we already have data for this date
            existing = (
                self.db.query(Analytics)
                .filter(
                    Analytics.location_id == location_id,
                    Analytics.platform == "GBP",
                    Analytics.date == day_metrics.get("date", yesterday),
                )
                .first()
            )

            if existing:
                # Update existing record
                existing.impressions = day_metrics.get("impressions")
                existing.clicks = day_metrics.get("clicks")
                existing.calls = day_metrics.get("calls")
                existing.direction_requests = day_metrics.get("direction_requests")
                existing.source_raw = day_metrics
            else:
                # Create new record
                analytics = Analytics(
                    location_id=location_id,
                    platform="GBP",
                    date=day_metrics.get("date", yesterday),
                    impressions=day_metrics.get("impressions"),
                    clicks=day_metrics.get("clicks"),
                    calls=day_metrics.get("calls"),
                    direction_requests=day_metrics.get("direction_requests"),
                    source_raw=day_metrics,
                )
                self.db.add(analytics)

        channel.last_sync_at = datetime.now(timezone.utc).isoformat()
        channel.error_message = None
        self.db.commit()

    async def _collect_instagram(self, location_id: UUID, channel: Channel) -> None:
        """Collect Instagram analytics."""
        client = InstagramClient(channel.credentials)

        # Get insights for yesterday
        yesterday = date.today() - timedelta(days=1)
        insights = await client.get_insights(
            start_date=yesterday,
            end_date=yesterday,
        )

        for day_insights in insights:
            existing = (
                self.db.query(Analytics)
                .filter(
                    Analytics.location_id == location_id,
                    Analytics.platform == "INSTAGRAM",
                    Analytics.date == day_insights.get("date", yesterday),
                )
                .first()
            )

            if existing:
                existing.reach = day_insights.get("reach")
                existing.likes = day_insights.get("likes")
                existing.comments = day_insights.get("comments")
                existing.shares = day_insights.get("shares")
                existing.saves = day_insights.get("saves")
                existing.source_raw = day_insights
            else:
                analytics = Analytics(
                    location_id=location_id,
                    platform="INSTAGRAM",
                    date=day_insights.get("date", yesterday),
                    reach=day_insights.get("reach"),
                    likes=day_insights.get("likes"),
                    comments=day_insights.get("comments"),
                    shares=day_insights.get("shares"),
                    saves=day_insights.get("saves"),
                    source_raw=day_insights,
                )
                self.db.add(analytics)

        channel.last_sync_at = datetime.now(timezone.utc).isoformat()
        channel.error_message = None
        self.db.commit()
