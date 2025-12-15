"""Multi-location & Agency Mode - Team management and white-labeling."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings

logger = logging.getLogger(__name__)


class TeamRole(str, Enum):
    """Team member roles with different permission levels."""
    OWNER = "owner"           # Full access, billing, can delete
    ADMIN = "admin"           # Full access except billing
    MANAGER = "manager"       # Can manage content, view reports
    EDITOR = "editor"         # Can create/edit content, cannot publish
    VIEWER = "viewer"         # Read-only access


class Permission(str, Enum):
    """Granular permissions."""
    # Content
    CONTENT_CREATE = "content:create"
    CONTENT_EDIT = "content:edit"
    CONTENT_DELETE = "content:delete"
    CONTENT_PUBLISH = "content:publish"
    CONTENT_APPROVE = "content:approve"
    
    # Locations
    LOCATION_VIEW = "location:view"
    LOCATION_CREATE = "location:create"
    LOCATION_EDIT = "location:edit"
    LOCATION_DELETE = "location:delete"
    
    # Analytics
    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_EXPORT = "analytics:export"
    
    # Reports
    REPORT_VIEW = "report:view"
    REPORT_GENERATE = "report:generate"
    
    # Team
    TEAM_VIEW = "team:view"
    TEAM_MANAGE = "team:manage"
    
    # Billing
    BILLING_VIEW = "billing:view"
    BILLING_MANAGE = "billing:manage"
    
    # Settings
    SETTINGS_VIEW = "settings:view"
    SETTINGS_MANAGE = "settings:manage"
    
    # White Label
    WHITELABEL_MANAGE = "whitelabel:manage"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    TeamRole.OWNER: [p for p in Permission],  # All permissions
    TeamRole.ADMIN: [
        Permission.CONTENT_CREATE, Permission.CONTENT_EDIT, Permission.CONTENT_DELETE,
        Permission.CONTENT_PUBLISH, Permission.CONTENT_APPROVE,
        Permission.LOCATION_VIEW, Permission.LOCATION_CREATE, Permission.LOCATION_EDIT,
        Permission.ANALYTICS_VIEW, Permission.ANALYTICS_EXPORT,
        Permission.REPORT_VIEW, Permission.REPORT_GENERATE,
        Permission.TEAM_VIEW, Permission.TEAM_MANAGE,
        Permission.SETTINGS_VIEW, Permission.SETTINGS_MANAGE,
        Permission.WHITELABEL_MANAGE,
    ],
    TeamRole.MANAGER: [
        Permission.CONTENT_CREATE, Permission.CONTENT_EDIT,
        Permission.CONTENT_PUBLISH, Permission.CONTENT_APPROVE,
        Permission.LOCATION_VIEW,
        Permission.ANALYTICS_VIEW,
        Permission.REPORT_VIEW, Permission.REPORT_GENERATE,
        Permission.TEAM_VIEW,
        Permission.SETTINGS_VIEW,
    ],
    TeamRole.EDITOR: [
        Permission.CONTENT_CREATE, Permission.CONTENT_EDIT,
        Permission.LOCATION_VIEW,
        Permission.ANALYTICS_VIEW,
        Permission.REPORT_VIEW,
    ],
    TeamRole.VIEWER: [
        Permission.LOCATION_VIEW,
        Permission.ANALYTICS_VIEW,
        Permission.REPORT_VIEW,
    ],
}


class AgencyService:
    """
    Service for multi-location and agency management.
    
    Features:
    - 팀 계정 권한 관리
    - 화이트라벨링
    - 자동 리포트 대량 발송
    - Agency 전용 대시보드
    """

    def __init__(self, db: Session):
        self.db = db

    # ============ Team Management ============

    async def invite_team_member(
        self,
        agency_account_id: UUID,
        email: str,
        role: TeamRole,
        location_ids: list[UUID] | None = None,  # None = all locations
    ) -> dict[str, Any]:
        """
        Invite a new team member to the agency.
        """
        from app.models.account import Account
        import secrets

        # Check if agency has permission
        agency = self.db.query(Account).filter(Account.id == agency_account_id).first()
        if not agency:
            return {"success": False, "error": "Agency account not found"}

        # Check if user already exists
        existing = self.db.query(Account).filter(Account.email == email).first()

        # Generate invite token
        invite_token = secrets.token_urlsafe(32)
        invite_expires = datetime.now(timezone.utc) + timedelta(days=7)

        # Create team member record
        team_member = {
            "email": email,
            "role": role.value,
            "invited_by": str(agency_account_id),
            "invite_token": invite_token,
            "invite_expires": invite_expires.isoformat(),
            "location_ids": [str(lid) for lid in location_ids] if location_ids else None,
            "status": "pending",
        }

        # Store in agency's team_members (would be a separate table in production)
        # For now, we'll use account settings
        if not agency.settings:
            agency.settings = {}
        if "team_members" not in agency.settings:
            agency.settings["team_members"] = []

        agency.settings["team_members"].append(team_member)
        self.db.commit()

        # Send invite email
        await self._send_team_invite_email(
            email=email,
            agency_name=agency.company_name or agency.full_name or "Agency",
            role=role,
            invite_token=invite_token,
        )

        return {
            "success": True,
            "invite_token": invite_token,
            "expires": invite_expires.isoformat(),
            "message": f"Invitation sent to {email}",
        }

    async def accept_team_invite(
        self,
        invite_token: str,
        user_account_id: UUID,
    ) -> dict[str, Any]:
        """
        Accept a team invitation.
        """
        from app.models.account import Account

        # Find the agency with this invite
        accounts = self.db.query(Account).all()

        for account in accounts:
            if not account.settings or "team_members" not in account.settings:
                continue

            for member in account.settings["team_members"]:
                if member.get("invite_token") == invite_token:
                    # Check expiration
                    expires = datetime.fromisoformat(member["invite_expires"])
                    if datetime.now(timezone.utc) > expires:
                        return {"success": False, "error": "Invite has expired"}

                    # Update member status
                    member["status"] = "active"
                    member["account_id"] = str(user_account_id)
                    member["joined_at"] = datetime.now(timezone.utc).isoformat()
                    del member["invite_token"]
                    del member["invite_expires"]

                    self.db.commit()

                    return {
                        "success": True,
                        "agency_id": str(account.id),
                        "role": member["role"],
                        "message": "Successfully joined the team",
                    }

        return {"success": False, "error": "Invalid invite token"}

    async def get_team_members(
        self,
        agency_account_id: UUID,
    ) -> list[dict[str, Any]]:
        """
        Get all team members for an agency.
        """
        from app.models.account import Account

        agency = self.db.query(Account).filter(Account.id == agency_account_id).first()
        if not agency or not agency.settings:
            return []

        members = agency.settings.get("team_members", [])

        # Enrich with account details
        result = []
        for member in members:
            member_data = {
                "email": member.get("email"),
                "role": member.get("role"),
                "status": member.get("status"),
                "location_ids": member.get("location_ids"),
                "joined_at": member.get("joined_at"),
            }

            if member.get("account_id"):
                account = self.db.query(Account).filter(
                    Account.id == UUID(member["account_id"])
                ).first()
                if account:
                    member_data["name"] = account.full_name
                    member_data["last_login"] = account.last_login_at.isoformat() if account.last_login_at else None

            result.append(member_data)

        return result

    async def update_team_member_role(
        self,
        agency_account_id: UUID,
        member_email: str,
        new_role: TeamRole,
    ) -> dict[str, Any]:
        """
        Update a team member's role.
        """
        from app.models.account import Account

        agency = self.db.query(Account).filter(Account.id == agency_account_id).first()
        if not agency or not agency.settings:
            return {"success": False, "error": "Agency not found"}

        members = agency.settings.get("team_members", [])

        for member in members:
            if member.get("email") == member_email:
                member["role"] = new_role.value
                self.db.commit()
                return {"success": True, "message": f"Role updated to {new_role.value}"}

        return {"success": False, "error": "Team member not found"}

    async def remove_team_member(
        self,
        agency_account_id: UUID,
        member_email: str,
    ) -> dict[str, Any]:
        """
        Remove a team member from the agency.
        """
        from app.models.account import Account

        agency = self.db.query(Account).filter(Account.id == agency_account_id).first()
        if not agency or not agency.settings:
            return {"success": False, "error": "Agency not found"}

        members = agency.settings.get("team_members", [])
        agency.settings["team_members"] = [
            m for m in members if m.get("email") != member_email
        ]

        self.db.commit()
        return {"success": True, "message": f"Removed {member_email} from team"}

    def check_permission(
        self,
        user_role: TeamRole,
        required_permission: Permission,
    ) -> bool:
        """
        Check if a role has a specific permission.
        """
        role_perms = ROLE_PERMISSIONS.get(user_role, [])
        return required_permission in role_perms

    # ============ White Labeling ============

    async def update_white_label_settings(
        self,
        agency_account_id: UUID,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update white label settings for an agency.
        
        Settings:
        - brand_name: Custom brand name
        - logo_url: Custom logo URL
        - primary_color: Primary brand color
        - secondary_color: Secondary brand color
        - custom_domain: Custom domain for the dashboard
        - email_from_name: Custom sender name for emails
        - email_from_address: Custom sender email (requires verification)
        - footer_text: Custom footer text
        - hide_powered_by: Hide "Powered by Local SEO Optimizer"
        """
        from app.models.account import Account

        agency = self.db.query(Account).filter(Account.id == agency_account_id).first()
        if not agency:
            return {"success": False, "error": "Agency not found"}

        if not agency.settings:
            agency.settings = {}

        # Validate settings
        allowed_keys = [
            "brand_name", "logo_url", "primary_color", "secondary_color",
            "custom_domain", "email_from_name", "email_from_address",
            "footer_text", "hide_powered_by", "favicon_url",
        ]

        white_label = agency.settings.get("white_label", {})

        for key, value in settings.items():
            if key in allowed_keys:
                white_label[key] = value

        agency.settings["white_label"] = white_label
        self.db.commit()

        return {
            "success": True,
            "white_label": white_label,
        }

    async def get_white_label_settings(
        self,
        agency_account_id: UUID,
    ) -> dict[str, Any]:
        """
        Get white label settings for an agency.
        """
        from app.models.account import Account

        agency = self.db.query(Account).filter(Account.id == agency_account_id).first()
        if not agency or not agency.settings:
            return self._get_default_white_label()

        return agency.settings.get("white_label", self._get_default_white_label())

    def _get_default_white_label(self) -> dict[str, Any]:
        """Get default white label settings."""
        return {
            "brand_name": "Local SEO Optimizer",
            "logo_url": None,
            "primary_color": "#667eea",
            "secondary_color": "#764ba2",
            "custom_domain": None,
            "email_from_name": "Local SEO Optimizer",
            "footer_text": None,
            "hide_powered_by": False,
        }

    # ============ Bulk Reports ============

    async def send_bulk_reports(
        self,
        agency_account_id: UUID,
        location_ids: list[UUID] | None = None,  # None = all locations
        report_type: str = "weekly",
    ) -> dict[str, Any]:
        """
        Send reports for multiple locations at once.
        """
        from app.models.location import Location
        from app.services.reporting import ReportingService

        # Get locations
        query = self.db.query(Location).filter(
            Location.account_id == agency_account_id
        )

        if location_ids:
            query = query.filter(Location.id.in_(location_ids))

        locations = query.all()

        if not locations:
            return {"success": False, "error": "No locations found"}

        reporting_service = ReportingService(self.db)
        results = []
        success_count = 0
        fail_count = 0

        for location in locations:
            try:
                if report_type == "weekly":
                    await reporting_service.generate_weekly_report(
                        location_id=location.id,
                        send_email=True,
                    )
                else:
                    await reporting_service.generate_monthly_report(
                        location_id=location.id,
                        send_email=True,
                    )

                success_count += 1
                results.append({
                    "location_id": str(location.id),
                    "location_name": location.name,
                    "status": "sent",
                })

            except Exception as e:
                fail_count += 1
                results.append({
                    "location_id": str(location.id),
                    "location_name": location.name,
                    "status": "failed",
                    "error": str(e),
                })

        return {
            "success": True,
            "total": len(locations),
            "sent": success_count,
            "failed": fail_count,
            "details": results,
        }

    async def schedule_bulk_reports(
        self,
        agency_account_id: UUID,
        schedule: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Schedule automatic bulk reports.
        
        Schedule format:
        {
            "enabled": True,
            "frequency": "weekly",  # weekly, monthly
            "day_of_week": 0,  # 0=Monday, for weekly
            "day_of_month": 1,  # for monthly
            "time": "09:00",
            "timezone": "America/New_York",
            "location_ids": [...] or None for all
        }
        """
        from app.models.account import Account

        agency = self.db.query(Account).filter(Account.id == agency_account_id).first()
        if not agency:
            return {"success": False, "error": "Agency not found"}

        if not agency.settings:
            agency.settings = {}

        agency.settings["bulk_report_schedule"] = schedule
        self.db.commit()

        return {
            "success": True,
            "schedule": schedule,
        }

    # ============ Agency Dashboard ============

    async def get_agency_dashboard(
        self,
        agency_account_id: UUID,
    ) -> dict[str, Any]:
        """
        Get agency dashboard overview with all locations.
        """
        from app.models.location import Location
        from app.models.analytics import Analytics
        from app.models.post import Post, PostStatus
        from datetime import date

        # Get all locations
        locations = self.db.query(Location).filter(
            Location.account_id == agency_account_id
        ).all()

        if not locations:
            return {
                "total_locations": 0,
                "locations": [],
                "aggregate_metrics": {},
            }

        location_ids = [loc.id for loc in locations]

        # Get recent analytics
        today = date.today()
        week_ago = today - timedelta(days=7)

        analytics = self.db.query(Analytics).filter(
            Analytics.location_id.in_(location_ids),
            Analytics.date >= week_ago,
        ).all()

        # Aggregate metrics
        total_calls = 0
        total_directions = 0
        total_impressions = 0
        total_reviews = 0

        for a in analytics:
            if a.metrics:
                total_calls += a.metrics.get("calls", 0)
                total_directions += a.metrics.get("direction_requests", 0)
                total_impressions += a.metrics.get("impressions", 0)
                total_reviews += a.metrics.get("new_reviews", 0)

        # Get pending approvals
        pending_posts = self.db.query(Post).filter(
            Post.location_id.in_(location_ids),
            Post.status == PostStatus.PENDING_APPROVAL,
        ).count()

        # Build location summaries
        location_summaries = []
        for loc in locations:
            loc_analytics = [a for a in analytics if a.location_id == loc.id]

            loc_calls = sum(a.metrics.get("calls", 0) for a in loc_analytics if a.metrics)
            loc_directions = sum(a.metrics.get("direction_requests", 0) for a in loc_analytics if a.metrics)

            location_summaries.append({
                "id": str(loc.id),
                "name": loc.name,
                "address": loc.address,
                "calls_7d": loc_calls,
                "directions_7d": loc_directions,
                "status": "active",  # Could check for issues
            })

        # Sort by calls (most active first)
        location_summaries.sort(key=lambda x: x["calls_7d"], reverse=True)

        # Get team members count
        from app.models.account import Account
        agency = self.db.query(Account).filter(Account.id == agency_account_id).first()
        team_count = len(agency.settings.get("team_members", [])) if agency and agency.settings else 0

        return {
            "total_locations": len(locations),
            "team_members": team_count,
            "pending_approvals": pending_posts,
            "aggregate_metrics": {
                "calls_7d": total_calls,
                "directions_7d": total_directions,
                "impressions_7d": total_impressions,
                "new_reviews_7d": total_reviews,
            },
            "locations": location_summaries[:20],  # Top 20
            "white_label": await self.get_white_label_settings(agency_account_id),
        }

    async def get_location_comparison(
        self,
        agency_account_id: UUID,
        metric: str = "calls",
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Compare performance across all locations.
        """
        from app.models.location import Location
        from app.models.analytics import Analytics
        from datetime import date

        locations = self.db.query(Location).filter(
            Location.account_id == agency_account_id
        ).all()

        if not locations:
            return []

        today = date.today()
        start_date = today - timedelta(days=days)

        results = []

        for loc in locations:
            analytics = self.db.query(Analytics).filter(
                Analytics.location_id == loc.id,
                Analytics.date >= start_date,
            ).all()

            total = sum(
                a.metrics.get(metric, 0) for a in analytics if a.metrics
            )

            results.append({
                "location_id": str(loc.id),
                "location_name": loc.name,
                "metric": metric,
                "value": total,
                "period_days": days,
            })

        # Sort by value descending
        results.sort(key=lambda x: x["value"], reverse=True)

        # Add ranking
        for i, r in enumerate(results):
            r["rank"] = i + 1

        return results

    # ============ Helper Methods ============

    async def _send_team_invite_email(
        self,
        email: str,
        agency_name: str,
        role: TeamRole,
        invite_token: str,
    ) -> None:
        """Send team invitation email."""
        from app.services.notification import NotificationService

        invite_url = f"{settings.app_url}/invite/accept?token={invite_token}"

        subject = f"You've been invited to join {agency_name}"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .btn {{ display: inline-block; background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>You're Invited! 🎉</h1>
                <p>You've been invited to join <strong>{agency_name}</strong> as a <strong>{role.value.title()}</strong>.</p>
                
                <p>As a {role.value}, you'll be able to:</p>
                <ul>
                    {"".join(f"<li>{p.value.replace(':', ' ').replace('_', ' ').title()}</li>" for p in ROLE_PERMISSIONS.get(role, [])[:5])}
                </ul>
                
                <p><a href="{invite_url}" class="btn">Accept Invitation</a></p>
                
                <p style="color: #666; font-size: 14px;">This invitation expires in 7 days.</p>
            </div>
        </body>
        </html>
        """

        notification_service = NotificationService(self.db)
        await notification_service.send_email(email, subject, html_body)
