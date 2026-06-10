"""P1: Metrics & Attribution service."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.time import utc_now_aware
from app.models.location import Location
from app.models.metrics import MetricSnapshot, SnapshotType, UTMLink, WeeklyReport
from app.models.post import Post, PostStatus
from app.schemas.metrics import (
    ChartDataPoint,
    DashboardHighlight,
    DashboardMetrics,
    DashboardResponse,
    MetricDelta,
    MetricSnapshotCreate,
    TopPost,
    WeeklyReportSummary,
)


class MetricsService:
    """Service for metrics and attribution."""

    def __init__(self, db: Session):
        self.db = db

    def get_snapshot(self, snapshot_id: UUID) -> Optional[MetricSnapshot]:
        """Get snapshot by ID."""
        result = self.db.execute(
            select(MetricSnapshot).where(MetricSnapshot.id == snapshot_id)
        )
        return result.scalar_one_or_none()

    def get_snapshots(
        self,
        location_id: UUID,
        snapshot_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 30,
    ) -> list[MetricSnapshot]:
        """Get snapshots for location."""
        query = select(MetricSnapshot).where(MetricSnapshot.location_id == location_id)

        if snapshot_type:
            query = query.where(MetricSnapshot.snapshot_type == SnapshotType(snapshot_type))
        if start_date:
            query = query.where(MetricSnapshot.snapshot_date >= start_date)
        if end_date:
            query = query.where(MetricSnapshot.snapshot_date <= end_date)

        query = query.order_by(MetricSnapshot.snapshot_date.desc()).limit(limit)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_previous_snapshot(
        self,
        location_id: UUID,
        current_date: date,
        snapshot_type: str = "daily",
    ) -> Optional[MetricSnapshot]:
        """Get previous period snapshot for delta calculation."""
        if snapshot_type == "daily":
            prev_date = current_date - timedelta(days=1)
        elif snapshot_type == "weekly":
            prev_date = current_date - timedelta(weeks=1)
        else:
            prev_date = current_date - timedelta(days=30)

        result = self.db.execute(
            select(MetricSnapshot).where(
                and_(
                    MetricSnapshot.location_id == location_id,
                    MetricSnapshot.snapshot_date == prev_date,
                    MetricSnapshot.snapshot_type == SnapshotType(snapshot_type),
                )
            )
        )
        return result.scalar_one_or_none()

    def get_latest_snapshot_before(
        self,
        location_id: UUID,
        before_date: date,
        snapshot_type: str = "daily",
    ) -> Optional[MetricSnapshot]:
        """Get the latest snapshot before a given date."""
        result = self.db.execute(
            select(MetricSnapshot)
            .where(
                and_(
                    MetricSnapshot.location_id == location_id,
                    MetricSnapshot.snapshot_date <= before_date,
                    MetricSnapshot.snapshot_type == SnapshotType(snapshot_type),
                )
            )
            .order_by(MetricSnapshot.snapshot_date.desc(), MetricSnapshot.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def create_snapshot(
        self,
        data: MetricSnapshotCreate,
        raw_data: Optional[dict] = None,
    ) -> MetricSnapshot:
        """Create new metric snapshot."""
        previous = self.get_previous_snapshot(
            data.location_id, data.snapshot_date, data.snapshot_type
        )

        post_ids = self._get_attributed_posts(
            data.location_id, data.snapshot_date, data.snapshot_type
        )

        snapshot = MetricSnapshot(
            location_id=data.location_id,
            snapshot_date=data.snapshot_date,
            snapshot_type=SnapshotType(data.snapshot_type),
            calls=data.calls,
            directions=data.directions,
            website_clicks=data.website_clicks,
            profile_views=data.profile_views,
            photo_views=data.photo_views,
            total_reviews=data.total_reviews,
            new_reviews=data.new_reviews,
            avg_rating=data.avg_rating,
            call_value=data.call_value,
            attributed_post_ids=post_ids,
            raw_data=raw_data,
        )

        if previous:
            snapshot.calls_delta = data.calls - previous.calls
            snapshot.directions_delta = data.directions - previous.directions
            snapshot.website_clicks_delta = data.website_clicks - previous.website_clicks

        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def _get_attributed_posts(
        self,
        location_id: UUID,
        end_date: date,
        snapshot_type: str,
    ) -> list[UUID]:
        """Get posts published in the snapshot period."""
        if snapshot_type == "daily":
            start_date = end_date
        elif snapshot_type == "weekly":
            start_date = end_date - timedelta(days=6)
        else:
            start_date = end_date - timedelta(days=29)

        result = self.db.execute(
            select(Post.id).where(
                and_(
                    Post.location_id == location_id,
                    Post.status == PostStatus.POSTED,
                    func.date(Post.posted_at) >= start_date,
                    func.date(Post.posted_at) <= end_date,
                )
            )
        )
        return [row[0] for row in result.all()]

    def get_dashboard(
        self,
        location_id: UUID,
        period_days: int = 7,
    ) -> DashboardResponse:
        """Get dashboard data for location."""
        today = date.today()
        period_end = today
        period_start = today - timedelta(days=period_days - 1)
        prev_period_start = period_start - timedelta(days=period_days)
        prev_period_end = period_start - timedelta(days=1)

        current_snapshots = self.get_snapshots(location_id, "daily", period_start, period_end)
        prev_snapshots = self.get_snapshots(location_id, "daily", prev_period_start, prev_period_end)

        current = self._aggregate_snapshots(current_snapshots)
        previous = self._aggregate_snapshots(prev_snapshots)

        metrics = DashboardMetrics(
            calls=self._calc_delta(current.get("calls", 0), previous.get("calls", 0)),
            directions=self._calc_delta(current.get("directions", 0), previous.get("directions", 0)),
            website_clicks=self._calc_delta(current.get("website_clicks", 0), previous.get("website_clicks", 0)),
            profile_views=self._calc_delta(current.get("profile_views", 0), previous.get("profile_views", 0)),
            new_reviews=self._calc_delta(current.get("new_reviews", 0), previous.get("new_reviews", 0)),
            avg_rating=current.get("avg_rating"),
            estimated_revenue=Decimal(current.get("calls", 0)) * Decimal("50.00"),
        )

        highlights = self._generate_highlights(metrics)
        top_posts = self._get_top_posts(location_id, period_start, period_end)
        chart_data = self._generate_chart_data(current_snapshots)

        return DashboardResponse(
            location_id=location_id,
            period_start=period_start,
            period_end=period_end,
            metrics=metrics,
            highlights=highlights,
            top_posts=top_posts,
            chart_data=chart_data,
        )

    def _aggregate_snapshots(self, snapshots: list[MetricSnapshot]) -> dict:
        """Aggregate multiple snapshots."""
        if not snapshots:
            return {}

        return {
            "calls": sum(s.calls for s in snapshots),
            "directions": sum(s.directions for s in snapshots),
            "website_clicks": sum(s.website_clicks for s in snapshots),
            "profile_views": sum(s.profile_views for s in snapshots),
            "new_reviews": sum(s.new_reviews for s in snapshots),
            "avg_rating": snapshots[-1].avg_rating if snapshots else None,
        }

    def _calc_delta(self, current: int, previous: int) -> MetricDelta:
        """Calculate delta between periods."""
        delta = current - previous
        percent = ((delta / previous) * 100) if previous > 0 else 0.0
        return MetricDelta(
            current=current,
            previous=previous,
            delta=delta,
            percent_change=round(percent, 1),
        )

    def _generate_highlights(self, metrics: DashboardMetrics) -> list[DashboardHighlight]:
        """Generate dashboard highlights."""
        highlights = []

        if metrics.calls.delta > 0:
            highlights.append(
                DashboardHighlight(
                    type="increase",
                    metric="calls",
                    message=f"Calls up by {metrics.calls.delta} ({metrics.calls.percent_change:+.1f}%)",
                    value=metrics.calls.delta,
                    percent=metrics.calls.percent_change,
                )
            )
        elif metrics.calls.delta < 0:
            highlights.append(
                DashboardHighlight(
                    type="decrease",
                    metric="calls",
                    message=f"Calls down by {abs(metrics.calls.delta)} ({metrics.calls.percent_change:.1f}%)",
                    value=metrics.calls.delta,
                    percent=metrics.calls.percent_change,
                )
            )

        if metrics.directions.delta > 0:
            highlights.append(
                DashboardHighlight(
                    type="increase",
                    metric="directions",
                    message=f"Direction requests up by {metrics.directions.delta} ({metrics.directions.percent_change:+.1f}%)",
                    value=metrics.directions.delta,
                    percent=metrics.directions.percent_change,
                )
            )

        if metrics.new_reviews.current > 0:
            highlights.append(
                DashboardHighlight(
                    type="milestone",
                    metric="reviews",
                    message=f"New reviews this period: {metrics.new_reviews.current}",
                    value=metrics.new_reviews.current,
                    percent=0,
                )
            )

        return highlights[:5]

    def _get_top_posts(
        self,
        location_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[TopPost]:
        """Get top contributing posts."""
        result = self.db.execute(
            select(Post)
            .where(
                and_(
                    Post.location_id == location_id,
                    Post.status == PostStatus.POSTED,
                    func.date(Post.posted_at) >= start_date,
                    func.date(Post.posted_at) <= end_date,
                )
            )
            .order_by(Post.posted_at.desc())
            .limit(5)
        )
        posts = result.scalars().all()

        return [
            TopPost(
                id=p.id,
                title=p.title or "Untitled",
                published_at=p.posted_at,
                platform=p.platform.value if p.platform else "unknown",
                estimated_impact="high" if i == 0 else "medium" if i < 3 else "low",
            )
            for i, p in enumerate(posts)
        ]

    def _generate_chart_data(
        self,
        snapshots: list[MetricSnapshot],
    ) -> list[ChartDataPoint]:
        """Generate chart data points."""
        return [
            ChartDataPoint(
                date=s.snapshot_date,
                calls=s.calls,
                directions=s.directions,
                website_clicks=s.website_clicks,
            )
            for s in sorted(snapshots, key=lambda x: x.snapshot_date)
        ]

    def get_reports(
        self,
        location_id: UUID,
        limit: int = 10,
    ) -> list[WeeklyReport]:
        """Get weekly reports for location."""
        result = self.db.execute(
            select(WeeklyReport)
            .where(WeeklyReport.location_id == location_id)
            .order_by(WeeklyReport.report_week.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def get_report(self, report_id: UUID) -> Optional[WeeklyReport]:
        """Get report by ID."""
        result = self.db.execute(select(WeeklyReport).where(WeeklyReport.id == report_id))
        return result.scalar_one_or_none()

    def generate_weekly_report(
        self,
        location_id: UUID,
        account_id: UUID,
        report_week: date,
    ) -> WeeklyReport:
        """Generate weekly report."""
        week_end = report_week + timedelta(days=6)

        current_snapshots = self.get_snapshots(location_id, "daily", report_week, week_end)

        prev_week_start = report_week - timedelta(days=7)
        prev_week_end = report_week - timedelta(days=1)
        prev_snapshots = self.get_snapshots(location_id, "daily", prev_week_start, prev_week_end)

        current = self._aggregate_snapshots(current_snapshots)
        previous = self._aggregate_snapshots(prev_snapshots)

        calls_delta = current.get("calls", 0) - previous.get("calls", 0)
        calls_percent = ((calls_delta / previous.get("calls", 1)) * 100) if previous.get("calls") else 0

        directions_delta = current.get("directions", 0) - previous.get("directions", 0)
        directions_percent = ((directions_delta / previous.get("directions", 1)) * 100) if previous.get("directions") else 0

        top_day = "Monday"
        if current_snapshots:
            top_snapshot = max(current_snapshots, key=lambda x: x.calls)
            top_day = top_snapshot.snapshot_date.strftime("%A")

        summary = WeeklyReportSummary(
            calls_total=current.get("calls", 0),
            calls_delta=calls_delta,
            calls_percent=round(calls_percent, 1),
            directions_total=current.get("directions", 0),
            directions_delta=directions_delta,
            directions_percent=round(directions_percent, 1),
            website_clicks_total=current.get("website_clicks", 0),
            new_reviews=current.get("new_reviews", 0),
            avg_rating=current.get("avg_rating"),
            estimated_revenue=Decimal(current.get("calls", 0)) * Decimal("50.00"),
            top_day=top_day,
            highlights=self._generate_report_highlights(current, previous),
        )

        weekly_snapshot = self._get_or_create_weekly_snapshot(location_id, report_week, current)

        report = WeeklyReport(
            location_id=location_id,
            account_id=account_id,
            report_week=report_week,
            current_snapshot_id=weekly_snapshot.id if weekly_snapshot else None,
            summary=summary.model_dump(mode="json"),
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def _generate_report_highlights(self, current: dict, previous: dict) -> list[str]:
        """Generate text highlights for report."""
        highlights = []

        calls_delta = current.get("calls", 0) - previous.get("calls", 0)
        if calls_delta > 0:
            highlights.append(f"Phone inquiries increased by {calls_delta}")

        directions_delta = current.get("directions", 0) - previous.get("directions", 0)
        if directions_delta > 0:
            highlights.append(f"Direction requests increased by {directions_delta}")

        if current.get("new_reviews", 0) > 0:
            highlights.append(f"Collected {current['new_reviews']} new reviews")

        return highlights

    def _get_or_create_weekly_snapshot(
        self,
        location_id: UUID,
        week_start: date,
        aggregated: dict,
    ) -> Optional[MetricSnapshot]:
        """Get or create weekly aggregated snapshot."""
        result = self.db.execute(
            select(MetricSnapshot).where(
                and_(
                    MetricSnapshot.location_id == location_id,
                    MetricSnapshot.snapshot_date == week_start,
                    MetricSnapshot.snapshot_type == SnapshotType.WEEKLY,
                )
            )
        )
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            snapshot = MetricSnapshot(
                location_id=location_id,
                snapshot_date=week_start,
                snapshot_type=SnapshotType.WEEKLY,
                calls=aggregated.get("calls", 0),
                directions=aggregated.get("directions", 0),
                website_clicks=aggregated.get("website_clicks", 0),
                profile_views=aggregated.get("profile_views", 0),
                new_reviews=aggregated.get("new_reviews", 0),
                avg_rating=aggregated.get("avg_rating"),
            )
            self.db.add(snapshot)
            self.db.flush()

        return snapshot

    def send_report(
        self,
        report_id: UUID,
        email_addresses: list[str],
    ) -> WeeklyReport:
        """Mark report as sent after successful delivery."""
        report = self.get_report(report_id)
        if report:
            report.sent_at = utc_now_aware()
            report.sent_to = email_addresses
            self.db.commit()
            self.db.refresh(report)
        return report

    def generate_utm_link(
        self,
        location_id: UUID,
        original_url: str,
        campaign: Optional[str] = None,
        post_id: Optional[UUID] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
    ) -> UTMLink:
        """Generate UTM tracked link."""
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        normalized_source = (utm_source or "gbp").strip().lower()
        normalized_medium = (utm_medium or "post").strip().lower()

        utm_params = {
            "utm_source": normalized_source,
            "utm_medium": normalized_medium,
        }
        if campaign:
            utm_params["utm_campaign"] = campaign
        if post_id:
            utm_params["utm_content"] = str(post_id)[:8]

        parsed = urlparse(original_url)
        existing_params = parse_qs(parsed.query)
        existing_params.update(utm_params)
        new_query = urlencode(existing_params, doseq=True)
        utm_url = urlunparse(parsed._replace(query=new_query))

        link = UTMLink(
            location_id=location_id,
            post_id=post_id,
            original_url=original_url,
            utm_url=utm_url,
            utm_source=normalized_source,
            utm_medium=normalized_medium,
            utm_campaign=campaign,
            utm_content=str(post_id)[:8] if post_id else None,
        )

        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link

    def get_utm_stats(self, location_id: UUID) -> dict:
        """Get UTM link statistics."""
        result = self.db.execute(
            select(UTMLink)
            .where(UTMLink.location_id == location_id)
            .order_by(UTMLink.created_at.desc())
            .limit(50)
        )
        links = list(result.scalars().all())

        return {
            "total_links": len(links),
            "total_clicks": sum(l.clicks for l in links),
            "links": links,
        }

    def delete_utm_link(self, link_id: UUID, location_id: UUID) -> bool:
        """Delete one UTM link for a location."""
        result = self.db.execute(
            select(UTMLink).where(
                UTMLink.id == link_id,
                UTMLink.location_id == location_id,
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            return False

        self.db.delete(link)
        self.db.commit()
        return True


def get_metrics_service(db: Session) -> MetricsService:
    """Get metrics service instance."""
    return MetricsService(db)
