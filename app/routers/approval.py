"""Approval workflow router for content management."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routers.deps import get_current_user
from app.models.account import Account
from app.models.post import Post, PostStatus
from app.services.approval import ApprovalWorkflowService
from app.services.notification import NotificationChannel

router = APIRouter(prefix="/approval", tags=["approval"])


# ============ Schemas ============

class DraftCreateRequest(BaseModel):
    """Request to create draft content for approval."""

    location_id: UUID
    theme: str = Field(..., description="Content theme (e.g., 'spring promotion', 'new service')")
    services: list[str] = Field(..., description="Services to highlight")
    platform_targets: list[str] | None = Field(
        default=["GBP", "INSTAGRAM", "WEBSITE"],
        description="Target platforms",
    )
    tone: str = Field(default="expert yet friendly", description="Content tone")
    language: str = Field(default="ko", description="Content language")
    audience: str | None = Field(default=None, description="Target audience")
    promo: str | None = Field(default=None, description="Promotional message")
    notification_channel: str = Field(
        default="email",
        description="Notification channel: kakao, slack, email, sms",
    )
    phone_number: str | None = Field(
        default=None,
        description="Phone number for SMS notification (required if channel is 'sms')",
    )
    generate_image: bool = Field(default=True, description="Generate AI image")
    image_style: str = Field(
        default="local_business",
        description="Image style: photorealistic, artistic, commercial, social_media, local_business",
    )


class NotificationPreferenceRequest(BaseModel):
    """Request to update notification preferences."""
    
    channel: str = Field(
        ...,
        description="Preferred channel: email, sms, or both",
    )
    phone_number: str | None = Field(
        default=None,
        description="Phone number for SMS (required if channel is 'sms' or 'both')",
    )


class DraftCreateResponse(BaseModel):
    """Response after creating draft content."""

    posts: list[dict]
    image_url: str | None
    notifications: list[dict]


class ApprovalActionRequest(BaseModel):
    """Request for approval action."""

    token: str = Field(..., description="Approval token")
    schedule_at: datetime | None = Field(default=None, description="Schedule publish time")


class RejectionRequest(BaseModel):
    """Request for rejection."""

    token: str = Field(..., description="Approval token")
    reason: str | None = Field(default=None, description="Rejection reason")


class RevisionRequest(BaseModel):
    """Request for revision."""

    token: str = Field(..., description="Approval token")
    notes: str = Field(..., description="Revision notes")


class PostApprovalResponse(BaseModel):
    """Response for approval actions."""

    id: UUID
    platform: str
    status: str
    title: str | None
    body: str | None
    image_url: str | None
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None

    model_config = {"from_attributes": True}


class PendingApprovalResponse(BaseModel):
    """Response for pending approvals list."""

    id: UUID
    platform: str
    status: str
    title: str | None
    body_preview: str | None
    image_url: str | None
    location_name: str | None
    approval_requested_at: datetime | None
    approval_url: str


class ApprovalStatsResponse(BaseModel):
    """Response for approval statistics."""

    pending: int
    approved: int
    rejected: int
    posted: int
    total: int
    approval_rate: float
    avg_approval_time_hours: float | None


# ============ Endpoints ============

@router.post("/draft", response_model=DraftCreateResponse)
async def create_draft_for_approval(
    request: DraftCreateRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create AI-generated draft content and send for approval.

    Workflow:
    1. AI generates content for specified platforms
    2. AI generates image (optional)
    3. Posts created with PENDING_APPROVAL status
    4. Notification sent via specified channel (Kakao/Slack/Email)
    5. Owner clicks approve/reject link
    """
    try:
        notification_channel = NotificationChannel(request.notification_channel.lower())
    except ValueError:
        notification_channel = NotificationChannel.SLACK

    service = ApprovalWorkflowService(db)

    try:
        result = await service.create_draft_with_approval(
            location_id=request.location_id,
            account_id=current_user.id,
            theme=request.theme,
            services=request.services,
            platform_targets=request.platform_targets,
            tone=request.tone,
            language=request.language,
            audience=request.audience,
            promo=request.promo,
            notification_channel=notification_channel,
            generate_image=request.generate_image,
            image_style=request.image_style,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/posts/{post_id}/approve", response_model=PostApprovalResponse)
async def approve_post(
    post_id: UUID,
    request: ApprovalActionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[Account | None, Depends(get_current_user)] = None,
):
    """
    Approve a post for publishing.

    Can be called with or without authentication (token-based approval).
    """
    service = ApprovalWorkflowService(db)

    try:
        post = await service.approve_post(
            post_id=post_id,
            approval_token=request.token,
            approver_id=current_user.id if current_user else None,
            schedule_at=request.schedule_at,
        )
        return PostApprovalResponse(
            id=post.id,
            platform=post.platform.value,
            status=post.status.value,
            title=post.title,
            body=post.body,
            image_url=post.ai_image_url,
            approved_at=post.approved_at,
            rejected_at=post.rejected_at,
            rejection_reason=post.rejection_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/posts/{post_id}/reject", response_model=PostApprovalResponse)
async def reject_post(
    post_id: UUID,
    request: RejectionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[Account | None, Depends(get_current_user)] = None,
):
    """
    Reject a post.

    Can be called with or without authentication (token-based rejection).
    """
    service = ApprovalWorkflowService(db)

    try:
        post = await service.reject_post(
            post_id=post_id,
            approval_token=request.token,
            reason=request.reason,
            rejector_id=current_user.id if current_user else None,
        )
        return PostApprovalResponse(
            id=post.id,
            platform=post.platform.value,
            status=post.status.value,
            title=post.title,
            body=post.body,
            image_url=post.ai_image_url,
            approved_at=post.approved_at,
            rejected_at=post.rejected_at,
            rejection_reason=post.rejection_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/posts/{post_id}/revision", response_model=PostApprovalResponse)
async def request_revision(
    post_id: UUID,
    request: RevisionRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Request revision for a post."""
    service = ApprovalWorkflowService(db)

    try:
        post = await service.request_revision(
            post_id=post_id,
            approval_token=request.token,
            revision_notes=request.notes,
        )
        return PostApprovalResponse(
            id=post.id,
            platform=post.platform.value,
            status=post.status.value,
            title=post.title,
            body=post.body,
            image_url=post.ai_image_url,
            approved_at=post.approved_at,
            rejected_at=post.rejected_at,
            rejection_reason=post.rejection_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/pending", response_model=list[PendingApprovalResponse])
async def get_pending_approvals(
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, le=100),
):
    """Get all posts pending approval for the current user."""
    from app.core.config import settings

    service = ApprovalWorkflowService(db)
    posts = service.get_pending_approvals(current_user.id, limit)

    return [
        PendingApprovalResponse(
            id=post.id,
            platform=post.platform.value,
            status=post.status.value,
            title=post.title,
            body_preview=(post.body[:200] + "...") if post.body and len(post.body) > 200 else post.body,
            image_url=post.ai_image_url,
            location_name=post.location.name if post.location else None,
            approval_requested_at=post.approval_requested_at,
            approval_url=f"{settings.app_url}/approval/posts/{post.id}/approve?token={post.approval_token}",
        )
        for post in posts
    ]


@router.get("/stats", response_model=ApprovalStatsResponse)
async def get_approval_stats(
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get approval workflow statistics."""
    service = ApprovalWorkflowService(db)
    stats = service.get_approval_stats(current_user.id)
    return ApprovalStatsResponse(**stats)


# ============ Public Approval Page Endpoints ============
# These endpoints can be accessed without authentication via token

@router.get("/posts/{post_id}/preview")
async def preview_post_for_approval(
    post_id: UUID,
    token: str = Query(..., description="Approval token"),
    db: Session = Depends(get_db),
):
    """
    Preview post content for approval (public endpoint with token).

    This endpoint is used for the approval page that owners access via notification links.
    """
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.approval_token == token,
    ).first()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or invalid token",
        )

    if post.status != PostStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Post is not pending approval (status: {post.status.value})",
        )

    return {
        "id": str(post.id),
        "platform": post.platform.value,
        "status": post.status.value,
        "title": post.title,
        "body": post.body,
        "hashtags": post.hashtags,
        "image_url": post.ai_image_url or post.image_url,
        "image_prompt": post.image_prompt,
        "location": {
            "name": post.location.name if post.location else None,
            "city": post.location.city if post.location else None,
        },
        "generated_by": post.generated_by,
        "approval_requested_at": post.approval_requested_at.isoformat() if post.approval_requested_at else None,
    }


@router.post("/posts/{post_id}/quick-approve")
async def quick_approve_post(
    post_id: UUID,
    token: str = Query(..., description="Approval token"),
    db: Session = Depends(get_db),
):
    """
    Quick approve endpoint (GET-style approval via link click).

    This is a simplified approval endpoint for use in notification links.
    """
    service = ApprovalWorkflowService(db)

    try:
        post = await service.approve_post(
            post_id=post_id,
            approval_token=token,
        )
        return {
            "success": True,
            "message": "콘텐츠가 승인되었습니다.",
            "post_id": str(post.id),
            "status": post.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/posts/{post_id}/quick-reject")
async def quick_reject_post(
    post_id: UUID,
    token: str = Query(..., description="Approval token"),
    reason: str = Query(default=None, description="Rejection reason"),
    db: Session = Depends(get_db),
):
    """
    Quick reject endpoint (GET-style rejection via link click).

    This is a simplified rejection endpoint for use in notification links.
    """
    service = ApprovalWorkflowService(db)

    try:
        post = await service.reject_post(
            post_id=post_id,
            approval_token=token,
            reason=reason,
        )
        return {
            "success": True,
            "message": "콘텐츠가 거절되었습니다.",
            "post_id": str(post.id),
            "status": post.status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============ Notification Preferences ============

@router.put("/notification-preferences")
async def update_notification_preferences(
    request: NotificationPreferenceRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Update notification channel preference for content approval.
    
    Options:
    - email: Receive approval requests via email only
    - sms: Receive approval requests via SMS only
    - both: Receive via both email and SMS
    """
    valid_channels = ["email", "sms", "both"]
    if request.channel not in valid_channels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel. Must be one of: {valid_channels}",
        )

    # Validate phone number if SMS is selected
    if request.channel in ["sms", "both"]:
        phone = request.phone_number or current_user.phone
        if not phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number is required for SMS notifications",
            )
        # Update phone if provided
        if request.phone_number:
            current_user.phone = request.phone_number

    current_user.notification_channel = request.channel
    db.commit()

    return {
        "success": True,
        "notification_channel": current_user.notification_channel,
        "phone": current_user.phone,
        "message": f"Notification preference updated to: {request.channel}",
    }


@router.get("/notification-preferences")
async def get_notification_preferences(
    current_user: Annotated[Account, Depends(get_current_user)],
):
    """Get current notification preferences."""
    return {
        "notification_channel": current_user.notification_channel,
        "phone": current_user.phone,
        "email": current_user.email,
    }


@router.post("/posts/{post_id}/send-notification")
async def send_approval_notification(
    post_id: UUID,
    channel: str = Query(default=None, description="Override channel: email or sms"),
    phone_number: str = Query(default=None, description="Override phone number for SMS"),
    current_user: Annotated[Account, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Manually send/resend approval notification for a post.
    
    Can override the default notification channel.
    """
    from app.services.magic_link import ApprovalWorkflowService as MagicApprovalService

    # Verify post ownership
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Determine channel
    target_channel = channel or current_user.notification_channel or "email"
    target_phone = phone_number or current_user.phone

    # Send notification
    service = MagicApprovalService(db)

    if target_channel == "both":
        result = await service.send_approval_notification_multi(
            post_id=post_id,
            channels=["email", "sms"],
            phone_number=target_phone,
        )
    else:
        result = await service.send_approval_notification(
            post_id=post_id,
            channel=target_channel,
            phone_number=target_phone,
        )

    return {
        "success": result.get("success", False),
        "channel": target_channel,
        "result": result,
    }
