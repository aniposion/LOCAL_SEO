"""Onboarding service for new user audit and analysis."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.onboarding import AuditGrade, OnboardingAudit, OnboardingStatus

logger = logging.getLogger(__name__)


class PlacesSearchService:
    """Service for searching businesses via Google Places API."""

    PLACES_API_URL = "https://maps.googleapis.com/maps/api/place"

    def __init__(self):
        self.api_key = settings.gbp_api_key

    async def search_business(
        self,
        business_name: str,
        address: str,
    ) -> list[dict[str, Any]]:
        """
        Search for business candidates using Google Places API.
        Returns list of matching places.
        """
        if not self.api_key or settings.app_env == "dev":
            # Return mock data for development
            logger.info("Using mock data for business search (dev mode)")
            return self._get_mock_candidates(business_name, address)

        query = f"{business_name} {address}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Text Search API
            response = await client.get(
                f"{self.PLACES_API_URL}/textsearch/json",
                params={
                    "query": query,
                    "key": self.api_key,
                }
            )

            if response.status_code != 200:
                logger.error(f"Places API error: {response.text}")
                return []

            data = response.json()
            results = data.get("results", [])

            candidates = []
            for place in results[:5]:  # Top 5 candidates
                candidates.append({
                    "place_id": place.get("place_id"),
                    "name": place.get("name"),
                    "address": place.get("formatted_address"),
                    "rating": place.get("rating"),
                    "review_count": place.get("user_ratings_total", 0),
                    "types": place.get("types", []),
                    "location": place.get("geometry", {}).get("location", {}),
                    "photos": len(place.get("photos", [])),
                })

            return candidates

    async def get_place_details(self, place_id: str) -> dict[str, Any] | None:
        """Get detailed information for a specific place."""
        if not self.api_key or settings.app_env == "dev":
            # Return mock data for development
            logger.info("Using mock data for place details (dev mode)")
            return self._get_mock_place_details(place_id)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.PLACES_API_URL}/details/json",
                params={
                    "place_id": place_id,
                    "fields": ",".join([
                        "name", "formatted_address", "formatted_phone_number",
                        "website", "rating", "user_ratings_total", "reviews",
                        "photos", "opening_hours", "types", "geometry",
                        "business_status", "url"
                    ]),
                    "key": self.api_key,
                }
            )

            if response.status_code != 200:
                logger.error(f"Place Details API error: {response.text}")
                return None

            data = response.json()
            result = data.get("result", {})

            if not result:
                return None

            # Extract latest review date
            reviews = result.get("reviews", [])
            latest_review_date = None
            if reviews:
                # Reviews are sorted by time, first is most recent
                latest_review_time = reviews[0].get("time")
                if latest_review_time:
                    latest_review_date = datetime.fromtimestamp(
                        latest_review_time, tz=timezone.utc
                    )

            return {
                "place_id": place_id,
                "name": result.get("name"),
                "address": result.get("formatted_address"),
                "phone": result.get("formatted_phone_number"),
                "website": result.get("website"),
                "rating": result.get("rating"),
                "review_count": result.get("user_ratings_total", 0),
                "reviews": reviews[:5],  # Keep top 5 reviews
                "latest_review_date": latest_review_date,
                "photo_count": len(result.get("photos", [])),
                "has_hours": bool(result.get("opening_hours")),
                "types": result.get("types", []),
                "category": self._extract_category(result.get("types", [])),
                "location": result.get("geometry", {}).get("location", {}),
                "maps_url": result.get("url"),
            }

    async def search_competitors(
        self,
        latitude: float,
        longitude: float,
        category: str,
        radius: int = 5000,
    ) -> list[dict[str, Any]]:
        """Search for nearby competitors in the same category."""
        if not self.api_key or settings.app_env == "dev":
            # Return mock data for development
            logger.info("Using mock data for competitors (dev mode)")
            return self._get_mock_competitors(category)

        # Map category to Google Places type
        place_type = self._category_to_type(category)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.PLACES_API_URL}/nearbysearch/json",
                params={
                    "location": f"{latitude},{longitude}",
                    "radius": radius,
                    "type": place_type,
                    "key": self.api_key,
                }
            )

            if response.status_code != 200:
                logger.error(f"Nearby Search API error: {response.text}")
                return []

            data = response.json()
            results = data.get("results", [])

            competitors = []
            for place in results[:10]:  # Top 10 competitors
                competitors.append({
                    "place_id": place.get("place_id"),
                    "name": place.get("name"),
                    "rating": place.get("rating"),
                    "review_count": place.get("user_ratings_total", 0),
                    "address": place.get("vicinity"),
                })

            return competitors

    def _extract_category(self, types: list[str]) -> str:
        """Extract primary business category from types."""
        priority_types = [
            "restaurant", "cafe", "bar", "bakery",
            "spa", "beauty_salon", "hair_care",
            "dentist", "doctor", "hospital",
            "gym", "fitness_center",
            "car_repair", "car_wash",
            "store", "shopping_mall",
        ]

        for ptype in priority_types:
            if ptype in types:
                return ptype

        return types[0] if types else "business"

    def _category_to_type(self, category: str) -> str:
        """Convert category to Google Places type."""
        mapping = {
            "restaurant": "restaurant",
            "cafe": "cafe",
            "spa": "spa",
            "beauty_salon": "beauty_salon",
            "dentist": "dentist",
            "gym": "gym",
            "car_repair": "car_repair",
        }
        return mapping.get(category, "establishment")

    def _get_mock_candidates(self, business_name: str, address: str) -> list[dict[str, Any]]:
        """Return mock business candidates for development."""
        import uuid
        return [
            {
                "place_id": f"mock_place_{uuid.uuid4().hex[:8]}",
                "name": business_name,
                "address": address,
                "rating": 4.2,
                "review_count": 47,
                "types": ["cafe", "restaurant", "food"],
                "location": {"lat": 40.7128, "lng": -74.0060},
                "photos": 8,
            }
        ]

    def _get_mock_place_details(self, place_id: str) -> dict[str, Any]:
        """Return mock place details for development."""
        from datetime import timedelta
        return {
            "place_id": place_id,
            "name": "Test Business",
            "address": "123 Main Street, New York, NY 10001",
            "phone": "+1 (555) 123-4567",
            "website": "https://testbusiness.com",
            "rating": 4.2,
            "review_count": 47,
            "reviews": [
                {"author_name": "John D.", "rating": 5, "text": "Great service!", "time": int((datetime.now(timezone.utc) - timedelta(days=3)).timestamp())},
                {"author_name": "Jane S.", "rating": 4, "text": "Good experience", "time": int((datetime.now(timezone.utc) - timedelta(days=10)).timestamp())},
            ],
            "latest_review_date": datetime.now(timezone.utc) - timedelta(days=3),
            "photo_count": 8,
            "has_hours": True,
            "types": ["cafe", "restaurant", "food"],
            "category": "cafe",
            "location": {"lat": 40.7128, "lng": -74.0060},
            "maps_url": "https://maps.google.com/?cid=123456789",
        }

    def _get_mock_competitors(self, category: str) -> list[dict[str, Any]]:
        """Return mock competitors for development."""
        return [
            {"place_id": "comp_1", "name": "Competitor Coffee A", "rating": 4.5, "review_count": 120, "address": "456 Oak St"},
            {"place_id": "comp_2", "name": "Competitor Coffee B", "rating": 4.3, "review_count": 85, "address": "789 Pine St"},
            {"place_id": "comp_3", "name": "Competitor Coffee C", "rating": 4.1, "review_count": 62, "address": "321 Elm St"},
            {"place_id": "comp_4", "name": "Competitor Coffee D", "rating": 3.9, "review_count": 45, "address": "654 Maple St"},
            {"place_id": "comp_5", "name": "Competitor Coffee E", "rating": 4.0, "review_count": 38, "address": "987 Cedar St"},
        ]


class OnboardingAuditService:
    """Service for running onboarding audits."""

    def __init__(self, db: Session):
        self.db = db
        self.places_service = PlacesSearchService()

    async def start_onboarding(
        self,
        account_id: UUID,
        business_name: str,
        address: str,
        city: str | None = None,
        state: str | None = None,
        phone: str | None = None,
        website_url: str | None = None,
    ) -> OnboardingAudit:
        """
        Start the onboarding process for a new user.
        Returns the audit record (processing happens async).
        """
        # Create audit record
        audit = OnboardingAudit(
            account_id=account_id,
            business_name=business_name,
            address=address,
            city=city,
            state=state,
            phone=phone,
            website_url=website_url,
            status=OnboardingStatus.PENDING,
        )

        self.db.add(audit)
        self.db.commit()
        self.db.refresh(audit)

        return audit

    async def search_and_match_business(
        self,
        audit_id: UUID,
    ) -> list[dict[str, Any]]:
        """
        Search for business candidates and return options.
        If only one match, auto-select it.
        """
        audit = self.db.query(OnboardingAudit).filter(
            OnboardingAudit.id == audit_id
        ).first()

        if not audit:
            raise ValueError("Audit not found")

        audit.status = OnboardingStatus.SEARCHING
        audit.started_at = datetime.now(timezone.utc)
        self.db.commit()

        # Search for candidates
        full_address = f"{audit.address}"
        if audit.city:
            full_address += f", {audit.city}"
        if audit.state:
            full_address += f", {audit.state}"

        candidates = await self.places_service.search_business(
            audit.business_name,
            full_address,
        )

        audit.place_candidates = candidates

        if len(candidates) == 1:
            # Auto-select if only one match
            await self.select_business(audit_id, candidates[0]["place_id"])
        elif len(candidates) == 0:
            audit.status = OnboardingStatus.FAILED
            audit.error_message = "No matching business found on Google Maps"

        self.db.commit()
        return candidates

    async def select_business(
        self,
        audit_id: UUID,
        place_id: str,
    ) -> OnboardingAudit:
        """Select a specific business from candidates and run full analysis."""
        audit = self.db.query(OnboardingAudit).filter(
            OnboardingAudit.id == audit_id
        ).first()

        if not audit:
            raise ValueError("Audit not found")

        audit.place_id = place_id
        audit.status = OnboardingStatus.ANALYZING
        self.db.commit()

        # Get detailed place info
        details = await self.places_service.get_place_details(place_id)

        if not details:
            audit.status = OnboardingStatus.FAILED
            audit.error_message = "Failed to get business details"
            self.db.commit()
            return audit

        # Update audit with collected data
        audit.matched_name = details["name"]
        audit.matched_address = details["address"]
        audit.category = details["category"]
        audit.latitude = details["location"].get("lat")
        audit.longitude = details["location"].get("lng")

        audit.review_count = details["review_count"]
        audit.average_rating = details["rating"]
        audit.latest_review_date = details["latest_review_date"]
        audit.photo_count = details["photo_count"]
        audit.has_hours = details["has_hours"]
        audit.has_phone = bool(details["phone"])
        audit.has_website = bool(details["website"])

        # Search competitors
        if audit.latitude and audit.longitude:
            competitors = await self.places_service.search_competitors(
                audit.latitude,
                audit.longitude,
                audit.category,
            )

            # Filter out the business itself
            competitors = [
                c for c in competitors
                if c["place_id"] != place_id
            ][:5]

            audit.competitors_data = competitors
            audit.competitor_count = len(competitors)

            if competitors:
                audit.competitor_avg_reviews = sum(
                    c["review_count"] for c in competitors
                ) / len(competitors)
                audit.competitor_avg_rating = sum(
                    c["rating"] for c in competitors if c["rating"]
                ) / len([c for c in competitors if c["rating"]])

        # Check social presence (basic)
        audit.has_instagram = await self._check_instagram(audit.business_name)
        audit.has_facebook = await self._check_facebook(audit.business_name)
        audit.has_yelp = await self._check_yelp(audit.business_name, audit.city)

        # Calculate scores
        self._calculate_scores(audit)

        # Generate AI summary and recommendations
        self._generate_recommendations(audit)

        audit.status = OnboardingStatus.COMPLETED
        audit.completed_at = datetime.now(timezone.utc)
        self.db.commit()

        return audit

    def _calculate_scores(self, audit: OnboardingAudit) -> None:
        """Calculate all audit scores."""
        # Review Score (0-100)
        review_score = 0
        if audit.review_count:
            # Count score (max 40 points for 100+ reviews)
            count_score = min(audit.review_count / 100, 1.0) * 40

            # Rating score (max 40 points for 4.5+ rating)
            rating_score = 0
            if audit.average_rating:
                rating_score = (audit.average_rating / 5.0) * 40

            # Recency score (max 20 points)
            recency_score = 0
            if audit.latest_review_date:
                days_ago = (datetime.now(timezone.utc) - audit.latest_review_date).days
                if days_ago <= 7:
                    recency_score = 20
                elif days_ago <= 14:
                    recency_score = 15
                elif days_ago <= 30:
                    recency_score = 10
                elif days_ago <= 60:
                    recency_score = 5

            review_score = count_score + rating_score + recency_score

        audit.review_score = review_score

        # Activity Score (0-100)
        activity_score = 50  # Base score (no post data available via Places API)
        if audit.latest_post_date:
            days_since_post = (datetime.now(timezone.utc) - audit.latest_post_date).days
            if days_since_post <= 7:
                activity_score = 100
            elif days_since_post <= 14:
                activity_score = 80
            elif days_since_post <= 30:
                activity_score = 60
            elif days_since_post <= 60:
                activity_score = 40
            else:
                activity_score = 20

        audit.activity_score = activity_score

        # Completeness Score (0-100)
        completeness_score = 0
        if audit.has_phone:
            completeness_score += 20
        if audit.has_website:
            completeness_score += 20
        if audit.has_hours:
            completeness_score += 20
        if audit.photo_count >= 10:
            completeness_score += 25
        elif audit.photo_count >= 5:
            completeness_score += 15
        elif audit.photo_count >= 1:
            completeness_score += 5
        if audit.has_description:
            completeness_score += 15

        audit.completeness_score = completeness_score

        # Competition Score (0-100)
        competition_score = 50  # Default if no competitors
        if audit.competitor_avg_reviews and audit.competitor_avg_reviews > 0:
            review_ratio = audit.review_count / audit.competitor_avg_reviews
            competition_score = min(review_ratio * 50, 50)

            if audit.average_rating and audit.competitor_avg_rating:
                rating_ratio = audit.average_rating / audit.competitor_avg_rating
                competition_score += min(rating_ratio * 50, 50)

        audit.competition_score = competition_score

        # Total Score (weighted average)
        weights = {
            "review": 0.35,
            "activity": 0.20,
            "completeness": 0.20,
            "competition": 0.25,
        }

        total_score = (
            audit.review_score * weights["review"] +
            audit.activity_score * weights["activity"] +
            audit.completeness_score * weights["completeness"] +
            audit.competition_score * weights["competition"]
        )

        audit.total_score = round(total_score, 1)

        # Assign grade
        if total_score >= 90:
            audit.grade = AuditGrade.A_PLUS
        elif total_score >= 85:
            audit.grade = AuditGrade.A
        elif total_score >= 80:
            audit.grade = AuditGrade.B_PLUS
        elif total_score >= 75:
            audit.grade = AuditGrade.B
        elif total_score >= 70:
            audit.grade = AuditGrade.B_MINUS
        elif total_score >= 65:
            audit.grade = AuditGrade.C_PLUS
        elif total_score >= 60:
            audit.grade = AuditGrade.C
        elif total_score >= 50:
            audit.grade = AuditGrade.D
        else:
            audit.grade = AuditGrade.F

        # Estimate losses
        self._estimate_losses(audit)

    def _estimate_losses(self, audit: OnboardingAudit) -> None:
        """Estimate monthly losses based on gaps."""
        base_potential = 5000  # Max potential monthly revenue from GBP

        # Loss from low score
        score_loss = base_potential * (100 - audit.total_score) / 100

        # Additional loss from review gap
        review_gap = 0
        if audit.competitor_avg_reviews:
            review_gap = max(0, audit.competitor_avg_reviews - audit.review_count)
        review_loss = min(review_gap * 20, 1000)  # $20 per missing review, max $1000

        total_loss = score_loss + review_loss
        audit.estimated_monthly_loss = round(min(total_loss, 5000), 0)

        # Estimate missed calls (rough: $50 per call value)
        audit.estimated_missed_calls = int(audit.estimated_monthly_loss / 50)

    def _generate_recommendations(self, audit: OnboardingAudit) -> None:
        """Generate recommendations based on scores."""
        recommendations = []

        # Review recommendations
        if audit.review_count < 20:
            recommendations.append({
                "priority": 1,
                "category": "reviews",
                "status": "danger",
                "title": "Get More Reviews",
                "description": f"You have only {audit.review_count} reviews. Aim for at least 50 to compete effectively.",
                "action": "Set up automated review request emails after each service.",
            })
        elif audit.competitor_avg_reviews and audit.review_count < audit.competitor_avg_reviews:
            gap = int(audit.competitor_avg_reviews - audit.review_count)
            recommendations.append({
                "priority": 2,
                "category": "reviews",
                "status": "warning",
                "title": f"Close the Review Gap",
                "description": f"You're {gap} reviews behind your competitors' average.",
                "action": "Encourage happy customers to leave reviews.",
            })

        # Activity recommendations
        if audit.activity_score < 60:
            recommendations.append({
                "priority": 1,
                "category": "activity",
                "status": "danger",
                "title": "Post Regularly on Google",
                "description": "Your Google Business Profile appears inactive. This hurts your visibility.",
                "action": "Post at least 2 updates per week to stay visible.",
            })

        # Completeness recommendations
        if not audit.has_hours:
            recommendations.append({
                "priority": 2,
                "category": "completeness",
                "status": "warning",
                "title": "Add Business Hours",
                "description": "Customers can't see when you're open.",
                "action": "Update your business hours on Google Business Profile.",
            })

        if audit.photo_count < 10:
            recommendations.append({
                "priority": 2,
                "category": "completeness",
                "status": "warning",
                "title": "Add More Photos",
                "description": f"You have only {audit.photo_count} photos. Businesses with 10+ photos get more clicks.",
                "action": "Upload high-quality photos of your business, products, and team.",
            })

        # Social presence
        if not audit.has_instagram:
            recommendations.append({
                "priority": 3,
                "category": "social",
                "status": "info",
                "title": "Create Instagram Presence",
                "description": "Instagram can drive additional local traffic.",
                "action": "Set up an Instagram business account.",
            })

        audit.recommendations = recommendations

        # Generate summary
        issues = []
        if audit.review_score < 50:
            issues.append("reviews need improvement")
        if audit.activity_score < 60:
            issues.append("profile is inactive")
        if audit.completeness_score < 70:
            issues.append("profile information is incomplete")
        if audit.competition_score < 50:
            issues.append("falling behind competitors")

        if issues:
            audit.summary = f"Your Google Maps presence needs attention. Key issues: {', '.join(issues)}. With consistent effort, you can significantly improve your visibility and attract more customers."
        else:
            audit.summary = "Your Google Maps presence is in good shape! Focus on maintaining regular activity and encouraging more reviews to stay ahead of competitors."

        # Recommend plan
        if audit.total_score < 50:
            audit.recommended_plan = "pro"  # Needs more help
        elif audit.total_score < 70:
            audit.recommended_plan = "starter"
        else:
            audit.recommended_plan = "starter"  # Maintenance mode

    async def _check_instagram(self, business_name: str) -> bool:
        """Check if business has Instagram presence (basic check)."""
        # Simplified: would need Instagram API or scraping
        # For MVP, return None (unknown)
        return None

    async def _check_facebook(self, business_name: str) -> bool:
        """Check if business has Facebook presence."""
        return None

    async def _check_yelp(self, business_name: str, city: str | None) -> bool:
        """Check if business has Yelp presence."""
        return None

    async def get_audit_status(self, audit_id: UUID) -> dict[str, Any]:
        """Get current status of an audit."""
        audit = self.db.query(OnboardingAudit).filter(
            OnboardingAudit.id == audit_id
        ).first()

        if not audit:
            raise ValueError("Audit not found")

        response = {
            "audit_id": str(audit.id),
            "status": audit.status.value,
            "business_name": audit.business_name,
        }

        if audit.status == OnboardingStatus.SEARCHING:
            response["message"] = "Searching for your business on Google Maps..."
            response["progress"] = 25

        elif audit.status == OnboardingStatus.ANALYZING:
            response["message"] = "Analyzing your online presence..."
            response["progress"] = 60

        elif audit.status == OnboardingStatus.COMPLETED:
            response["message"] = "Analysis complete!"
            response["progress"] = 100
            response["result"] = audit.to_result_dict()

        elif audit.status == OnboardingStatus.FAILED:
            response["message"] = audit.error_message or "Analysis failed"
            response["progress"] = 0

        else:
            response["message"] = "Preparing analysis..."
            response["progress"] = 10

        # Add candidates if multiple matches found
        if audit.place_candidates and len(audit.place_candidates) > 1:
            response["candidates"] = audit.place_candidates
            response["needs_selection"] = True

        return response

    async def get_audit_result(self, account_id: UUID) -> OnboardingAudit | None:
        """Get completed audit result for an account."""
        return self.db.query(OnboardingAudit).filter(
            OnboardingAudit.account_id == account_id,
            OnboardingAudit.status == OnboardingStatus.COMPLETED,
        ).order_by(OnboardingAudit.created_at.desc()).first()
