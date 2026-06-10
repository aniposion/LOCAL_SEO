"""Analytics service for server-side event tracking."""
from datetime import datetime
import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.analytics_event import AnalyticsEvent

logger = logging.getLogger(__name__)

# P0: Core 8 events (확장 가능)
CORE_EVENTS = [
    "user_signed_up",
    "user_logged_in",
    "trial_started",
    "onboarding_step_completed",
    "audit_completed",
    "content_generated",
    "subscription_created",
    "payment_failed",
    "payment_recovered",
]


def track_event(
    user_id: UUID,
    event_name: str,
    properties: Optional[dict[str, Any]] = None,
    account_id: Optional[UUID] = None,
    session_id: Optional[str] = None,
    db: Optional[Session] = None
) -> AnalyticsEvent:
    """
    Track a server-side analytics event.
    
    CRITICAL: This is the single source of truth for all user actions.
    All events must go through this function for consistency.
    
    Args:
        user_id: User UUID (required)
        event_name: Event name (e.g., "audit_completed")
        properties: Event properties (e.g., {"score": 85, "location_id": "123"})
        account_id: Account UUID (optional)
        session_id: Session ID (optional)
        db: Database session (required if not in request context)
    
    Returns:
        AnalyticsEvent: Created event
    
    Example:
        track_event(
            user_id=user.id,
            event_name="audit_completed",
            properties={"location_id": location.id, "score": 85},
            account_id=account.id,
            db=db
        )
    """
    if not db:
        raise ValueError("Database session is required")
    
    # Ensure properties is a dict
    if properties is None:
        properties = {}
    
    # Add timestamp to properties
    properties["tracked_at"] = utc_now_naive().isoformat()
    
    # Create event
    event = AnalyticsEvent(
        user_id=user_id,
        account_id=account_id,
        session_id=session_id,
        event_name=event_name,
        properties=properties
    )
    
    db.add(event)
    db.flush()  # Get ID without committing
    
    logger.info(
        f"Event tracked: {event_name} user={user_id} "
        f"account={account_id} properties={properties}"
    )
    
    return event


def track_onboarding_step(
    user_id: UUID,
    step: str,
    db: Session,
    account_id: Optional[UUID] = None,
    additional_properties: Optional[dict] = None
) -> AnalyticsEvent:
    """
    Track onboarding step completion.
    
    Convenience function for onboarding events.
    """
    properties = {"step": step}
    if additional_properties:
        properties.update(additional_properties)
    
    return track_event(
        user_id=user_id,
        event_name="onboarding_step_completed",
        properties=properties,
        account_id=account_id,
        db=db
    )


def get_user_events(
    user_id: UUID,
    event_name: Optional[str] = None,
    limit: int = 100,
    db: Session = None
) -> list[AnalyticsEvent]:
    """Get events for a user."""
    if not db:
        raise ValueError("Database session is required")
    
    query = db.query(AnalyticsEvent).filter(AnalyticsEvent.user_id == user_id)
    
    if event_name:
        query = query.filter(AnalyticsEvent.event_name == event_name)
    
    return query.order_by(AnalyticsEvent.created_at.desc()).limit(limit).all()


def calculate_funnel(
    event_names: list[str],
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> dict[str, Any]:
    """
    Calculate funnel conversion rates.
    
    Args:
        event_names: List of event names in funnel order
        db: Database session
        start_date: Optional start date filter
        end_date: Optional end date filter
    
    Returns:
        dict with funnel data and conversion rates
    
    Example:
        calculate_funnel([
            "user_signed_up",
            "trial_started",
            "onboarding_step_completed",
            "subscription_created"
        ], db)
    """
    from sqlalchemy import func, distinct
    
    funnel_data = {}
    previous_count = None
    
    for event_name in event_names:
        query = db.query(func.count(distinct(AnalyticsEvent.user_id))).filter(
            AnalyticsEvent.event_name == event_name
        )
        
        if start_date:
            query = query.filter(AnalyticsEvent.created_at >= start_date)
        if end_date:
            query = query.filter(AnalyticsEvent.created_at <= end_date)
        
        count = query.scalar() or 0
        
        conversion_rate = None
        if previous_count and previous_count > 0:
            conversion_rate = (count / previous_count) * 100
        
        funnel_data[event_name] = {
            "count": count,
            "conversion_rate": conversion_rate
        }
        
        previous_count = count
    
    return funnel_data
