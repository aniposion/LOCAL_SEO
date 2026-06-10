"""Competitor Stealth Watch service."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.integrations.google_places import GooglePlacesClient
from app.integrations.llm import LLMAdapter
from app.models.competitor import Competitor, CompetitorAnalysis, CompetitorReview, CompetitorStatus
from app.models.location import Location
from app.schemas.competitor import (
    ActionItem,
    CompetitorAnalysisCreate,
    CompetitorCreate,
    CompetitorReviewCreate,
    CompetitorReportFreshness,
    WeeklyCompetitorReport,
)

logger = logging.getLogger(__name__)


@dataclass
class CompetitorAnalysisResult:
    """Internal competitor analysis result with usage metadata."""

    analysis: CompetitorAnalysis
    used_ai_generation: bool


class CompetitorService:
    """Service for competitor analysis and tracking."""

    def __init__(self, db: Session):
        """Initialize competitor service."""
        self.db = db
        self._places_client: GooglePlacesClient | None = None
        self._llm: LLMAdapter | None = None

    @property
    def places_client(self) -> GooglePlacesClient:
        if self._places_client is None:
            self._places_client = GooglePlacesClient()
        return self._places_client

    @property
    def llm(self) -> LLMAdapter:
        if self._llm is None:
            self._llm = LLMAdapter()
        return self._llm

    async def discover_competitors(
        self,
        location_id: UUID,
        radius_miles: float = 3.0,
        business_type: str = "restaurant",
        max_results: int = 3,
    ) -> list[Competitor]:
        """
        Discover competitors near a location using Google Places API.

        Args:
            location_id: User's location ID
            radius_miles: Search radius in miles
            business_type: Type of business to search
            max_results: Maximum number of competitors to return

        Returns:
            List of discovered competitors
        """
        # Get user's location
        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            raise ValueError(f"Location {location_id} not found")

        if not location.latitude or not location.longitude:
            raise ValueError(f"Location {location_id} has no coordinates")

        # Convert miles to meters
        radius_meters = int(radius_miles * 1609.34)

        # Search for nearby places
        places = await self.places_client.nearby_search(
            latitude=location.latitude,
            longitude=location.longitude,
            radius_meters=radius_meters,
            business_type=business_type,
            max_results=max_results * 2,  # Get more to filter
        )

        competitors = []
        for place in places[:max_results]:
            # Check if competitor already exists
            existing = (
                self.db.query(Competitor)
                .filter(Competitor.place_id == place.get("id"))
                .first()
            )

            if existing:
                # Update existing competitor
                existing.rating = place.get("rating", 0.0)
                existing.review_count = place.get("userRatingCount", 0)
                existing.last_synced_at = utc_now_naive()
                existing.raw_data = place
                self.db.commit()
                competitors.append(existing)
            else:
                # Calculate distance
                place_location = place.get("location", {})
                distance = self.places_client.calculate_distance(
                    location.latitude,
                    location.longitude,
                    place_location.get("latitude", 0),
                    place_location.get("longitude", 0),
                )

                # Create new competitor
                competitor_data = CompetitorCreate(
                    location_id=location_id,
                    place_id=place.get("id"),
                    name=place.get("displayName", {}).get("text", "Unknown"),
                    address=place.get("formattedAddress"),
                    business_type=business_type,
                    rating=place.get("rating", 0.0),
                    review_count=place.get("userRatingCount", 0),
                    distance_miles=distance,
                    raw_data=place,
                )

                competitor = Competitor(**competitor_data.model_dump())
                competitor.last_synced_at = utc_now_naive()
                self.db.add(competitor)
                self.db.commit()
                self.db.refresh(competitor)
                competitors.append(competitor)

        return competitors

    async def sync_competitor_reviews(
        self, competitor_id: int, max_reviews: int = 50
    ) -> list[CompetitorReview]:
        """
        Sync reviews for a competitor from Google Places API.

        Args:
            competitor_id: Competitor ID
            max_reviews: Maximum number of reviews to fetch

        Returns:
            List of synced reviews
        """
        competitor = self.db.query(Competitor).filter(Competitor.id == competitor_id).first()
        if not competitor:
            raise ValueError(f"Competitor {competitor_id} not found")

        # Fetch reviews from Google Places
        reviews_data = await self.places_client.get_place_reviews(
            competitor.place_id, max_reviews=max_reviews
        )

        synced_reviews = []
        for review_data in reviews_data:
            # Check if review already exists
            review_id = review_data.get("name", "").split("/")[-1]
            existing = (
                self.db.query(CompetitorReview)
                .filter(CompetitorReview.review_id == review_id)
                .first()
            )

            if not existing:
                # Parse publish time
                publish_time_str = review_data.get("publishTime")
                publish_time = None
                if publish_time_str:
                    try:
                        publish_time = datetime.fromisoformat(
                            publish_time_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

                # Create new review
                review = CompetitorReview(
                    competitor_id=competitor_id,
                    review_id=review_id,
                    author_name=review_data.get("authorAttribution", {}).get(
                        "displayName"
                    ),
                    rating=review_data.get("rating", 0),
                    text=review_data.get("text", {}).get("text"),
                    publish_time=publish_time,
                )
                self.db.add(review)
                synced_reviews.append(review)

        competitor.last_review_synced_at = utc_now_naive()
        self.db.add(competitor)
        self.db.commit()
        return synced_reviews

    def _minutes_since(self, timestamp: Optional[datetime]) -> Optional[int]:
        if not timestamp:
            return None
        now = utc_now_naive()
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(UTC).replace(tzinfo=None)
        delta = now - timestamp
        return max(int(delta.total_seconds() // 60), 0)

    def _build_freshness_summary(
        self,
        analysis: CompetitorAnalysis,
        competitors: list[Competitor],
        review_sample_size: int,
    ) -> CompetitorReportFreshness:
        last_analysis_at = analysis.created_at
        analysis_age_minutes = self._minutes_since(last_analysis_at)
        last_review_sync_at = max(
            [c.last_review_synced_at for c in competitors if c.last_review_synced_at],
            default=None,
        )
        last_review_sync_age_minutes = self._minutes_since(last_review_sync_at)

        freshness_notes: list[str] = []
        freshness_status = "fresh"

        if analysis_age_minutes is None:
            freshness_status = "attention"
            freshness_notes.append("No saved analysis timestamp is available.")
        elif analysis_age_minutes > 7 * 24 * 60:
            freshness_status = "stale"
            freshness_notes.append("Saved analysis is older than 7 days.")
        elif analysis_age_minutes > 3 * 24 * 60:
            freshness_status = "attention"
            freshness_notes.append("Saved analysis is more than 3 days old.")

        if last_review_sync_age_minutes is None:
            freshness_status = "stale" if freshness_status == "fresh" else freshness_status
            freshness_notes.append("No competitor review sync has been recorded yet.")
        elif last_review_sync_age_minutes > 14 * 24 * 60:
            freshness_status = "stale"
            freshness_notes.append("Competitor reviews were last synced more than 14 days ago.")
        elif last_review_sync_age_minutes > 7 * 24 * 60 and freshness_status != "stale":
            freshness_status = "attention"
            freshness_notes.append("Competitor reviews were last synced more than 7 days ago.")

        if review_sample_size == 0:
            freshness_status = "stale"
            freshness_notes.append("No synced competitor reviews were found in the analysis window.")
        elif review_sample_size < 10 and freshness_status == "fresh":
            freshness_status = "attention"
            freshness_notes.append("Review sample size is small.")

        if not freshness_notes:
            freshness_notes.append("Analysis and review sync timestamps are within the expected operating window.")

        return CompetitorReportFreshness(
            last_analysis_at=last_analysis_at,
            analysis_age_minutes=analysis_age_minutes,
            cache_age_minutes=analysis_age_minutes,
            last_review_sync_at=last_review_sync_at,
            last_review_sync_age_minutes=last_review_sync_age_minutes,
            review_sample_size=review_sample_size,
            freshness_status=freshness_status,
            freshness_notes=freshness_notes,
        )

    async def analyze_competitors_with_meta(
        self, location_id: UUID, force_refresh: bool = False
    ) -> CompetitorAnalysisResult:
        """
        Generate AI-powered competitor analysis.

        Args:
            location_id: User's location ID
            force_refresh: Force refresh even if cached

        Returns:
            Competitor analysis
        """
        # Check for cached analysis (within 7 days)
        if not force_refresh:
            week_ago = utc_now_naive() - timedelta(days=7)
            cached = (
                self.db.query(CompetitorAnalysis)
                .filter(
                    and_(
                        CompetitorAnalysis.location_id == location_id,
                        CompetitorAnalysis.created_at >= week_ago,
                    )
                )
                .order_by(desc(CompetitorAnalysis.created_at))
                .first()
            )
            if cached:
                logger.info(f"Returning cached analysis for location {location_id}")
                return CompetitorAnalysisResult(analysis=cached, used_ai_generation=False)

        # Get active competitors
        competitors = (
            self.db.query(Competitor)
            .filter(
                and_(
                    Competitor.location_id == location_id,
                    Competitor.status == CompetitorStatus.ACTIVE,
                )
            )
            .all()
        )

        if not competitors:
            raise ValueError(f"No active competitors found for location {location_id}")

        # Collect recent reviews (last 30 days)
        thirty_days_ago = utc_now_naive() - timedelta(days=30)
        all_reviews = []
        for competitor in competitors:
            reviews = (
                self.db.query(CompetitorReview)
                .filter(
                    and_(
                        CompetitorReview.competitor_id == competitor.id,
                        CompetitorReview.publish_time >= thirty_days_ago,
                    )
                )
                .all()
            )
            all_reviews.extend(reviews)

        # Prepare data for LLM analysis
        competitor_data = []
        for comp in competitors:
            comp_reviews = [r for r in all_reviews if r.competitor_id == comp.id]
            competitor_data.append(
                {
                    "name": comp.name,
                    "rating": comp.rating,
                    "review_count": comp.review_count,
                    "recent_reviews": [
                        {"rating": r.rating, "text": r.text} for r in comp_reviews[:10]
                    ],
                }
            )

        # Generate analysis with LLM
        analysis_prompt = self._build_analysis_prompt(competitor_data)
        analysis_result = await self.llm.generate(analysis_prompt)

        # Parse LLM response
        parsed = self._parse_analysis_response(analysis_result)

        # Create analysis record
        week_start = utc_now_naive() - timedelta(days=7)
        week_end = utc_now_naive()

        analysis_data = CompetitorAnalysisCreate(
            location_id=location_id,
            week_start=week_start,
            week_end=week_end,
            trending_keywords=parsed["trending_keywords"],
            threat_level=parsed["threat_level"],
            rating_trend=parsed["rating_trend"],
            recommended_actions=parsed["recommended_actions"],
            summary_text=parsed["summary_text"],
            metrics_snapshot={
                "competitors": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "rating": c.rating,
                        "review_count": c.review_count,
                    }
                    for c in competitors
                ]
            },
        )

        analysis = CompetitorAnalysis(**analysis_data.model_dump())
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)

        return CompetitorAnalysisResult(
            analysis=analysis,
            used_ai_generation=not parsed.get("used_fallback", False),
        )

    async def analyze_competitors(
        self, location_id: UUID, force_refresh: bool = False
    ) -> CompetitorAnalysis:
        """Generate competitor analysis for callers that only need the record."""
        result = await self.analyze_competitors_with_meta(location_id, force_refresh=force_refresh)
        return result.analysis

    def _build_analysis_prompt(self, competitor_data: list[dict[str, Any]]) -> str:
        """Build prompt for LLM analysis."""
        prompt = """You are a local business consultant analyzing competitor data. 

Analyze the following competitor information and provide insights:

"""
        for i, comp in enumerate(competitor_data, 1):
            prompt += f"\n**Competitor {i}: {comp['name']}**\n"
            prompt += f"- Rating: {comp['rating']}/5.0 ({comp['review_count']} reviews)\n"
            prompt += "- Recent Reviews:\n"
            for review in comp["recent_reviews"][:5]:
                if review["text"]:
                    prompt += f"  * [{review['rating']}★] {review['text'][:100]}...\n"

        prompt += """

Please provide:
1. **Trending Keywords**: Extract 5-7 keywords that frequently appear in competitor reviews (e.g., menu items, services, atmosphere)
2. **Threat Level**: Assess overall competitive threat (low/medium/high)
3. **Rating Trend**: Analyze if competitors are improving, declining, or stable
4. **Recommended Actions**: Provide 3 specific action items the business owner should take this week
5. **Summary**: Write a 2-3 sentence executive summary

Format your response as JSON:
{
  "trending_keywords": ["keyword1", "keyword2", ...],
  "threat_level": "medium",
  "rating_trend": "improving",
  "recommended_actions": [
    {"title": "Action 1", "description": "Details...", "priority": "high", "effort": "low"},
    {"title": "Action 2", "description": "Details...", "priority": "medium", "effort": "medium"},
    {"title": "Action 3", "description": "Details...", "priority": "low", "effort": "high"}
  ],
  "summary_text": "Executive summary..."
}
"""
        return prompt

    def _parse_analysis_response(self, response: str) -> dict[str, Any]:
        """Parse LLM analysis response."""
        import json

        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)

                # Convert action dicts to ActionItem objects
                actions = [ActionItem(**action) for action in data["recommended_actions"]]
                data["recommended_actions"] = actions
                data["used_fallback"] = False

                return data
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")

        # Fallback response
        return {
            "trending_keywords": ["quality", "service", "value"],
            "threat_level": "medium",
            "rating_trend": "stable",
            "recommended_actions": [
                ActionItem(
                    title="Monitor competitor reviews weekly",
                    description="Set up alerts for new competitor reviews",
                    priority="medium",
                    effort="low",
                )
            ],
            "summary_text": "Competitor analysis completed. Continue monitoring trends.",
            "used_fallback": True,
        }

    async def get_weekly_report(self, location_id: UUID) -> WeeklyCompetitorReport:
        """
        Get weekly competitor report.

        Args:
            location_id: User's location ID

        Returns:
            Weekly report with analysis
        """
        # Get latest analysis
        analysis = (
            self.db.query(CompetitorAnalysis)
            .filter(CompetitorAnalysis.location_id == location_id)
            .order_by(desc(CompetitorAnalysis.created_at))
            .first()
        )

        if not analysis:
            # Generate new analysis
            analysis = await self.analyze_competitors(location_id)

        # Get competitors
        competitors = (
            self.db.query(Competitor)
            .filter(
                and_(
                    Competitor.location_id == location_id,
                    Competitor.status == CompetitorStatus.ACTIVE,
                )
            )
            .all()
        )

        thirty_days_ago = utc_now_naive() - timedelta(days=30)
        review_sample_size = (
            self.db.query(CompetitorReview)
            .filter(
                and_(
                    CompetitorReview.competitor_id.in_([competitor.id for competitor in competitors]),
                    CompetitorReview.publish_time >= thirty_days_ago,
                )
            )
            .count()
            if competitors
            else 0
        )

        freshness = self._build_freshness_summary(analysis, competitors, review_sample_size)

        # Build report
        from app.schemas.competitor import CompetitorResponse

        report = WeeklyCompetitorReport(
            location_id=location_id,
            week_start=analysis.week_start,
            week_end=analysis.week_end,
            competitors=[CompetitorResponse.model_validate(c) for c in competitors],
            analysis=analysis,
            overall_threat_level=analysis.threat_level,
            key_insights=analysis.trending_keywords[:5],
            freshness=freshness,
        )

        return report
