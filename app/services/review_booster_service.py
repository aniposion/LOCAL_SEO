"""P2: Review Booster service - Compliance-Safe implementation."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.time import utc_now_aware
from app.models.review_booster import (
    BoosterRequest,
    CampaignStatus,
    FeedbackStatus,
    PrivateFeedback,
    RequestChannel,
    RequestStatus,
    ReviewCampaign,
    ReviewOptout,
)
from app.schemas.review_booster import (
    FeedbackUpdateStatus,
    OptoutCreate,
    ReviewCampaignCreate,
    ReviewCampaignUpdate,
    ReviewRequestCreate,
)

logger = logging.getLogger(__name__)


class ReviewBoosterService:
    """Service for compliance-safe review requests."""

    def __init__(self, db: Session):
        self.db = db

    def get_campaigns(
        self,
        location_id: UUID,
        status: Optional[str] = None,
    ) -> list[ReviewCampaign]:
        query = select(ReviewCampaign).where(ReviewCampaign.location_id == location_id)
        if status:
            query = query.where(ReviewCampaign.status == CampaignStatus(status))
        query = query.order_by(ReviewCampaign.created_at.desc())
        return list(self.db.execute(query).scalars().all())

    def get_campaign(self, campaign_id: UUID) -> Optional[ReviewCampaign]:
        return self.db.execute(
            select(ReviewCampaign).where(ReviewCampaign.id == campaign_id)
        ).scalar_one_or_none()

    def create_campaign(self, location_id: UUID, data: ReviewCampaignCreate) -> ReviewCampaign:
        campaign = ReviewCampaign(
            location_id=location_id,
            name=data.name,
            sms_template=data.sms_template,
            email_template=data.email_template,
            email_subject=data.email_subject,
            delay_hours=data.delay_hours,
            channels=data.channels,
            google_review_url=data.google_review_url,
            private_feedback_url=data.private_feedback_url,
        )
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        logger.info("Created review campaign %s for location %s", campaign.id, location_id)
        return campaign

    def update_campaign(
        self,
        campaign_id: UUID,
        data: ReviewCampaignUpdate,
    ) -> Optional[ReviewCampaign]:
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(campaign, field, value)

        campaign.updated_at = utc_now_aware()
        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def delete_campaign(self, campaign_id: UUID) -> bool:
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return False
        campaign.status = CampaignStatus.COMPLETED
        self.db.commit()
        return True

    def get_requests(
        self,
        location_id: UUID,
        campaign_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[BoosterRequest]:
        query = select(BoosterRequest).where(BoosterRequest.location_id == location_id)
        if campaign_id:
            query = query.where(BoosterRequest.campaign_id == campaign_id)
        if status:
            query = query.where(BoosterRequest.status == RequestStatus(status))
        query = query.order_by(BoosterRequest.created_at.desc()).limit(limit)
        return list(self.db.execute(query).scalars().all())

    def get_request(self, request_id: UUID) -> Optional[BoosterRequest]:
        return self.db.execute(
            select(BoosterRequest).where(BoosterRequest.id == request_id)
        ).scalar_one_or_none()

    def requeue_request(self, request_id: UUID) -> Optional[BoosterRequest]:
        request = self.get_request(request_id)
        if not request:
            return None
        if request.status != RequestStatus.FAILED:
            raise ValueError("Only failed requests can be requeued")

        request.status = RequestStatus.PENDING
        request.retry_count = 0
        request.next_retry_at = None
        request.last_error = None
        request.last_attempt_at = None
        self.db.commit()
        self.db.refresh(request)
        return request

    def send_request(self, location_id: UUID, data: ReviewRequestCreate) -> BoosterRequest:
        campaign = self.get_campaign(data.campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        if campaign.status == CampaignStatus.COMPLETED:
            raise ValueError("Completed campaigns cannot send new review requests")

        if self.is_opted_out(location_id, data.customer_phone, data.customer_email):
            request = BoosterRequest(
                campaign_id=data.campaign_id,
                location_id=location_id,
                customer_name=data.customer_name,
                customer_phone=data.customer_phone,
                customer_email=data.customer_email,
                consent_given=data.consent_given,
                consent_timestamp=utc_now_aware(),
                consent_method=data.consent_method,
                channel=RequestChannel(data.channel),
                status=RequestStatus.OPTED_OUT,
                message_content="[OPTED OUT - Not sent]",
                google_link_included=True,
                opted_out_at=utc_now_aware(),
            )
            self.db.add(request)
            self.db.commit()
            self.db.refresh(request)
            return request

        request = BoosterRequest(
            campaign_id=data.campaign_id,
            location_id=location_id,
            customer_name=data.customer_name,
            customer_phone=data.customer_phone,
            customer_email=data.customer_email,
            consent_given=data.consent_given,
            consent_timestamp=utc_now_aware(),
            consent_method=data.consent_method,
            channel=RequestChannel(data.channel),
            status=RequestStatus.PENDING,
            message_content=self._build_message(campaign, data),
            google_link_included=True,
            feedback_link_included=bool(campaign.private_feedback_url),
        )
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        logger.info("Created review request %s for campaign %s", request.id, campaign.id)
        return request

    def _build_message(self, campaign: ReviewCampaign, data: ReviewRequestCreate) -> str:
        template = campaign.sms_template if data.channel == "sms" else campaign.email_template
        if not template:
            template = (
                "안녕하세요 {customer_name}님. 이용해 주셔서 감사합니다. "
                "서비스가 어떠셨는지 리뷰를 남겨주시면 큰 도움이 됩니다. {google_link}"
            )

        location_name = "우리 매장"
        message = template.replace("{customer_name}", data.customer_name or "고객")
        message = message.replace("{business_name}", location_name)
        message = message.replace("{google_link}", campaign.google_review_url)
        if campaign.private_feedback_url and "{feedback_link}" in message:
            message = message.replace("{feedback_link}", campaign.private_feedback_url)
        return message

    def update_request_status(
        self,
        request_id: UUID,
        status: str,
        external_id: Optional[str] = None,
    ) -> Optional[BoosterRequest]:
        request = self.get_request(request_id)
        if not request:
            return None

        request.status = RequestStatus(status)
        if status == "sent":
            request.sent_at = utc_now_aware()
            if external_id:
                if request.channel == RequestChannel.SMS:
                    request.twilio_message_sid = external_id
                else:
                    request.sendgrid_message_id = external_id
        elif status == "delivered":
            request.delivered_at = utc_now_aware()

        self.db.commit()
        self.db.refresh(request)
        return request

    def track_click(self, request_id: UUID, link_type: str) -> bool:
        request = self.get_request(request_id)
        if not request:
            return False

        if link_type == "google":
            request.google_link_clicked_at = utc_now_aware()
            campaign = self.get_campaign(request.campaign_id)
            if campaign:
                campaign.total_clicked += 1
        elif link_type == "feedback":
            request.feedback_link_clicked_at = utc_now_aware()

        self.db.commit()
        return True

    def is_opted_out(
        self,
        location_id: UUID,
        phone: Optional[str],
        email: Optional[str],
    ) -> bool:
        if not phone and not email:
            return False

        conditions = []
        if phone:
            conditions.append(and_(ReviewOptout.location_id == location_id, ReviewOptout.phone == phone))
        if email:
            conditions.append(and_(ReviewOptout.location_id == location_id, ReviewOptout.email == email))

        return (
            self.db.execute(select(ReviewOptout).where(or_(*conditions)).limit(1)).scalar_one_or_none()
            is not None
        )

    def add_optout(self, location_id: UUID, data: OptoutCreate) -> ReviewOptout:
        optout = ReviewOptout(
            location_id=location_id,
            phone=data.phone,
            email=data.email,
            reason=data.reason,
        )
        self.db.add(optout)
        self.db.commit()
        self.db.refresh(optout)
        logger.info("Added opt-out for location %s", location_id)
        return optout

    def get_feedbacks(
        self,
        location_id: UUID,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[PrivateFeedback]:
        query = select(PrivateFeedback).where(PrivateFeedback.location_id == location_id)
        if status:
            query = query.where(PrivateFeedback.status == FeedbackStatus(status))
        query = query.order_by(PrivateFeedback.created_at.desc()).limit(limit)
        return list(self.db.execute(query).scalars().all())

    def get_feedback(self, feedback_id: UUID) -> Optional[PrivateFeedback]:
        return self.db.execute(
            select(PrivateFeedback).where(PrivateFeedback.id == feedback_id)
        ).scalar_one_or_none()

    def update_feedback(
        self,
        feedback_id: UUID,
        data: FeedbackUpdateStatus,
    ) -> Optional[PrivateFeedback]:
        feedback = self.get_feedback(feedback_id)
        if not feedback:
            return None

        feedback.status = FeedbackStatus(data.status)
        if data.notes:
            feedback.notes = data.notes
        if data.assigned_to:
            feedback.assigned_to = data.assigned_to
        if data.status == "resolved":
            feedback.resolved_at = utc_now_aware()

        self.db.commit()
        self.db.refresh(feedback)
        return feedback


def get_review_booster_service(db: Session) -> ReviewBoosterService:
    """Get service instance."""
    return ReviewBoosterService(db)
