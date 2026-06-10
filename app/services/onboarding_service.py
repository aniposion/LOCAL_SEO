"""Onboarding progress tracking service."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.onboarding import OnboardingProgress
from app.services.analytics_service import track_onboarding_step

logger = logging.getLogger(__name__)

# P0: 4 realistic steps (user can actually complete these)
ONBOARDING_STEPS = [
    "run_audit",           # Run first SEO audit
    "view_insights",       # View audit results
    "generate_content",    # Generate first AI content
    "generate_social_card" # Generate first social proof card
]


class OnboardingService:
    """Tracks completion of key onboarding and activation steps."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_progress(self, account_id: UUID) -> OnboardingProgress:
        """Get or create onboarding progress for an account."""
        progress = self.db.query(OnboardingProgress).filter(
            OnboardingProgress.account_id == account_id
        ).first()

        if not progress:
            progress = OnboardingProgress(
                account_id=account_id,
                completed_steps=0,
                total_steps=len(ONBOARDING_STEPS),
                current_step=ONBOARDING_STEPS[0],
                steps_data={},
            )
            self.db.add(progress)
            self.db.flush()

            logger.info("Created onboarding progress for account %s", account_id)

        return progress

    def complete_step(
        self,
        account_id: UUID,
        step: str,
        event_account_id: Optional[UUID] = None,
    ) -> OnboardingProgress:
        """Mark an onboarding step as completed."""
        if step not in ONBOARDING_STEPS:
            raise ValueError(f"Invalid step: {step}. Must be one of {ONBOARDING_STEPS}")

        progress = self.get_or_create_progress(account_id)

        if step in progress.steps_data and progress.steps_data[step]:
            logger.info("Step %s already completed for account %s", step, account_id)
            return progress

        steps_data = progress.steps_data or {}
        steps_data[step] = utc_now_naive().isoformat()
        progress.steps_data = steps_data
        progress.completed_steps = len([value for value in steps_data.values() if value])
        progress.current_step = self._get_next_step(steps_data)

        if progress.completed_steps >= progress.total_steps:
            progress.completed_at = utc_now_naive()
            logger.info("Account %s completed onboarding", account_id)

        self.db.add(progress)
        self.db.flush()

        track_onboarding_step(
            user_id=account_id,
            step=step,
            account_id=event_account_id or account_id,
            additional_properties={
                "completed_steps": progress.completed_steps,
                "total_steps": progress.total_steps,
                "is_completed": progress.is_completed,
            },
            db=self.db,
        )

        logger.info(
            "Step completed: %s for account %s. Progress: %s/%s",
            step,
            account_id,
            progress.completed_steps,
            progress.total_steps,
        )

        return progress

    def get_progress(self, account_id: UUID) -> dict:
        """Get onboarding progress payload for UI."""
        progress = self.get_or_create_progress(account_id)

        steps_status = []
        for step in ONBOARDING_STEPS:
            completed_at = progress.steps_data.get(step) if progress.steps_data else None
            steps_status.append({
                "step": step,
                "completed": bool(completed_at),
                "completed_at": completed_at,
            })

        return {
            "completed_steps": progress.completed_steps,
            "total_steps": progress.total_steps,
            "current_step": progress.current_step,
            "is_completed": progress.is_completed,
            "completion_percentage": progress.completion_percentage,
            "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
            "steps": steps_status,
        }

    def _get_next_step(self, steps_data: dict) -> Optional[str]:
        """Get the next incomplete step."""
        for step in ONBOARDING_STEPS:
            if step not in steps_data or not steps_data[step]:
                return step
        return None

    def calculate_time_to_activation(self, account_id: UUID) -> Optional[float]:
        """Calculate time-to-activation in minutes for an account."""
        progress = self.db.query(OnboardingProgress).filter(
            OnboardingProgress.account_id == account_id
        ).first()

        if not progress or not progress.completed_at:
            return None

        delta = progress.completed_at - progress.created_at
        return delta.total_seconds() / 60
