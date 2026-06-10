"""Tests for onboarding flow when Google Places is unavailable."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.onboarding import OnboardingStatus
from app.services.onboarding import (
    OnboardingAuditService,
    PlacesIntegrationUnavailableError,
    PlacesSearchService,
)


class TestOnboardingPlacesAvailability:
    """Tests for honest unavailable states in onboarding."""

    def test_places_search_raises_when_integration_is_unavailable(self) -> None:
        """Missing Places config should not fabricate business candidates."""
        service = PlacesSearchService()
        service.api_key = None

        with pytest.raises(PlacesIntegrationUnavailableError) as exc_info:
            asyncio.run(service.search_business("Test Business", "123 Main St"))

        assert "Google Places integration is unavailable." in str(exc_info.value)

    def test_onboarding_search_marks_audit_failed_when_places_are_unavailable(
        self,
        db: Session,
        test_user,
    ) -> None:
        """Onboarding search should fail honestly when Places is unavailable."""
        service = OnboardingAuditService(db)
        audit = asyncio.run(
            service.start_onboarding(
                account_id=test_user.id,
                business_name="Test Business",
                address="123 Main St",
                city="Test City",
                state="TS",
            )
        )

        service.places_service.api_key = None
        candidates = asyncio.run(service.search_and_match_business(audit.id))

        assert candidates == []
        db.refresh(audit)
        assert audit.status == OnboardingStatus.FAILED
        assert audit.error_message == "Google Places integration is unavailable."

    def test_onboarding_select_marks_audit_failed_when_place_details_are_unavailable(
        self,
        db: Session,
        test_user,
    ) -> None:
        """Manual selection should also surface a real unavailable state."""
        service = OnboardingAuditService(db)
        audit = asyncio.run(
            service.start_onboarding(
                account_id=test_user.id,
                business_name="Test Business",
                address="123 Main St",
            )
        )

        service.places_service.api_key = None
        updated = asyncio.run(service.select_business(audit.id, str(uuid4())))

        db.refresh(audit)
        assert updated.status == OnboardingStatus.FAILED
        assert audit.status == OnboardingStatus.FAILED
        assert audit.error_message == "Google Places integration is unavailable."
