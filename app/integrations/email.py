"""Email integration for sending reports."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


class EmailClientUnavailableError(RuntimeError):
    """Raised when report email delivery is not configured."""


class EmailClientDeliveryError(RuntimeError):
    """Raised when report email delivery fails after configuration is present."""


class EmailClient:
    """Client for sending emails via SMTP."""

    def __init__(self) -> None:
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password
        self.from_email = settings.email_from

    async def send(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> None:
        """Send an email."""
        if not self.host:
            raise EmailClientUnavailableError("SMTP is not configured for report email delivery.")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to_email

        # Plain text version
        msg.attach(MIMEText(body, "plain"))

        # HTML version if provided
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        # Send email
        try:
            with smtplib.SMTP(self.host, self.port) as server:
                if self.user and self.password:
                    server.starttls()
                    server.login(self.user, self.password)
                server.sendmail(self.from_email, to_email, msg.as_string())
        except Exception as exc:
            raise EmailClientDeliveryError(str(exc)) from exc

    async def send_report(
        self,
        to_email: str,
        location_name: str,
        report_url: str,
        summary: dict,
    ) -> None:
        """Send a weekly report email."""
        subject = f"Weekly SEO Report - {location_name}"

        plain_body = f"""
Your weekly SEO report for {location_name} is ready!

Key Metrics:
- GBP Impressions: {summary.get('kpi_cards', {}).get('gbp', {}).get('impressions', 0)}
- Instagram Reach: {summary.get('kpi_cards', {}).get('instagram', {}).get('reach', 0)}
- Website Views: {summary.get('kpi_cards', {}).get('website', {}).get('views', 0)}

Download your full report: {report_url}

Recommended Actions:
{chr(10).join(f'- {action}' for action in summary.get('next_actions', []))}

Best regards,
Local SEO Optimizer Team
"""

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #2196F3; color: white; padding: 20px; text-align: center; }}
        .metrics {{ display: flex; justify-content: space-around; margin: 20px 0; }}
        .metric {{ text-align: center; padding: 15px; background: #f5f5f5; border-radius: 8px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2196F3; }}
        .actions {{ background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .btn {{ display: inline-block; background: #2196F3; color: white; padding: 12px 24px; 
                text-decoration: none; border-radius: 4px; margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Weekly SEO Report</h1>
            <p>{location_name}</p>
        </div>
        
        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{summary.get('kpi_cards', {}).get('gbp', {}).get('impressions', 0)}</div>
                <div>GBP Impressions</div>
            </div>
            <div class="metric">
                <div class="metric-value">{summary.get('kpi_cards', {}).get('instagram', {}).get('reach', 0)}</div>
                <div>IG Reach</div>
            </div>
            <div class="metric">
                <div class="metric-value">{summary.get('kpi_cards', {}).get('website', {}).get('views', 0)}</div>
                <div>Web Views</div>
            </div>
        </div>
        
        <p style="text-align: center;">
            <a href="{report_url}" class="btn">Download Full Report</a>
        </p>
        
        <div class="actions">
            <h3>Recommended Actions</h3>
            <ul>
                {''.join(f'<li>{action}</li>' for action in summary.get('next_actions', []))}
            </ul>
        </div>
        
        <p style="color: #666; font-size: 12px; text-align: center;">
            Local SEO Optimizer - Automated SEO for Local Businesses
        </p>
    </div>
</body>
</html>
"""

        await self.send(to_email, subject, plain_body, html_body)
