"""AI Smart Review Responder API endpoints."""

import csv
import io
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.rate_limiter import check_rate_limit, record_rate_limit_usage
from app.db.session import get_db
from app.models.account import Account
from app.models.location import Location
from app.routers.deps import get_current_account
from app.schemas.review_response import (
    ApproveResponseRequest,
    BulkRetryRequest,
    BulkRetryResponse,
    FailedResponsesResponse,
    GenerateResponseRequest,
    PendingResponsesFilter,
    RejectResponseRequest,
    ReviewResponderSummaryResponse,
    ReviewResponseHistoryItem,
    ReviewResponseHistoryResponse,
    ResponseDraft,
    ReviewResponseResponse,
)
from app.services.feature_access import FeatureAccessService
from app.services.review_responder_service import ReviewResponderService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["Review Responder"])


def _require_owned_location(db: Session, location_id: UUID, account_id: UUID) -> Location:
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == account_id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


def _owned_location_ids(db: Session, account_id: UUID) -> list[UUID]:
    return [
        location_id
        for (location_id,) in db.query(Location.id).filter(Location.account_id == account_id).all()
    ]


@router.post("/generate-response", response_model=ResponseDraft)
async def generate_review_response(
    request: GenerateResponseRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ResponseDraft:
    """
    Generate AI response draft for a review.

    Analyzes the review sentiment and intent, then generates an appropriate
    response following American business etiquette and best practices.
    """
    try:
        _require_owned_location(db, request.location_id, current_account.id)
        FeatureAccessService(db).check_feature_access(current_account, "ai_review_response")
        # Check rate limit
        await check_rate_limit(
            request=None, db=db, account_id=current_account.id, feature="review_responses"
        )

        service = ReviewResponderService(db)
        draft_result = await service.generate_response_draft_with_meta(request)
        if draft_result.used_ai_generation:
            record_rate_limit_usage(db, current_account.id, "review_responses")
        return draft_result.draft
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate review response",
        )


@router.post("/create-response", response_model=ReviewResponseResponse)
async def create_review_response(
    request: GenerateResponseRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ReviewResponseResponse:
    """
    Create a review response with AI draft and send for approval.

    This endpoint generates an AI response, saves it to the database,
    and sends a notification to the business owner for approval.
    """
    try:
        _require_owned_location(db, request.location_id, current_account.id)
        FeatureAccessService(db).check_feature_access(current_account, "ai_review_response")
        # Check rate limit
        await check_rate_limit(
            request=None, db=db, account_id=current_account.id, feature="review_responses"
        )

        service = ReviewResponderService(db)
        response, used_ai_generation = await service.create_review_response(
            request, current_account.id
        )
        if used_ai_generation:
            record_rate_limit_usage(db, current_account.id, "review_responses")
        return ReviewResponseResponse.model_validate(response)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create review response",
        )


@router.get("/pending", response_model=list[ReviewResponseHistoryItem])
async def get_pending_responses(
    location_id: Optional[UUID] = None,
    platform: Optional[str] = None,
    search: Optional[str] = None,
    high_priority_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> list[ReviewResponseHistoryItem]:
    """
    Get pending review responses awaiting approval.

    Returns a list of AI-generated responses that need to be reviewed
    and approved by the business owner before publication.
    """
    try:
        allowed_location_ids = _owned_location_ids(db, current_account.id)
        if location_id is not None and location_id not in allowed_location_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

        service = ReviewResponderService(db)
        responses = service.get_pending_responses(
            location_ids=[location_id] if location_id is not None else allowed_location_ids,
            platform=platform,
            search=search,
            high_priority_only=high_priority_only,
            limit=limit,
            offset=offset,
        )
        return responses
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pending responses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pending responses",
        )


@router.post("/{response_id}/approve", response_model=ReviewResponseResponse)
async def approve_response(
    response_id: int,
    request: ApproveResponseRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ReviewResponseResponse:
    """
    Approve a review response and publish it to the platform.

    The business owner can optionally edit the AI-generated draft before
    approval. Once approved, the response is published to Google Business Profile.
    """
    try:
        from app.models.review_response import ReviewResponse

        existing = db.query(ReviewResponse).filter(ReviewResponse.id == response_id).first()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response not found")
        _require_owned_location(db, existing.location_id, current_account.id)
        FeatureAccessService(db).check_feature_access(current_account, "ai_review_response")

        service = ReviewResponderService(db)
        response = await service.approve_response(
            response_id=response_id,
            account_id=current_account.id,
            edited_draft=request.edited_draft,
        )
        return ReviewResponseResponse.model_validate(response)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve response",
        )


@router.post("/{response_id}/reject", response_model=ReviewResponseResponse)
async def reject_response(
    response_id: int,
    request: RejectResponseRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ReviewResponseResponse:
    """
    Reject a review response.

    The business owner can reject the AI-generated response with a reason.
    This helps improve future AI responses through feedback.
    """
    try:
        from app.models.review_response import ReviewResponse

        existing = db.query(ReviewResponse).filter(ReviewResponse.id == response_id).first()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response not found")
        _require_owned_location(db, existing.location_id, current_account.id)
        FeatureAccessService(db).check_feature_access(current_account, "ai_review_response")

        service = ReviewResponderService(db)
        response = await service.reject_response(
            response_id=response_id, account_id=current_account.id, reason=request.reason
        )
        return ReviewResponseResponse.model_validate(response)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject response",
        )


@router.post("/{response_id}/retry", response_model=ReviewResponseResponse)
async def retry_response(
    response_id: int,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ReviewResponseResponse:
    """
    Retry publishing a failed review response.

    Only valid for responses with status 'failed'. Re-uses the existing
    approved draft and attempts a fresh publish to GBP. Returns the updated
    record — status will be 'published' on success or 'failed' with a new
    publish_error on failure. No other statuses are retryable.
    """
    try:
        from app.models.review_response import ReviewResponse

        existing = db.query(ReviewResponse).filter(ReviewResponse.id == response_id).first()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response not found")
        _require_owned_location(db, existing.location_id, current_account.id)

        service = ReviewResponderService(db)
        response = await service.retry_publish(
            response_id=response_id,
            account_id=current_account.id,
        )
        return ReviewResponseResponse.model_validate(response)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry response",
        )


@router.get("/summary", response_model=ReviewResponderSummaryResponse)
async def get_summary(
    location_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ReviewResponderSummaryResponse:
    """Get an operator summary for review responses."""
    allowed_location_ids = _owned_location_ids(db, current_account.id)
    if location_id is not None and location_id not in allowed_location_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    service = ReviewResponderService(db)
    return service.get_summary(
        location_ids=[location_id] if location_id is not None else allowed_location_ids,
        account_id=current_account.id,
    )


@router.get("/failed", response_model=FailedResponsesResponse)
async def get_failed_responses(
    location_id: Optional[UUID] = None,
    platform: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> FailedResponsesResponse:
    """
    Dedicated operational view of failed review response publishes.

    Returns only failed items, sorted most-recently-failed first, with
    error_category for quick triage. Use POST /reviews/bulk-retry to retry
    multiple items at once.
    """
    allowed_location_ids = _owned_location_ids(db, current_account.id)
    if location_id is not None and location_id not in allowed_location_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    service = ReviewResponderService(db)
    items, total, error_category_counts = service.get_failed_responses(
        location_ids=[location_id] if location_id is not None else allowed_location_ids,
        platform=platform,
        search=search,
        limit=limit,
        offset=offset,
    )
    return FailedResponsesResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        error_category_counts=error_category_counts,
    )


@router.post("/bulk-retry", response_model=BulkRetryResponse)
async def bulk_retry_responses(
    request: BulkRetryRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> BulkRetryResponse:
    """
    Bulk retry failed review response publishes.

    Silently skips items that are not found, not owned by this account, or
    not currently in 'failed' status. Returns a result for every input ID
    including skipped items so the caller can reconcile state.
    """
    allowed_location_ids = _owned_location_ids(db, current_account.id)
    service = ReviewResponderService(db)
    return await service.bulk_retry(
        response_ids=request.response_ids,
        allowed_location_ids=allowed_location_ids,
        account_id=current_account.id,
    )


@router.get("/history", response_model=ReviewResponseHistoryResponse)
async def get_history(
    location_id: Optional[UUID] = None,
    platform: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    high_priority_only: bool = False,
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ReviewResponseHistoryResponse:
    """Get paginated review response history for operators."""
    allowed_location_ids = _owned_location_ids(db, current_account.id)
    if location_id is not None and location_id not in allowed_location_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    service = ReviewResponderService(db)
    items, total = service.get_review_history(
        location_ids=[location_id] if location_id is not None else allowed_location_ids,
        platform=platform,
        status=status_filter,
        search=search,
        high_priority_only=high_priority_only,
        limit=limit,
        offset=offset,
    )
    return ReviewResponseHistoryResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/history/export")
async def export_history(
    location_id: Optional[UUID] = None,
    platform: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    high_priority_only: bool = False,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> Response:
    """Export review response history as CSV."""
    allowed_location_ids = _owned_location_ids(db, current_account.id)
    if location_id is not None and location_id not in allowed_location_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    service = ReviewResponderService(db)
    rows, headers = service.export_review_history_csv(
        location_ids=[location_id] if location_id is not None else allowed_location_ids,
        platform=platform,
        status=status_filter,
        search=search,
        high_priority_only=high_priority_only,
    )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)

    filename = "review-responder-history.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{response_id}", response_model=ReviewResponseHistoryItem)
async def get_response(
    response_id: int,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ReviewResponseHistoryItem:
    """
    Get a specific review response by ID.
    """
    from app.models.review_response import ReviewResponse

    response = db.query(ReviewResponse).filter(ReviewResponse.id == response_id).first()
    if not response:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response not found")
    location = (
        db.query(Location)
        .filter(Location.id == response.location_id, Location.account_id == current_account.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response not found")

    service = ReviewResponderService(db)
    return service._history_item(response)


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def review_webhook(
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    """
    Webhook endpoint for receiving new review notifications.

    This endpoint receives webhooks from Google Business Profile or other
    platforms when new reviews are posted, triggering automatic response
    generation.
    """
    try:
        from app.models.review_response import ReviewWebhook

        # Store webhook for processing
        webhook = ReviewWebhook(
            location_id=payload.get("location_id"),
            platform=payload.get("platform", "google"),
            event_type=payload.get("event_type", "new_review"),
            review_id=payload.get("review_id"),
            payload=str(payload),
            processed=0,
        )
        db.add(webhook)
        db.commit()

        return {"success": True, "message": "Webhook received and queued for processing"}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )
