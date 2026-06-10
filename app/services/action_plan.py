"""
Action Plan Service - Generate actionable recommendations from SEO audit.
P0 Priority Feature
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.location import Location
from app.models.onboarding import OnboardingAudit
from app.models.recommendation import (
    EffortLevel,
    PerformanceTracking,
    Recommendation,
    RecommendationStatus,
    RecommendationType,
)

logger = logging.getLogger(__name__)


# Recommendation templates with expected impact
RECOMMENDATION_TEMPLATES = {
    RecommendationType.PHOTO_UPLOAD: {
        "title": "사진 {count}장 업로드",
        "description": "프로필 사진을 추가하면 고객의 신뢰도와 클릭률이 향상됩니다.",
        "impact_score": 75,
        "effort": EffortLevel.MEDIUM,
        "autopilot_possible": False,
        "expected_calls_lift": Decimal("8.0"),
        "expected_views_lift": Decimal("15.0"),
        "expected_directions_lift": Decimal("5.0"),
    },
    RecommendationType.POST_PUBLISH: {
        "title": "이번 주 포스트 {count}개 발행",
        "description": "정기적인 포스팅은 검색 노출과 고객 참여를 높입니다.",
        "impact_score": 85,
        "effort": EffortLevel.LOW,
        "autopilot_possible": True,
        "expected_calls_lift": Decimal("12.0"),
        "expected_views_lift": Decimal("20.0"),
        "expected_directions_lift": Decimal("8.0"),
    },
    RecommendationType.HOURS_UPDATE: {
        "title": "영업시간 업데이트",
        "description": "정확한 영업시간은 고객 경험과 신뢰도에 필수입니다.",
        "impact_score": 60,
        "effort": EffortLevel.LOW,
        "autopilot_possible": False,
        "expected_calls_lift": Decimal("5.0"),
        "expected_views_lift": Decimal("3.0"),
        "expected_directions_lift": Decimal("10.0"),
    },
    RecommendationType.CATEGORY_FIX: {
        "title": "카테고리 최적화",
        "description": "적합한 카테고리 설정으로 타겟 고객에게 더 잘 노출됩니다.",
        "impact_score": 70,
        "effort": EffortLevel.LOW,
        "autopilot_possible": False,
        "expected_calls_lift": Decimal("10.0"),
        "expected_views_lift": Decimal("18.0"),
        "expected_directions_lift": Decimal("7.0"),
    },
    RecommendationType.DESCRIPTION_UPDATE: {
        "title": "비즈니스 설명 개선",
        "description": "키워드가 포함된 매력적인 설명으로 전환율을 높입니다.",
        "impact_score": 65,
        "effort": EffortLevel.MEDIUM,
        "autopilot_possible": True,
        "expected_calls_lift": Decimal("6.0"),
        "expected_views_lift": Decimal("12.0"),
        "expected_directions_lift": Decimal("4.0"),
    },
    RecommendationType.REVIEW_RESPONSE: {
        "title": "미응답 리뷰 {count}개 답변",
        "description": "리뷰 답변은 고객 관계와 검색 순위에 긍정적 영향을 줍니다.",
        "impact_score": 80,
        "effort": EffortLevel.LOW,
        "autopilot_possible": True,
        "expected_calls_lift": Decimal("7.0"),
        "expected_views_lift": Decimal("10.0"),
        "expected_directions_lift": Decimal("5.0"),
    },
    RecommendationType.QA_RESPONSE: {
        "title": "Q&A 질문 {count}개 답변",
        "description": "Q&A 답변은 자주 묻는 질문에 대한 정보를 제공합니다.",
        "impact_score": 55,
        "effort": EffortLevel.LOW,
        "autopilot_possible": True,
        "expected_calls_lift": Decimal("3.0"),
        "expected_views_lift": Decimal("5.0"),
        "expected_directions_lift": Decimal("2.0"),
    },
}


class ActionPlanService:
    """Service for generating and managing action plans."""

    def __init__(self, db: Session):
        self.db = db

    async def generate_action_plan(
        self,
        location_id: UUID,
        audit_id: UUID | None = None,
        max_actions: int = 5,
    ) -> list[Recommendation]:
        """
        Generate action plan from audit results.
        
        Args:
            location_id: Location UUID
            audit_id: Optional audit UUID to base recommendations on
            max_actions: Maximum number of actions to recommend
            
        Returns:
            List of Recommendation objects
        """
        location = self.db.get(Location, location_id)
        if not location:
            raise ValueError(f"Location {location_id} not found")

        # Get audit if provided
        audit = None
        if audit_id:
            audit = self.db.get(OnboardingAudit, audit_id)

        # Analyze gaps and generate recommendations
        recommendations = []

        # Photo recommendations
        photo_rec = await self._check_photos(location, audit)
        if photo_rec:
            recommendations.append(photo_rec)

        # Post recommendations
        post_rec = await self._check_posts(location)
        if post_rec:
            recommendations.append(post_rec)

        # Hours recommendations
        hours_rec = await self._check_hours(location, audit)
        if hours_rec:
            recommendations.append(hours_rec)

        # Category recommendations
        category_rec = await self._check_category(location, audit)
        if category_rec:
            recommendations.append(category_rec)

        # Description recommendations
        desc_rec = await self._check_description(location, audit)
        if desc_rec:
            recommendations.append(desc_rec)

        # Review response recommendations
        review_rec = await self._check_reviews(location)
        if review_rec:
            recommendations.append(review_rec)

        # Sort by priority score and limit
        recommendations.sort(key=lambda r: r.priority_score, reverse=True)
        recommendations = recommendations[:max_actions]

        # Assign week
        current_week = datetime.now()
        for rec in recommendations:
            rec.location_id = location_id
            rec.audit_id = audit_id
            rec.week_of = current_week

        # Save recommendations
        for rec in recommendations:
            self.db.add(rec)
        self.db.commit()

        logger.info(f"Generated {len(recommendations)} recommendations for {location_id}")
        return recommendations

    async def _check_photos(
        self, location: Location, audit: OnboardingAudit | None
    ) -> Recommendation | None:
        """Check if photo upload is needed."""
        # Use audit data or default
        photo_count = 0
        if audit and audit.audit_result:
            photo_count = audit.audit_result.get("photo_count", 0)

        if photo_count < 10:
            needed = 10 - photo_count
            template = RECOMMENDATION_TEMPLATES[RecommendationType.PHOTO_UPLOAD]
            return Recommendation(
                type=RecommendationType.PHOTO_UPLOAD,
                title=template["title"].format(count=needed),
                description=template["description"],
                impact_score=template["impact_score"],
                effort=template["effort"],
                autopilot_possible=template["autopilot_possible"],
                expected_calls_lift=template["expected_calls_lift"],
                expected_views_lift=template["expected_views_lift"],
                expected_directions_lift=template["expected_directions_lift"],
            )
        return None

    async def _check_posts(self, location: Location) -> Recommendation | None:
        """Check if posting is needed."""
        # Check recent post count (last 7 days)
        # Simplified - always recommend posting
        template = RECOMMENDATION_TEMPLATES[RecommendationType.POST_PUBLISH]
        return Recommendation(
            type=RecommendationType.POST_PUBLISH,
            title=template["title"].format(count=2),
            description=template["description"],
            impact_score=template["impact_score"],
            effort=template["effort"],
            autopilot_possible=template["autopilot_possible"],
            expected_calls_lift=template["expected_calls_lift"],
            expected_views_lift=template["expected_views_lift"],
            expected_directions_lift=template["expected_directions_lift"],
        )

    async def _check_hours(
        self, location: Location, audit: OnboardingAudit | None
    ) -> Recommendation | None:
        """Check if hours update is needed."""
        has_hours = False
        if audit and audit.audit_result:
            has_hours = audit.audit_result.get("has_hours", False)

        if not has_hours:
            template = RECOMMENDATION_TEMPLATES[RecommendationType.HOURS_UPDATE]
            return Recommendation(
                type=RecommendationType.HOURS_UPDATE,
                title=template["title"],
                description=template["description"],
                impact_score=template["impact_score"],
                effort=template["effort"],
                autopilot_possible=template["autopilot_possible"],
                expected_calls_lift=template["expected_calls_lift"],
                expected_views_lift=template["expected_views_lift"],
                expected_directions_lift=template["expected_directions_lift"],
            )
        return None

    async def _check_category(
        self, location: Location, audit: OnboardingAudit | None
    ) -> Recommendation | None:
        """Check if category optimization is needed."""
        category_score = 100
        if audit and audit.audit_result:
            category_score = audit.audit_result.get("category_score", 100)

        if category_score < 80:
            template = RECOMMENDATION_TEMPLATES[RecommendationType.CATEGORY_FIX]
            return Recommendation(
                type=RecommendationType.CATEGORY_FIX,
                title=template["title"],
                description=template["description"],
                impact_score=template["impact_score"],
                effort=template["effort"],
                autopilot_possible=template["autopilot_possible"],
                expected_calls_lift=template["expected_calls_lift"],
                expected_views_lift=template["expected_views_lift"],
                expected_directions_lift=template["expected_directions_lift"],
            )
        return None

    async def _check_description(
        self, location: Location, audit: OnboardingAudit | None
    ) -> Recommendation | None:
        """Check if description update is needed."""
        has_description = bool(location.description)
        desc_length = len(location.description or "")

        if not has_description or desc_length < 100:
            template = RECOMMENDATION_TEMPLATES[RecommendationType.DESCRIPTION_UPDATE]
            return Recommendation(
                type=RecommendationType.DESCRIPTION_UPDATE,
                title=template["title"],
                description=template["description"],
                impact_score=template["impact_score"],
                effort=template["effort"],
                autopilot_possible=template["autopilot_possible"],
                expected_calls_lift=template["expected_calls_lift"],
                expected_views_lift=template["expected_views_lift"],
                expected_directions_lift=template["expected_directions_lift"],
            )
        return None

    async def _check_reviews(self, location: Location) -> Recommendation | None:
        """Check for unanswered reviews."""
        # Simplified - would need to check actual review data
        unanswered = 3  # Placeholder
        
        if unanswered > 0:
            template = RECOMMENDATION_TEMPLATES[RecommendationType.REVIEW_RESPONSE]
            return Recommendation(
                type=RecommendationType.REVIEW_RESPONSE,
                title=template["title"].format(count=unanswered),
                description=template["description"],
                impact_score=template["impact_score"],
                effort=template["effort"],
                autopilot_possible=template["autopilot_possible"],
                expected_calls_lift=template["expected_calls_lift"],
                expected_views_lift=template["expected_views_lift"],
                expected_directions_lift=template["expected_directions_lift"],
            )
        return None

    async def get_this_week_actions(
        self, location_id: UUID
    ) -> dict[str, list[Recommendation]]:
        """
        Get this week's actions split by auto/manual.
        
        Returns:
            {
                "auto": [...],  # Can be auto-executed
                "manual": [...],  # Requires user action
            }
        """
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())

        stmt = select(Recommendation).where(
            Recommendation.location_id == location_id,
            Recommendation.week_of >= week_start,
            Recommendation.status.in_([
                RecommendationStatus.PENDING,
                RecommendationStatus.IN_PROGRESS,
            ]),
        )
        result = self.db.execute(stmt)
        recommendations = list(result.scalars().all())

        return {
            "auto": [r for r in recommendations if r.autopilot_possible],
            "manual": [r for r in recommendations if not r.autopilot_possible],
        }

    async def get_expected_lift(
        self, location_id: UUID
    ) -> dict[str, Decimal]:
        """
        Calculate expected lift from pending recommendations.
        
        Returns:
            {
                "calls": 12.0,
                "views": 18.0,
                "directions": 5.0,
            }
        """
        actions = await self.get_this_week_actions(location_id)
        all_actions = actions["auto"] + actions["manual"]

        return {
            "calls": sum(
                r.expected_calls_lift or Decimal("0")
                for r in all_actions
            ),
            "views": sum(
                r.expected_views_lift or Decimal("0")
                for r in all_actions
            ),
            "directions": sum(
                r.expected_directions_lift or Decimal("0")
                for r in all_actions
            ),
        }

    async def mark_completed(
        self, recommendation_id: UUID
    ) -> Recommendation | None:
        """Mark a recommendation as completed."""
        rec = self.db.get(Recommendation, recommendation_id)
        if not rec:
            return None

        rec.status = RecommendationStatus.COMPLETED
        rec.completed_at = datetime.now()
        self.db.commit()
        self.db.refresh(rec)
        return rec

    async def skip_recommendation(
        self, recommendation_id: UUID
    ) -> Recommendation | None:
        """Skip a recommendation."""
        rec = self.db.get(Recommendation, recommendation_id)
        if not rec:
            return None

        rec.status = RecommendationStatus.SKIPPED
        self.db.commit()
        self.db.refresh(rec)
        return rec

    async def record_performance(
        self,
        location_id: UUID,
        calls: int | None = None,
        directions: int | None = None,
        views: int | None = None,
        reviews: int | None = None,
        avg_rating: Decimal | None = None,
    ) -> PerformanceTracking:
        """
        Record weekly performance metrics.
        
        Calculates week-over-week change automatically.
        """
        week_of = datetime.now()

        # Get previous week's data
        prev_week = week_of - timedelta(days=7)
        stmt = select(PerformanceTracking).where(
            PerformanceTracking.location_id == location_id,
            PerformanceTracking.week_of >= prev_week - timedelta(days=1),
            PerformanceTracking.week_of < prev_week + timedelta(days=1),
        )
        result = self.db.execute(stmt)
        prev = result.scalar_one_or_none()

        # Calculate changes
        calls_change = None
        views_change = None
        directions_change = None

        if prev:
            if prev.calls and calls:
                calls_change = Decimal(str(
                    ((calls - prev.calls) / prev.calls) * 100
                ))
            if prev.views and views:
                views_change = Decimal(str(
                    ((views - prev.views) / prev.views) * 100
                ))
            if prev.directions and directions:
                directions_change = Decimal(str(
                    ((directions - prev.directions) / prev.directions) * 100
                ))

        tracking = PerformanceTracking(
            location_id=location_id,
            week_of=week_of,
            calls=calls,
            directions=directions,
            views=views,
            reviews=reviews,
            avg_rating=avg_rating,
            calls_change=calls_change,
            views_change=views_change,
            directions_change=directions_change,
        )

        self.db.add(tracking)
        self.db.commit()
        self.db.refresh(tracking)
        return tracking

    async def get_roi_dashboard(
        self, location_id: UUID
    ) -> dict[str, Any]:
        """
        Get ROI dashboard data.
        
        Returns:
            {
                "expected_lift": {...},
                "actual_change": {...},
                "completed_actions": 5,
                "pending_actions": 3,
            }
        """
        expected = await self.get_expected_lift(location_id)

        # Get last 4 weeks performance
        four_weeks_ago = datetime.now() - timedelta(days=28)
        stmt = select(PerformanceTracking).where(
            PerformanceTracking.location_id == location_id,
            PerformanceTracking.week_of >= four_weeks_ago,
        ).order_by(PerformanceTracking.week_of.desc())
        result = self.db.execute(stmt)
        performance = list(result.scalars().all())

        actual_change = {
            "calls": Decimal("0"),
            "views": Decimal("0"),
            "directions": Decimal("0"),
        }
        if performance:
            latest = performance[0]
            actual_change = {
                "calls": latest.calls_change or Decimal("0"),
                "views": latest.views_change or Decimal("0"),
                "directions": latest.directions_change or Decimal("0"),
            }

        # Count actions
        stmt = select(func.count(Recommendation.id)).where(
            Recommendation.location_id == location_id,
            Recommendation.status == RecommendationStatus.COMPLETED,
        )
        completed = self.db.execute(stmt).scalar() or 0

        stmt = select(func.count(Recommendation.id)).where(
            Recommendation.location_id == location_id,
            Recommendation.status == RecommendationStatus.PENDING,
        )
        pending = self.db.execute(stmt).scalar() or 0

        return {
            "expected_lift": {
                "calls": float(expected["calls"]),
                "views": float(expected["views"]),
                "directions": float(expected["directions"]),
            },
            "actual_change": {
                "calls": float(actual_change["calls"]),
                "views": float(actual_change["views"]),
                "directions": float(actual_change["directions"]),
            },
            "completed_actions": completed,
            "pending_actions": pending,
            "performance_history": [
                {
                    "week": p.week_of.isoformat(),
                    "calls": p.calls,
                    "views": p.views,
                    "directions": p.directions,
                }
                for p in performance
            ],
        }
