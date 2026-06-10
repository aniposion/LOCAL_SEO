"""P2: Review Booster Program router - Compliance-Safe."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.location import Location
from app.models.review_booster import BoosterRequest, PrivateFeedback, ReviewCampaign
from app.routers.deps import get_current_account
from app.schemas.review_booster import (
    FeedbackList,
    FeedbackUpdateStatus,
    OptoutCreate,
    OptoutResponse,
    PrivateFeedbackResponse,
    ReviewBoosterAnalyticsResponse,
    ReviewCampaignCreate,
    ReviewCampaignList,
    ReviewCampaignResponse,
    ReviewCampaignUpdate,
    ReviewRequestCreate,
    ReviewRequestList,
    ReviewRequestResponse,
)
from app.services.feature_access import FeatureAccessService
from app.services.review_booster_service import get_review_booster_service

router = APIRouter(prefix="/review-booster", tags=["review-booster"])


def _get_owned_location(db: Session, location_id: UUID, account_id: UUID) -> Location:
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == account_id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


def _get_owned_campaign(db: Session, campaign_id: UUID, account_id: UUID) -> ReviewCampaign:
    campaign = db.query(ReviewCampaign).filter(ReviewCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    _get_owned_location(db, campaign.location_id, account_id)
    return campaign


def _get_owned_request(db: Session, request_id: UUID, account_id: UUID) -> BoosterRequest:
    request = db.query(BoosterRequest).filter(BoosterRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    _get_owned_location(db, request.location_id, account_id)
    return request


def _get_owned_feedback(db: Session, feedback_id: UUID, account_id: UUID) -> PrivateFeedback:
    feedback = db.query(PrivateFeedback).filter(PrivateFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    _get_owned_location(db, feedback.location_id, account_id)
    return feedback


@router.get("/campaigns", response_model=ReviewCampaignList)
def get_campaigns(
    location_id: UUID = Query(..., description="Location ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    _get_owned_location(db, location_id, current_account.id)
    service = get_review_booster_service(db)
    campaigns = service.get_campaigns(location_id, status)
    return ReviewCampaignList(
        items=[ReviewCampaignResponse.model_validate(c) for c in campaigns],
        total=len(campaigns),
    )


@router.get("/analytics/{location_id}", response_model=ReviewBoosterAnalyticsResponse)
def get_analytics(
    location_id: UUID,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    _get_owned_location(db, location_id, current_account.id)
    service = get_review_booster_service(db)
    campaigns = service.get_campaigns(location_id)
    requests = service.get_requests(location_id, limit=1000)

    active_campaigns = sum(1 for campaign in campaigns if campaign.status.value == 'active')
    paused_campaigns = sum(1 for campaign in campaigns if campaign.status.value == 'paused')
    completed_campaigns = sum(1 for campaign in campaigns if campaign.status.value == 'completed')

    pending_requests = sum(1 for request in requests if request.status.value == 'pending')
    delivered_requests = sum(1 for request in requests if request.status.value == 'delivered')
    failed_requests = sum(1 for request in requests if request.status.value == 'failed')
    pending_retries = sum(
        1
        for request in requests
        if request.status.value == 'failed'
        and (request.retry_count or 0) > 0
        and request.next_retry_at is not None
    )
    opted_out_requests = sum(1 for request in requests if request.status.value == 'opted_out')

    return ReviewBoosterAnalyticsResponse(
        location_id=location_id,
        period_days=days,
        total_campaigns=len(campaigns),
        active_campaigns=active_campaigns,
        paused_campaigns=paused_campaigns,
        completed_campaigns=completed_campaigns,
        total_requests=len(requests),
        pending_requests=pending_requests,
        delivered_requests=delivered_requests,
        failed_requests=failed_requests,
        pending_retries=pending_retries,
        opted_out_requests=opted_out_requests,
        attention_requests=failed_requests + opted_out_requests + pending_retries,
        total_sent=sum(campaign.total_sent for campaign in campaigns),
    )
@router.post("/campaigns", response_model=ReviewCampaignResponse)
def create_campaign(
    data: ReviewCampaignCreate,
    location_id: UUID = Query(..., description="Location ID"),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    _get_owned_location(db, location_id, current_account.id)
    FeatureAccessService(db).check_feature_access(current_account, "review_booster")
    campaign = get_review_booster_service(db).create_campaign(location_id, data)
    return ReviewCampaignResponse.model_validate(campaign)


@router.get("/campaigns/{campaign_id}", response_model=ReviewCampaignResponse)
def get_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    return ReviewCampaignResponse.model_validate(_get_owned_campaign(db, campaign_id, current_account.id))


@router.put("/campaigns/{campaign_id}", response_model=ReviewCampaignResponse)
def update_campaign(
    campaign_id: UUID,
    data: ReviewCampaignUpdate,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    _get_owned_campaign(db, campaign_id, current_account.id)
    campaign = get_review_booster_service(db).update_campaign(campaign_id, data)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return ReviewCampaignResponse.model_validate(campaign)


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    _get_owned_campaign(db, campaign_id, current_account.id)
    success = get_review_booster_service(db).delete_campaign(campaign_id)
    if not success:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"status": "archived"}


@router.post("/requests/send", response_model=ReviewRequestResponse)
def send_review_request(
    data: ReviewRequestCreate,
    location_id: UUID = Query(..., description="Location ID"),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    if data.channel == "sms" and not data.customer_phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone number required for SMS channel")
    if data.channel == "email" and not data.customer_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email required for email channel")

    _get_owned_location(db, location_id, current_account.id)
    _get_owned_campaign(db, data.campaign_id, current_account.id)
    FeatureAccessService(db).check_feature_access(current_account, "review_booster")

    try:
        request = get_review_booster_service(db).send_request(location_id, data)
        return ReviewRequestResponse.model_validate(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/requests", response_model=ReviewRequestList)
def get_requests(
    location_id: UUID = Query(..., description="Location ID"),
    campaign_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    _get_owned_location(db, location_id, current_account.id)
    requests = get_review_booster_service(db).get_requests(location_id, campaign_id, status, limit)
    return ReviewRequestList(
        items=[ReviewRequestResponse.model_validate(r) for r in requests],
        total=len(requests),
    )


@router.get("/requests/{request_id}", response_model=ReviewRequestResponse)
def get_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    return ReviewRequestResponse.model_validate(_get_owned_request(db, request_id, current_account.id))


@router.post("/requests/{request_id}/requeue", response_model=ReviewRequestResponse)
def requeue_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    _get_owned_request(db, request_id, current_account.id)
    FeatureAccessService(db).check_feature_access(current_account, "review_booster")
    try:
        request = get_review_booster_service(db).requeue_request(request_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    return ReviewRequestResponse.model_validate(request)


@router.post("/optouts", response_model=OptoutResponse)
def add_optout(
    data: OptoutCreate,
    location_id: UUID = Query(..., description="Location ID"),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    if not data.phone and not data.email:
        raise HTTPException(status_code=400, detail="Either phone or email is required")

    _get_owned_location(db, location_id, current_account.id)
    optout = get_review_booster_service(db).add_optout(location_id, data)
    return OptoutResponse(is_opted_out=True, opted_out_at=optout.opted_out_at)


@router.get("/optouts/check", response_model=OptoutResponse)
def check_optout(
    location_id: UUID = Query(...),
    phone: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    _get_owned_location(db, location_id, current_account.id)
    is_opted_out = get_review_booster_service(db).is_opted_out(location_id, phone, email)
    return OptoutResponse(is_opted_out=is_opted_out)


@router.get("/feedbacks", response_model=FeedbackList)
def get_feedbacks(
    location_id: UUID = Query(..., description="Location ID"),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    _get_owned_location(db, location_id, current_account.id)
    feedbacks = get_review_booster_service(db).get_feedbacks(location_id, status, limit)
    return FeedbackList(
        items=[PrivateFeedbackResponse.model_validate(f) for f in feedbacks],
        total=len(feedbacks),
    )


@router.get("/feedbacks/{feedback_id}", response_model=PrivateFeedbackResponse)
def get_feedback(
    feedback_id: UUID,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    return PrivateFeedbackResponse.model_validate(_get_owned_feedback(db, feedback_id, current_account.id))


@router.put("/feedbacks/{feedback_id}", response_model=PrivateFeedbackResponse)
def update_feedback(
    feedback_id: UUID,
    data: FeedbackUpdateStatus,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    _get_owned_feedback(db, feedback_id, current_account.id)
    feedback = get_review_booster_service(db).update_feedback(feedback_id, data)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return PrivateFeedbackResponse.model_validate(feedback)


@router.get("/templates")
def get_templates():
    return {
        "sms_templates": [
            {
                "id": "default",
                "name": "Default follow-up",
                "template": "Hi {customer_name}, thanks for choosing {business_name}. If you have a minute, please leave a Google review here: {google_link}",
            },
            {
                "id": "restaurant",
                "name": "Restaurant follow-up",
                "template": "Hi {customer_name}, thanks for visiting {business_name}. If your visit went well, we would appreciate a Google review here: {google_link}",
            },
            {
                "id": "service",
                "name": "Service business follow-up",
                "template": "Hi {customer_name}, thanks for working with {business_name}. If you have a moment, please share your feedback here: {google_link}",
            },
        ],
        "placeholders": [
            "{customer_name} - customer name",
            "{business_name} - business name",
            "{google_link} - Google review link (required)",
            "{feedback_link} - internal feedback link (optional)",
        ],
    }


