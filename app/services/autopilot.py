"""
Autopilot Service - Automatic content calendar generation and scheduling.
P0 Priority Feature
"""

import logging
import re
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content_calendar import AutopilotSettings, ContentCalendar, ContentUsageHistory
from app.models.location import Location
from app.services.content import ContentService

logger = logging.getLogger(__name__)


# Seasonal/Event themes by month
SEASONAL_THEMES = {
    1: ["New Year", "Winter Wellness", "Fresh Start"],
    2: ["Valentine's Day", "Self-Care", "Winter Special"],
    3: ["Spring Renewal", "Spring Cleaning", "Fresh Beginnings"],
    4: ["Easter", "Spring Special", "Renewal"],
    5: ["Mother's Day", "Spring Finale", "Pre-Summer"],
    6: ["Summer Kickoff", "Father's Day", "Beach Ready"],
    7: ["Summer Special", "Independence Day", "Vacation Mode"],
    8: ["Back to School", "End of Summer", "Last Chance Summer"],
    9: ["Fall Preview", "Labor Day", "New Season"],
    10: ["Halloween", "Fall Special", "Cozy Season"],
    11: ["Thanksgiving", "Black Friday", "Holiday Prep"],
    12: ["Holiday Season", "Christmas", "Year End Special"],
}

SIMILARITY_STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "for",
    "in",
    "of",
    "on",
    "our",
    "the",
    "this",
    "to",
    "with",
    "your",
}


class AutopilotService:
    """Content autopilot service for automatic calendar generation."""

    def __init__(self, db: Session):
        self.db = db
        self.content_service = ContentService()

    async def generate_monthly_calendar(
        self,
        location_id: UUID,
        month: date,
        force_regenerate: bool = False,
    ) -> list[ContentCalendar]:
        """
        Generate monthly content calendar for a location.
        
        Args:
            location_id: Location UUID
            month: Target month (first day of month)
            force_regenerate: If True, regenerate even if exists
            
        Returns:
            List of ContentCalendar entries for the month
        """
        # Get location and settings
        location = self.db.get(Location, location_id)
        if not location:
            raise ValueError(f"Location {location_id} not found")

        settings = await self.get_autopilot_settings(location_id)
        if not settings or not settings.enabled:
            logger.info(f"Autopilot disabled for location {location_id}")
            return []

        # Check existing calendar
        month_start = date(month.year, month.month, 1)
        existing = await self.get_existing_calendar(location_id, month_start)
        if existing and not force_regenerate:
            logger.info(f"Calendar already exists for {month_start}")
            return existing

        # Get recent content for duplicate prevention
        recent_content = await self.get_recent_content(location_id, days=30)

        # Generate weekly entries
        weeks = self._get_weeks_in_month(month_start)
        calendar_entries = []

        for week_start in weeks:
            entry = await self._generate_week_entry(
                location=location,
                settings=settings,
                week_start=week_start,
                month_start=month_start,
                recent_content=recent_content,
            )
            calendar_entries.append(entry)

            # Add to recent content to prevent duplicates within same month
            recent_content.append({
                "content_type": "theme",
                "content_value": entry.theme,
                "used_at": datetime.now(),
            })

        # Save all entries
        for entry in calendar_entries:
            self.db.add(entry)
        self.db.commit()

        logger.info(f"Generated {len(calendar_entries)} calendar entries for {month_start}")
        return calendar_entries

    async def _generate_week_entry(
        self,
        location: Location,
        settings: AutopilotSettings,
        week_start: date,
        month_start: date,
        recent_content: list[dict],
    ) -> ContentCalendar:
        """Generate a single week's content plan."""
        
        # Select theme based on season/events
        theme = await self._select_theme(
            week_start=week_start,
            location=location,
            recent_content=recent_content,
            preferences=settings.theme_preferences,
        )

        # Generate offer and CTA
        offer = await self._generate_offer(theme, location)
        cta = await self._generate_cta(theme)

        # Generate image concept
        image_concept = await self._generate_image_concept(theme, location)

        return ContentCalendar(
            location_id=location.id,
            week_of=datetime.combine(week_start, datetime.min.time()),
            month_of=datetime.combine(month_start, datetime.min.time()),
            theme=theme,
            offer=offer,
            cta=cta,
            target_platforms=settings.platforms or ["GBP", "INSTAGRAM"],
            image_concept=image_concept,
            auto_generated=True,
            approved=settings.auto_approve,
        )

    async def _select_theme(
        self,
        week_start: date,
        location: Location,
        recent_content: list[dict],
        preferences: list[str] | None,
    ) -> str:
        """Select appropriate theme avoiding recent duplicates."""
        
        month = week_start.month
        seasonal_options = SEASONAL_THEMES.get(month, ["Special Offer"])

        recent_themes = [
            c for c in recent_content if c["content_type"] == "theme"
        ]

        available_themes = []
        for theme in seasonal_options:
            if not await self.check_similarity(theme, recent_themes, threshold=0.78):
                available_themes.append(theme)

        if not available_themes:
            # All themes used, pick least recent
            available_themes = seasonal_options

        # Prefer themes matching preferences
        if preferences:
            for theme in available_themes:
                theme_lower = theme.lower()
                for pref in preferences:
                    if pref.lower() in theme_lower:
                        return theme

        return available_themes[0]

    async def _generate_offer(self, theme: str, location: Location) -> str:
        """Generate offer text based on theme."""
        
        offers = {
            "New Year": "New Year Special: 15% OFF",
            "Valentine's Day": "Valentine's Special for You",
            "Summer": "Summer Special Deal",
            "Holiday": "Holiday Season Discount",
            "default": "This Week's Special",
        }

        for key, offer in offers.items():
            if key.lower() in theme.lower():
                return offer

        return offers["default"]

    async def _generate_cta(self, theme: str) -> str:
        """Generate CTA based on theme."""
        
        ctas = [
            "Book Now",
            "Reserve Today",
            "Get Your Spot",
            "Claim Offer",
            "Schedule Now",
        ]

        # Simple rotation based on theme hash
        index = hash(theme) % len(ctas)
        return ctas[index]

    async def _generate_image_concept(self, theme: str, location: Location) -> str:
        """Generate image concept for the week's content."""
        
        business_type = location.category or "business"
        
        return f"""Photorealistic {business_type} setting, {theme} theme.
Warm natural lighting, professional composition.
Clean and inviting atmosphere, focus on customer experience.
Style: Modern, welcoming, aspirational."""

    def _get_weeks_in_month(self, month_start: date) -> list[date]:
        """Get list of week start dates in a month."""
        
        weeks = []
        current = month_start

        # Find first Monday of or before month start
        while current.weekday() != 0:  # 0 = Monday
            current -= timedelta(days=1)

        # Collect all weeks that overlap with the month
        while current.month <= month_start.month or (
            current.month == 1 and month_start.month == 12
        ):
            if current.month == month_start.month or (
                current + timedelta(days=6)
            ).month == month_start.month:
                weeks.append(current)
            current += timedelta(days=7)

            if len(weeks) >= 5:  # Max 5 weeks per month
                break

        return weeks

    async def get_autopilot_settings(
        self, location_id: UUID
    ) -> AutopilotSettings | None:
        """Get autopilot settings for a location."""
        
        stmt = select(AutopilotSettings).where(
            AutopilotSettings.location_id == location_id
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_autopilot_settings(
        self,
        location_id: UUID,
        **kwargs,
    ) -> AutopilotSettings:
        """Update or create autopilot settings."""
        
        settings = await self.get_autopilot_settings(location_id)
        
        if not settings:
            settings = AutopilotSettings(location_id=location_id, **kwargs)
            self.db.add(settings)
        else:
            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)

        self.db.commit()
        self.db.refresh(settings)
        return settings

    async def get_existing_calendar(
        self, location_id: UUID, month_start: date
    ) -> list[ContentCalendar]:
        """Get existing calendar entries for a month."""
        
        month_end = date(
            month_start.year + (1 if month_start.month == 12 else 0),
            (month_start.month % 12) + 1,
            1
        )

        stmt = select(ContentCalendar).where(
            ContentCalendar.location_id == location_id,
            ContentCalendar.month_of >= datetime.combine(month_start, datetime.min.time()),
            ContentCalendar.month_of < datetime.combine(month_end, datetime.min.time()),
        )
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_content(
        self, location_id: UUID, days: int = 30
    ) -> list[dict]:
        """Get recently used content for duplicate prevention."""
        
        cutoff = datetime.now() - timedelta(days=days)

        stmt = select(ContentUsageHistory).where(
            ContentUsageHistory.location_id == location_id,
            ContentUsageHistory.used_at >= cutoff,
        )
        result = self.db.execute(stmt)
        
        return [
            {
                "content_type": r.content_type,
                "content_value": r.content_value,
                "used_at": r.used_at,
            }
            for r in result.scalars().all()
        ]

    async def record_content_usage(
        self,
        location_id: UUID,
        content_type: str,
        content_value: str,
        post_id: UUID | None = None,
    ):
        """Record content usage for duplicate prevention."""
        
        usage = ContentUsageHistory(
            location_id=location_id,
            content_type=content_type,
            content_value=content_value,
            post_id=post_id,
            used_at=datetime.now(),
        )
        self.db.add(usage)
        self.db.commit()

    async def check_similarity(
        self,
        content: str,
        recent_content: list[dict],
        threshold: float = 0.85,
    ) -> bool:
        """
        Check if content is too similar to recent content.

        Uses deterministic local similarity checks so duplicate prevention works
        without depending on an external embedding provider.
        """

        normalized_content = self._normalize_for_similarity(content)
        if not normalized_content:
            return False
        content_tokens = self._tokenize_for_similarity(normalized_content)
        content_bigrams = self._token_bigrams(content_tokens)
        
        for recent in recent_content:
            normalized_recent = self._normalize_for_similarity(recent.get("content_value", ""))
            if not normalized_recent:
                continue

            if normalized_content == normalized_recent:
                return True
            if normalized_content in normalized_recent or normalized_recent in normalized_content:
                return True

            recent_tokens = self._tokenize_for_similarity(normalized_recent)
            token_similarity = self._token_jaccard(content_tokens, recent_tokens)
            phrase_similarity = SequenceMatcher(None, normalized_content, normalized_recent).ratio()
            bigram_similarity = self._token_jaccard(content_bigrams, self._token_bigrams(recent_tokens))
            similarity = max(token_similarity, phrase_similarity, bigram_similarity)

            if similarity >= threshold:
                return True

        return False

    def _normalize_for_similarity(self, value: str) -> str:
        """Normalize text before local duplicate checks."""
        normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
        return re.sub(r"\s+", " ", normalized)

    def _tokenize_for_similarity(self, value: str) -> set[str]:
        """Tokenize content while ignoring low-signal stop words."""
        return {
            token
            for token in value.split()
            if len(token) > 1 and token not in SIMILARITY_STOP_WORDS
        }

    def _token_bigrams(self, tokens: set[str]) -> set[str]:
        """Build order-insensitive token bigrams for short phrase comparison."""
        ordered = sorted(tokens)
        return {
            f"{left} {right}"
            for left, right in zip(ordered, ordered[1:])
        }

    def _token_jaccard(self, left: set[str], right: set[str]) -> float:
        """Return Jaccard similarity for two token sets."""
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)
