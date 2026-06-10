"""Reporting service for generating PDF reports."""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.analytics import Analytics
from app.models.location import Location
from app.models.post import Post, PostStatus
from app.models.report import Report
from app.models.seo_score import SEOScore
from app.services.notification import NotificationService
from app.services.storage import get_storage_service


class ReportingUnavailableError(RuntimeError):
    """Raised when report delivery dependencies are not configured."""


class ReportingDeliveryError(RuntimeError):
    """Raised when report upload or delivery fails after configuration exists."""


class ReportingService:
    """Service for generating and sending reports."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = get_storage_service()
        self.notification_service = NotificationService(db)

    async def generate_weekly_report(
        self,
        location_id: UUID,
        send_email: bool = True,
    ) -> Report:
        """Generate a weekly PDF report for a location."""
        period_start, period_end = self._previous_week_period()
        return await self._generate_period_report(
            location_id=location_id,
            period_start=period_start,
            period_end=period_end,
            send_email=send_email,
            report_label="Weekly",
        )

    async def generate_monthly_report(
        self,
        location_id: UUID,
        send_email: bool = True,
    ) -> Report:
        """Generate a monthly PDF report for a location."""
        period_start, period_end = self._previous_month_period()
        return await self._generate_period_report(
            location_id=location_id,
            period_start=period_start,
            period_end=period_end,
            send_email=send_email,
            report_label="Monthly",
        )

    def _previous_week_period(self) -> tuple[date, date]:
        """Return the previous fully completed Monday-Sunday window."""
        today = date.today()
        period_end = today - timedelta(days=today.weekday() + 1)
        period_start = period_end - timedelta(days=6)
        return period_start, period_end

    def _previous_month_period(self) -> tuple[date, date]:
        """Return the previous fully completed calendar month."""
        today = date.today()
        current_month_start = date(today.year, today.month, 1)
        period_end = current_month_start - timedelta(days=1)
        period_start = date(period_end.year, period_end.month, 1)
        return period_start, period_end

    async def _generate_period_report(
        self,
        *,
        location_id: UUID,
        period_start: date,
        period_end: date,
        send_email: bool,
        report_label: str,
    ) -> Report:
        """Generate and optionally email a report for an explicit period."""

        # Get location
        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            raise ValueError("Location not found")

        # Gather data
        summary = await self._gather_report_data(location_id, period_start, period_end)

        # Generate PDF
        pdf_content = await self._generate_pdf(
            location,
            period_start,
            period_end,
            summary,
            report_label=report_label,
        )

        if not self.storage.is_configured():
            raise ReportingUnavailableError(
                "Cloud storage must be configured for weekly report uploads."
            )

        # Upload report to the configured cloud storage provider
        file_key = f"reports/{location_id}/{period_start.isoformat()}-{period_end.isoformat()}.pdf"
        try:
            file_url = self.storage.upload_file(
                pdf_content,
                filename=f"{period_start.isoformat()}-{period_end.isoformat()}.pdf",
                content_type="application/pdf",
                object_name=file_key,
            )
        except Exception as exc:
            raise ReportingDeliveryError(str(exc)) from exc

        # Create report record
        report = Report(
            location_id=location_id,
            period_start=period_start,
            period_end=period_end,
            file_url=file_url,
            summary=summary,
        )
        self.db.add(report)

        # Send email if requested
        if send_email:
            account = self.db.query(Account).filter(Account.id == location.account_id).first()
            if not account or not account.email:
                raise ReportingUnavailableError(
                    "Report email delivery requires a location owner email address."
                )

            await self._send_report_email(
                to_email=account.email,
                location_name=location.name,
                period_start=period_start,
                period_end=period_end,
                file_url=file_url,
                summary=summary,
                report_label=report_label,
            )
            report.email_sent = True
            report.email_sent_at = datetime.now(timezone.utc).isoformat()

        self.db.commit()
        self.db.refresh(report)

        return report

    async def _gather_report_data(
        self,
        location_id: UUID,
        period_start: date,
        period_end: date,
    ) -> dict:
        """Gather all data needed for the report."""
        # Analytics summary
        analytics = (
            self.db.query(Analytics)
            .filter(
                Analytics.location_id == location_id,
                Analytics.date >= period_start,
                Analytics.date <= period_end,
            )
            .all()
        )

        kpi_cards = {
            "gbp": {"impressions": 0, "clicks": 0, "calls": 0, "directions": 0},
            "instagram": {"reach": 0, "likes": 0, "comments": 0},
            "website": {"views": 0, "visitors": 0},
        }

        for a in analytics:
            if a.platform == "GBP":
                kpi_cards["gbp"]["impressions"] += a.impressions or 0
                kpi_cards["gbp"]["clicks"] += a.clicks or 0
                kpi_cards["gbp"]["calls"] += a.calls or 0
                kpi_cards["gbp"]["directions"] += a.direction_requests or 0
            elif a.platform == "INSTAGRAM":
                kpi_cards["instagram"]["reach"] += a.reach or 0
                kpi_cards["instagram"]["likes"] += a.likes or 0
                kpi_cards["instagram"]["comments"] += a.comments or 0
            elif a.platform == "WEBSITE":
                kpi_cards["website"]["views"] += a.page_views or 0
                kpi_cards["website"]["visitors"] += a.unique_visitors or 0

        # Top posts
        top_posts = (
            self.db.query(Post)
            .filter(
                Post.location_id == location_id,
                Post.status == PostStatus.POSTED,
                Post.posted_at >= datetime.combine(period_start, datetime.min.time()).replace(tzinfo=timezone.utc),
                Post.posted_at <= datetime.combine(period_end, datetime.max.time()).replace(tzinfo=timezone.utc),
            )
            .order_by(Post.posted_at.desc())
            .limit(5)
            .all()
        )

        top_posts_data = [
            {
                "platform": p.platform.value,
                "title": p.title,
                "posted_at": p.posted_at.isoformat() if p.posted_at else None,
            }
            for p in top_posts
        ]

        # Latest SEO score
        latest_score = (
            self.db.query(SEOScore)
            .filter(SEOScore.location_id == location_id)
            .order_by(SEOScore.date.desc())
            .first()
        )

        # Generate next actions
        next_actions = self._generate_next_actions(kpi_cards, latest_score)

        return {
            "kpi_cards": kpi_cards,
            "top_posts": top_posts_data,
            "seo_score": latest_score.score if latest_score else None,
            "next_actions": next_actions,
        }

    def _generate_next_actions(self, kpi_cards: dict, seo_score: SEOScore | None) -> list[str]:
        """Generate recommended next actions."""
        actions = []

        # Check GBP performance
        if kpi_cards["gbp"]["impressions"] < 100:
            actions.append("Increase GBP posting frequency to improve visibility")
        if kpi_cards["gbp"]["clicks"] > 0 and kpi_cards["gbp"]["calls"] == 0:
            actions.append("Add clear call-to-action in GBP posts to drive calls")

        # Check Instagram performance
        if kpi_cards["instagram"]["reach"] < 50:
            actions.append("Use more relevant hashtags to increase Instagram reach")
        if kpi_cards["instagram"]["reach"] > 0:
            engagement_rate = (kpi_cards["instagram"]["likes"] + kpi_cards["instagram"]["comments"]) / kpi_cards["instagram"]["reach"]
            if engagement_rate < 0.03:
                actions.append("Create more engaging Instagram content to boost interaction")

        # Check website
        if kpi_cards["website"]["views"] < 10:
            actions.append("Publish more blog content to drive website traffic")

        # SEO score based
        if seo_score and seo_score.score < 50:
            actions.append("Focus on consistent posting across all platforms")

        if not actions:
            actions.append("Maintain current posting schedule and monitor performance")

        return actions[:5]  # Limit to 5 actions

    async def _generate_pdf(
        self,
        location: Location,
        period_start: date,
        period_end: date,
        summary: dict,
        *,
        report_label: str,
    ) -> bytes:
        """Generate PDF report from HTML template."""
        # For MVP, generate simple HTML and convert to PDF
        # In production, use WeasyPrint or similar
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{report_label} SEO Report - {location.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                .kpi-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }}
                .kpi-card {{ background: #f5f5f5; padding: 20px; border-radius: 8px; }}
                .kpi-value {{ font-size: 24px; font-weight: bold; color: #2196F3; }}
                .actions {{ background: #e3f2fd; padding: 20px; border-radius: 8px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <h1>{report_label} SEO Report</h1>
            <h2>{location.name}</h2>
            <p>Period: {period_start.isoformat()} to {period_end.isoformat()}</p>
            
            <div class="kpi-grid">
                <div class="kpi-card">
                    <h3>Google Business</h3>
                    <p>Impressions: <span class="kpi-value">{summary['kpi_cards']['gbp']['impressions']}</span></p>
                    <p>Clicks: {summary['kpi_cards']['gbp']['clicks']}</p>
                    <p>Calls: {summary['kpi_cards']['gbp']['calls']}</p>
                </div>
                <div class="kpi-card">
                    <h3>Instagram</h3>
                    <p>Reach: <span class="kpi-value">{summary['kpi_cards']['instagram']['reach']}</span></p>
                    <p>Likes: {summary['kpi_cards']['instagram']['likes']}</p>
                    <p>Comments: {summary['kpi_cards']['instagram']['comments']}</p>
                </div>
                <div class="kpi-card">
                    <h3>Website</h3>
                    <p>Views: <span class="kpi-value">{summary['kpi_cards']['website']['views']}</span></p>
                    <p>Visitors: {summary['kpi_cards']['website']['visitors']}</p>
                </div>
            </div>
            
            <div class="actions">
                <h3>Recommended Actions</h3>
                <ul>
                    {''.join(f'<li>{action}</li>' for action in summary['next_actions'])}
                </ul>
            </div>
        </body>
        </html>
        """

        # For MVP, return HTML as bytes (in production, convert to PDF)
        # You would use: from weasyprint import HTML; return HTML(string=html).write_pdf()
        return html.encode("utf-8")

    async def _send_report_email(
        self,
        to_email: str,
        location_name: str,
        period_start: date,
        period_end: date,
        file_url: str,
        summary: dict,
        *,
        report_label: str,
    ) -> None:
        """Send report email."""
        subject = (
            f"{report_label} SEO Report - {location_name} "
            f"({period_start.isoformat()} to {period_end.isoformat()})"
        )

        body = f"""
        Your {report_label.lower()} SEO report for {location_name} is ready!
        
        Period: {period_start.isoformat()} to {period_end.isoformat()}
        
        Key Highlights:
        - GBP Impressions: {summary['kpi_cards']['gbp']['impressions']}
        - Instagram Reach: {summary['kpi_cards']['instagram']['reach']}
        - Website Views: {summary['kpi_cards']['website']['views']}
        
        Download your full report: {file_url}
        
        Recommended Actions:
        {chr(10).join(f'- {action}' for action in summary['next_actions'])}
        """

        html_body = (
            f"<h2>{report_label} SEO Report</h2>"
            f"<p><strong>{location_name}</strong></p>"
            f"<p>Period: {period_start.isoformat()} to {period_end.isoformat()}</p>"
            f"<p><a href=\"{file_url}\">Download your full report</a></p>"
            "<ul>"
            f"<li>GBP Impressions: {summary['kpi_cards']['gbp']['impressions']}</li>"
            f"<li>Instagram Reach: {summary['kpi_cards']['instagram']['reach']}</li>"
            f"<li>Website Views: {summary['kpi_cards']['website']['views']}</li>"
            "</ul>"
            "<p>Recommended Actions:</p>"
            "<ul>"
            + "".join(f"<li>{action}</li>" for action in summary["next_actions"])
            + "</ul>"
        )

        result = await self.notification_service.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=body,
        )
        if result.get("success"):
            return

        error_message = str(result.get("error") or "Report email delivery failed").strip()
        lowered_error = error_message.lower()
        if "not configured" in lowered_error or "unavailable" in lowered_error:
            raise ReportingUnavailableError(error_message)
        raise ReportingDeliveryError(error_message)
