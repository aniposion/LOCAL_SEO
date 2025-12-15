"""Multi-location & Agency Mode router."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routers.deps import get_current_user
from app.models.account import Account, AccountRole
from app.services.agency import AgencyService, TeamRole, Permission

router = APIRouter(prefix="/agency", tags=["agency"])


# ============ Schemas ============

class TeamInviteRequest(BaseModel):
    """Request to invite a team member."""
    email: EmailStr
    role: str = Field(..., description="owner, admin, manager, editor, viewer")
    location_ids: list[UUID] | None = Field(
        default=None,
        description="Specific locations to grant access to. None = all locations",
    )


class TeamRoleUpdateRequest(BaseModel):
    """Request to update a team member's role."""
    email: EmailStr
    new_role: str


class WhiteLabelRequest(BaseModel):
    """Request to update white label settings."""
    brand_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    custom_domain: str | None = None
    email_from_name: str | None = None
    footer_text: str | None = None
    hide_powered_by: bool | None = None
    favicon_url: str | None = None


class BulkReportRequest(BaseModel):
    """Request to send bulk reports."""
    location_ids: list[UUID] | None = None
    report_type: str = Field(default="weekly", description="weekly or monthly")


class ReportScheduleRequest(BaseModel):
    """Request to schedule automatic reports."""
    enabled: bool = True
    frequency: str = Field(default="weekly", description="weekly or monthly")
    day_of_week: int | None = Field(default=0, ge=0, le=6, description="0=Monday")
    day_of_month: int | None = Field(default=1, ge=1, le=28)
    time: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")
    timezone: str = Field(default="America/New_York")
    location_ids: list[UUID] | None = None


# ============ Middleware ============

def require_agency_role(current_user: Account) -> Account:
    """Require user to have agency role or higher."""
    if current_user.role not in [AccountRole.AGENCY, AccountRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agency plan required for this feature",
        )
    return current_user


# ============ Team Management Endpoints ============

@router.post("/team/invite")
async def invite_team_member(
    request: TeamInviteRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Invite a new team member to your agency.
    
    Roles:
    - owner: Full access including billing
    - admin: Full access except billing
    - manager: Content management and reports
    - editor: Create/edit content only
    - viewer: Read-only access
    """
    require_agency_role(current_user)

    try:
        role = TeamRole(request.role.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {[r.value for r in TeamRole]}",
        )

    service = AgencyService(db)
    result = await service.invite_team_member(
        agency_account_id=current_user.id,
        email=request.email,
        role=role,
        location_ids=request.location_ids,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error"),
        )

    return result


@router.post("/team/accept-invite")
async def accept_team_invite(
    token: str = Query(..., description="Invite token from email"),
    current_user: Annotated[Account, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Accept a team invitation.
    """
    service = AgencyService(db)
    result = await service.accept_team_invite(
        invite_token=token,
        user_account_id=current_user.id,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error"),
        )

    return result


@router.get("/team")
async def get_team_members(
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get all team members for your agency.
    """
    require_agency_role(current_user)

    service = AgencyService(db)
    members = await service.get_team_members(current_user.id)

    return {
        "team_members": members,
        "total": len(members),
    }


@router.put("/team/role")
async def update_team_member_role(
    request: TeamRoleUpdateRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Update a team member's role.
    """
    require_agency_role(current_user)

    try:
        role = TeamRole(request.new_role.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    service = AgencyService(db)
    result = await service.update_team_member_role(
        agency_account_id=current_user.id,
        member_email=request.email,
        new_role=role,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error"),
        )

    return result


@router.delete("/team/{email}")
async def remove_team_member(
    email: str,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Remove a team member from your agency.
    """
    require_agency_role(current_user)

    service = AgencyService(db)
    result = await service.remove_team_member(
        agency_account_id=current_user.id,
        member_email=email,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error"),
        )

    return result


@router.get("/team/roles")
async def get_available_roles():
    """
    Get available team roles and their permissions.
    """
    from app.services.agency import ROLE_PERMISSIONS

    roles = []
    for role in TeamRole:
        permissions = ROLE_PERMISSIONS.get(role, [])
        roles.append({
            "role": role.value,
            "permissions": [p.value for p in permissions],
            "permission_count": len(permissions),
        })

    return {"roles": roles}


# ============ White Label Endpoints ============

@router.get("/white-label")
async def get_white_label_settings(
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get current white label settings.
    """
    require_agency_role(current_user)

    service = AgencyService(db)
    settings = await service.get_white_label_settings(current_user.id)

    return settings


@router.put("/white-label")
async def update_white_label_settings(
    request: WhiteLabelRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Update white label settings.
    
    Customize:
    - Brand name and logo
    - Colors
    - Custom domain
    - Email sender name
    - Footer text
    - Hide "Powered by" badge
    """
    require_agency_role(current_user)

    service = AgencyService(db)
    result = await service.update_white_label_settings(
        agency_account_id=current_user.id,
        settings=request.model_dump(exclude_none=True),
    )

    return result


# ============ Bulk Reports Endpoints ============

@router.post("/reports/send-bulk")
async def send_bulk_reports(
    request: BulkReportRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Send reports for multiple locations at once.
    
    If location_ids is not provided, sends to all locations.
    """
    require_agency_role(current_user)

    service = AgencyService(db)
    result = await service.send_bulk_reports(
        agency_account_id=current_user.id,
        location_ids=request.location_ids,
        report_type=request.report_type,
    )

    return result


@router.put("/reports/schedule")
async def schedule_bulk_reports(
    request: ReportScheduleRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Schedule automatic bulk reports.
    
    Configure:
    - Frequency (weekly/monthly)
    - Day and time
    - Timezone
    - Which locations to include
    """
    require_agency_role(current_user)

    service = AgencyService(db)
    result = await service.schedule_bulk_reports(
        agency_account_id=current_user.id,
        schedule=request.model_dump(),
    )

    return result


# ============ Dashboard Endpoints ============

@router.get("/dashboard")
async def get_agency_dashboard(
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get agency dashboard overview.
    
    Returns:
    - Total locations
    - Team member count
    - Pending approvals
    - Aggregate metrics (calls, directions, etc.)
    - Top performing locations
    - White label settings
    """
    require_agency_role(current_user)

    service = AgencyService(db)
    dashboard = await service.get_agency_dashboard(current_user.id)

    return dashboard


@router.get("/locations/compare")
async def compare_locations(
    metric: str = Query(default="calls", description="calls, directions, impressions, reviews"),
    days: int = Query(default=30, ge=7, le=365),
    current_user: Annotated[Account, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Compare performance across all locations.
    
    Returns locations ranked by the specified metric.
    """
    require_agency_role(current_user)

    valid_metrics = ["calls", "directions", "impressions", "new_reviews"]
    if metric not in valid_metrics:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric. Must be one of: {valid_metrics}",
        )

    service = AgencyService(db)
    comparison = await service.get_location_comparison(
        agency_account_id=current_user.id,
        metric=metric,
        days=days,
    )

    return {
        "metric": metric,
        "period_days": days,
        "locations": comparison,
    }


@router.get("/permissions/check")
async def check_permission(
    permission: str = Query(..., description="Permission to check"),
    current_user: Annotated[Account, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Check if the current user has a specific permission.
    """
    # Get user's role in the agency context
    # For now, use account role
    try:
        perm = Permission(permission)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid permission. Available: {[p.value for p in Permission]}",
        )

    # Map account role to team role
    role_map = {
        AccountRole.ADMIN: TeamRole.OWNER,
        AccountRole.AGENCY: TeamRole.ADMIN,
        AccountRole.OWNER: TeamRole.MANAGER,
        AccountRole.MANAGER: TeamRole.EDITOR,
    }

    team_role = role_map.get(current_user.role, TeamRole.VIEWER)

    service = AgencyService(db)
    has_permission = service.check_permission(team_role, perm)

    return {
        "permission": permission,
        "has_permission": has_permission,
        "role": team_role.value,
    }
