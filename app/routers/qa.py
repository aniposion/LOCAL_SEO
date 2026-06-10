"""Q&A management router for Google Business Profile questions."""

from datetime import datetime
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.time import utc_now_aware
from app.core.user_messages import integration_unavailable
from app.db.session import get_db
from app.integrations.gbp import GBPClient
from app.integrations.llm import LLMClient
from app.models.account import Account
from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.location import Location
from app.models.qa import QADraft, QADraftStatus, QAFeedbackRating
from app.routers.deps import get_current_account
from app.services.credits import CreditsService
from app.services.feature_access import FeatureAccessService

router = APIRouter(prefix="/qa", tags=["Q&A"])
logger = logging.getLogger(__name__)


class QuestionResponse(BaseModel):
    id: str
    question_text: str
    author_name: str
    created_at: datetime
    answer: Optional[str] = None
    answer_status: str
    draft_answer: Optional[str] = None
    draft_status: Optional[str] = None
    last_error: Optional[str] = None


class QuestionsListResponse(BaseModel):
    questions: list[QuestionResponse]
    total: int
    pending_count: int
    integration_status: str = "ok"
    warning: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    last_sync_error: Optional[str] = None


class SyncQuestionsResponse(BaseModel):
    success: bool
    message: str
    synced_questions: int
    pending_count: int
    last_sync_at: datetime | None = None
    last_sync_error: str | None = None


class AnswerRequest(BaseModel):
    question_id: str
    answer_text: str
    draft_id: str | None = None


class GenerateAnswerRequest(BaseModel):
    question_id: str
    question_text: str
    author_name: Optional[str] = None


class GenerateAnswerResponse(BaseModel):
    suggested_answer: str
    draft_id: str
    draft_status: str


def _preview_ai_response_usage(db: Session, account_id: UUID, count: int = 1) -> None:
    result = CreditsService(db).preview_usage(str(account_id), "ai_response", count)
    if result.get("allowed"):
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "Rate limit exceeded",
            "message": result.get("reason"),
            "remaining_daily": result.get("remaining_daily", 0),
            "remaining_monthly": result.get("remaining_monthly", 0),
            "cooldown_seconds": result.get("cooldown_remaining_seconds", 0),
            "overage_available": result.get("overage_available", False),
            "overage_cost_cents": result.get("overage_cost_cents", 0),
        },
    )


def _record_ai_response_usage(db: Session, account_id: UUID, count: int = 1) -> None:
    result = CreditsService(db).use_credits(str(account_id), "ai_response", count)
    if result.get("allowed"):
        return

    logger.warning(
        "Q&A ai_response usage record failed after successful generation for account %s x%s: %s",
        account_id,
        count,
        result.get("reason"),
    )


class DraftResponse(BaseModel):
    id: str
    question_id: str
    question_text: str
    author_name: Optional[str] = None
    suggested_answer: Optional[str] = None
    posted_answer: Optional[str] = None
    draft_status: str
    last_error: Optional[str] = None
    feedback_rating: Optional[str] = None
    feedback_notes: Optional[str] = None
    feedback_at: Optional[datetime] = None
    question_created_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    updated_at: datetime


class DraftHistoryResponse(BaseModel):
    items: list[DraftResponse]
    total: int
    limit: int
    offset: int
    feedback_good_count: int = 0
    feedback_needs_edit_count: int = 0
    feedback_wrong_count: int = 0


class DraftFeedbackRequest(BaseModel):
    rating: str
    notes: str | None = None


def _get_owned_location(db: Session, account: Account, location_id: UUID) -> Location:
    location = db.query(Location).filter(Location.id == location_id, Location.account_id == account.id).first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


def _get_gbp_channel(db: Session, location_id: UUID) -> Channel | None:
    return (
        db.query(Channel)
        .filter(Channel.location_id == location_id, Channel.type == ChannelType.GBP, Channel.is_active.is_(True))
        .first()
    )


def _upsert_qa_draft(
    db: Session,
    *,
    location_id: UUID,
    question_id: str,
    question_text: str,
    author_name: str | None,
    question_created_at: datetime | None,
) -> QADraft:
    draft = (
        db.query(QADraft)
        .filter(QADraft.location_id == location_id, QADraft.question_id == question_id)
        .first()
    )
    if not draft:
        draft = QADraft(
            location_id=location_id,
            question_id=question_id,
            question_text=question_text,
            author_name=author_name,
            question_created_at=question_created_at,
            draft_status=QADraftStatus.PENDING,
        )
        db.add(draft)
    else:
        draft.question_text = question_text
        draft.author_name = author_name
        draft.question_created_at = question_created_at
    return draft


def _question_to_response(question: dict, draft: QADraft | None) -> QuestionResponse:
    answer = question.get("topAnswers", [{}])[0].get("text") if question.get("topAnswers") else None
    q_status = "answered" if answer else "pending"
    created_raw = question.get("createTime")
    created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00")) if created_raw else utc_now_aware()
    return QuestionResponse(
        id=question.get("name", ""),
        question_text=question.get("text", ""),
        author_name=question.get("author", {}).get("displayName", "Anonymous"),
        created_at=created_at,
        answer=answer,
        answer_status=q_status,
        draft_answer=draft.suggested_answer if draft else None,
        draft_status=draft.draft_status.value if draft else None,
        last_error=draft.last_error if draft else None,
    )


async def _sync_questions_for_location(
    *,
    db: Session,
    location: Location,
    channel: Channel,
    status_filter: str | None = None,
) -> QuestionsListResponse:
    credentials = channel.get_credentials()
    if not credentials or not credentials.get("access_token"):
        return QuestionsListResponse(
            questions=[],
            total=0,
            pending_count=0,
            integration_status="needs_gbp_credentials",
            warning=integration_unavailable(
                "Google Business Profile Q&A sync",
                "Google Business Profile credentials are missing for this location",
                "Open Integrations to reconnect Google Business Profile and try again",
            ),
            last_sync_at=channel.last_sync_at,
            last_sync_error=(channel.meta or {}).get("qa_last_sync_error") if channel.meta else None,
        )

    try:
        gbp_client = GBPClient(credentials)
        questions_data = await gbp_client.get_questions(location.gbp_location_id)
        questions: list[QuestionResponse] = []
        pending_count = 0

        for q in questions_data.get("questions", []):
            answer = q.get("topAnswers", [{}])[0].get("text") if q.get("topAnswers") else None
            q_status = "answered" if answer else "pending"
            if q_status == "pending":
                pending_count += 1
            if status_filter and q_status != status_filter:
                continue

            question_id = q.get("name", "")
            created_raw = q.get("createTime")
            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00")) if created_raw else None
            draft = _upsert_qa_draft(
                db,
                location_id=location.id,
                question_id=question_id,
                question_text=q.get("text", ""),
                author_name=q.get("author", {}).get("displayName", "Anonymous"),
                question_created_at=created_at,
            )
            if answer:
                draft.posted_answer = answer
                draft.draft_status = QADraftStatus.POSTED
                draft.answered_at = draft.answered_at or utc_now_aware()
                draft.last_error = None
            questions.append(_question_to_response(q, draft))

        channel.last_sync_at = utc_now_aware()
        channel.meta = {
            **(channel.meta or {}),
            "qa_last_sync_at": channel.last_sync_at.isoformat(),
            "qa_last_sync_error": None,
            "qa_last_sync_question_count": len(questions_data.get("questions", [])),
        }
        db.commit()
        return QuestionsListResponse(
            questions=questions,
            total=len(questions),
            pending_count=pending_count,
            integration_status="ok",
            last_sync_at=channel.last_sync_at,
            last_sync_error=None,
        )
    except Exception as exc:
        channel.last_sync_at = utc_now_aware()
        channel.meta = {
            **(channel.meta or {}),
            "qa_last_sync_at": channel.last_sync_at.isoformat(),
            "qa_last_sync_error": str(exc),
            "qa_last_sync_question_count": 0,
        }
        db.commit()
        return QuestionsListResponse(
            questions=[],
            total=0,
            pending_count=0,
            integration_status="gbp_fetch_failed",
            warning=integration_unavailable(
                "Google Business Profile Q&A sync",
                "the Google Business Profile fetch failed",
                "Reconnect the account in Integrations and try again",
            ),
            last_sync_at=channel.last_sync_at,
            last_sync_error=str(exc),
        )


@router.get("/{location_id}", response_model=QuestionsListResponse)
async def get_questions(
    location_id: UUID,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    location = _get_owned_location(db, account, location_id)
    channel = _get_gbp_channel(db, location.id)

    if not channel or channel.status != ChannelStatus.CONNECTED:
        return QuestionsListResponse(
            questions=[],
            total=0,
            pending_count=0,
            integration_status="needs_gbp_connection",
            warning="Google Business Profile is not connected for this location.",
            last_sync_at=channel.last_sync_at if channel else None,
            last_sync_error=(channel.meta or {}).get("qa_last_sync_error") if channel and channel.meta else None,
        )
    return await _sync_questions_for_location(db=db, location=location, channel=channel, status_filter=status_filter)


@router.post("/{location_id}/sync", response_model=SyncQuestionsResponse)
async def sync_questions(
    location_id: UUID,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    location = _get_owned_location(db, account, location_id)
    channel = _get_gbp_channel(db, location.id)

    if not channel or channel.status != ChannelStatus.CONNECTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=integration_unavailable(
                "Google Business Profile Q&A sync",
                "Google Business Profile is not connected for this location",
                "Open Integrations to reconnect Google Business Profile and try again",
            ),
        )

    payload = await _sync_questions_for_location(db=db, location=location, channel=channel)
    return SyncQuestionsResponse(
        success=payload.integration_status == "ok",
        message="Questions synced successfully"
        if payload.integration_status == "ok"
        else (payload.warning or "Q&A sync failed"),
        synced_questions=payload.total,
        pending_count=payload.pending_count,
        last_sync_at=payload.last_sync_at,
        last_sync_error=payload.last_sync_error,
    )


@router.get("/{location_id}/drafts", response_model=DraftHistoryResponse)
def list_drafts(
    location_id: UUID,
    status_filter: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    location = _get_owned_location(db, account, location_id)
    base_query = db.query(QADraft).filter(QADraft.location_id == location.id)
    feedback_good_count = base_query.filter(QADraft.feedback_rating == QAFeedbackRating.GOOD).count()
    feedback_needs_edit_count = base_query.filter(QADraft.feedback_rating == QAFeedbackRating.NEEDS_EDIT).count()
    feedback_wrong_count = base_query.filter(QADraft.feedback_rating == QAFeedbackRating.WRONG).count()

    query = base_query
    if status_filter:
        query = query.filter(QADraft.draft_status == status_filter)
    if search:
        like_pattern = f"%{search.strip()}%"
        query = query.filter(
            (QADraft.question_text.ilike(like_pattern))
            | (QADraft.suggested_answer.ilike(like_pattern))
            | (QADraft.posted_answer.ilike(like_pattern))
            | (QADraft.last_error.ilike(like_pattern))
            | (QADraft.author_name.ilike(like_pattern))
        )
    safe_limit = min(max(limit, 1), 200)
    safe_offset = max(offset, 0)
    total = query.count()
    drafts = query.order_by(QADraft.updated_at.desc()).offset(safe_offset).limit(safe_limit).all()
    return DraftHistoryResponse(
        items=[
            DraftResponse(
                id=str(draft.id),
                question_id=draft.question_id,
                question_text=draft.question_text,
                author_name=draft.author_name,
                suggested_answer=draft.suggested_answer,
                posted_answer=draft.posted_answer,
                draft_status=draft.draft_status.value,
                last_error=draft.last_error,
                feedback_rating=draft.feedback_rating.value if draft.feedback_rating else None,
                feedback_notes=draft.feedback_notes,
                feedback_at=draft.feedback_at,
                question_created_at=draft.question_created_at,
                answered_at=draft.answered_at,
                updated_at=draft.updated_at,
            )
            for draft in drafts
        ],
        total=total,
        limit=safe_limit,
        offset=safe_offset,
        feedback_good_count=feedback_good_count,
        feedback_needs_edit_count=feedback_needs_edit_count,
        feedback_wrong_count=feedback_wrong_count,
    )


@router.post("/{location_id}/drafts/{draft_id}/feedback", response_model=DraftResponse)
def save_draft_feedback(
    location_id: UUID,
    draft_id: UUID,
    request: DraftFeedbackRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    location = _get_owned_location(db, account, location_id)
    draft = (
        db.query(QADraft)
        .filter(QADraft.id == draft_id, QADraft.location_id == location.id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    try:
        feedback_rating = QAFeedbackRating(request.rating)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid feedback rating") from exc

    draft.feedback_rating = feedback_rating
    draft.feedback_notes = request.notes.strip() if request.notes else None
    draft.feedback_at = utc_now_aware()
    db.commit()
    db.refresh(draft)

    return DraftResponse(
        id=str(draft.id),
        question_id=draft.question_id,
        question_text=draft.question_text,
        author_name=draft.author_name,
        suggested_answer=draft.suggested_answer,
        posted_answer=draft.posted_answer,
        draft_status=draft.draft_status.value,
        last_error=draft.last_error,
        feedback_rating=draft.feedback_rating.value if draft.feedback_rating else None,
        feedback_notes=draft.feedback_notes,
        feedback_at=draft.feedback_at,
        question_created_at=draft.question_created_at,
        answered_at=draft.answered_at,
        updated_at=draft.updated_at,
    )


@router.post("/{location_id}/answer")
async def post_answer(
    location_id: UUID,
    request: AnswerRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    location = _get_owned_location(db, account, location_id)
    FeatureAccessService(db).check_feature_access(account, "qa_auto_response")
    channel = _get_gbp_channel(db, location.id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Google Business Profile is not connected")

    credentials = channel.get_credentials()
    if not credentials or not credentials.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=integration_unavailable(
                "Google Business Profile Q&A answer posting",
                "Google Business Profile credentials are missing",
                "Open Integrations to reconnect Google Business Profile and try again",
            ),
        )

    draft = None
    if request.draft_id:
        try:
            draft_uuid = UUID(request.draft_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid draft id") from exc
        draft = (
            db.query(QADraft)
            .filter(QADraft.id == draft_uuid, QADraft.location_id == location.id)
            .first()
        )
    if not draft:
        draft = (
            db.query(QADraft)
            .filter(QADraft.location_id == location.id, QADraft.question_id == request.question_id)
            .first()
        )
    if not draft:
        draft = QADraft(
            location_id=location.id,
            question_id=request.question_id,
            question_text="",
            draft_status=QADraftStatus.PENDING,
        )
        db.add(draft)

    try:
        gbp_client = GBPClient(credentials)
        await gbp_client.answer_question(location.gbp_location_id, request.question_id, request.answer_text)
        draft.question_id = request.question_id
        draft.posted_answer = request.answer_text
        draft.draft_status = QADraftStatus.POSTED
        draft.answered_at = utc_now_aware()
        draft.last_error = None
        if not draft.suggested_answer:
            draft.suggested_answer = request.answer_text
        db.commit()
        return {
            "success": True,
            "message": "Answer posted successfully",
            "draft_id": str(draft.id),
            "draft_status": draft.draft_status.value,
        }
    except Exception as exc:
        draft.draft_status = QADraftStatus.FAILED
        draft.last_error = str(exc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{location_id}/generate-answer", response_model=GenerateAnswerResponse)
async def generate_answer(
    location_id: UUID,
    request: GenerateAnswerRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    location = _get_owned_location(db, account, location_id)
    FeatureAccessService(db).check_feature_access(account, "qa_auto_response")
    _preview_ai_response_usage(db, account.id, 1)

    draft = _upsert_qa_draft(
        db,
        location_id=location.id,
        question_id=request.question_id,
        question_text=request.question_text,
        author_name=request.author_name,
        question_created_at=None,
    )

    used_ai_generation = False
    try:
        llm = LLMClient()
        prompt = f"""You are a helpful business owner responding to a customer question on Google Maps.

Business: {location.name}
Category: {getattr(location, 'category', None) or 'Local Business'}
Address: {location.address or ''}

Customer Question: {request.question_text}

Write a friendly, helpful, and professional answer. Keep it concise (2-3 sentences max).
Include relevant details about the business if applicable."""
        answer = await llm.generate(prompt)
        used_ai_generation = True
    except Exception:
        question_lower = request.question_text.lower()
        if "hour" in question_lower or "open" in question_lower:
            answer = "Our hours can vary by day, so please check the latest business profile hours before visiting or call us directly for the most accurate information."
        elif "parking" in question_lower:
            answer = "Parking availability can vary by time of day, but we can confirm the best parking options when you visit or call us directly."
        elif "reservation" in question_lower or "book" in question_lower:
            answer = "Yes, booking is available. Please contact us directly or use the booking option listed on our profile if it is available for this location."
        elif "price" in question_lower or "cost" in question_lower:
            answer = "Pricing can depend on the service you need, so the best next step is to contact us directly for the most accurate quote."
        else:
            answer = "Thanks for your question. Please contact us directly and we will be happy to help with the details for this location."

    if used_ai_generation:
        _record_ai_response_usage(db, account.id, 1)
    draft.suggested_answer = answer
    draft.draft_status = QADraftStatus.DRAFT
    draft.last_error = None
    db.commit()
    db.refresh(draft)

    return GenerateAnswerResponse(
        suggested_answer=answer,
        draft_id=str(draft.id),
        draft_status=draft.draft_status.value,
    )
