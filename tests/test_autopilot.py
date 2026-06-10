from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.autopilot import AutopilotService


def _service() -> AutopilotService:
    return AutopilotService(db=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_check_similarity_normalizes_minor_copy_changes() -> None:
    service = _service()
    recent = [
        {
            "content_type": "theme",
            "content_value": "Summer Special Deal!",
            "used_at": datetime.now(UTC),
        }
    ]

    assert await service.check_similarity("summer special deal", recent)


@pytest.mark.asyncio
async def test_check_similarity_allows_distinct_themes() -> None:
    service = _service()
    recent = [
        {
            "content_type": "theme",
            "content_value": "Winter Wellness",
            "used_at": datetime.now(UTC),
        }
    ]

    assert not await service.check_similarity("Back to School", recent)


@pytest.mark.asyncio
async def test_select_theme_skips_recently_similar_theme() -> None:
    service = _service()
    location = SimpleNamespace(id=uuid4(), category="Cafe")
    recent = [
        {
            "content_type": "theme",
            "content_value": "Summer Kickoff",
            "used_at": datetime.now(UTC),
        }
    ]

    theme = await service._select_theme(
        week_start=date(2026, 6, 8),
        location=location,  # type: ignore[arg-type]
        recent_content=recent,
        preferences=None,
    )

    assert theme != "Summer Kickoff"
    assert theme == "Father's Day"
