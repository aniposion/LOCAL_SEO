"""
A/B Testing Service
Compare content performance and optimize posting strategies
"""
import random
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class TestStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TestMetric(str, Enum):
    ENGAGEMENT = "engagement"  # likes, comments, shares
    CLICKS = "clicks"          # CTA clicks
    CALLS = "calls"            # phone calls generated
    DIRECTIONS = "directions"  # direction requests
    CONVERSIONS = "conversions"  # bookings, orders


class VariantType(str, Enum):
    TITLE = "title"
    BODY = "body"
    IMAGE = "image"
    CTA = "cta"
    POSTING_TIME = "posting_time"
    HASHTAGS = "hashtags"


@dataclass
class TestVariant:
    """A/B test variant."""
    id: str
    name: str
    variant_type: VariantType
    content: dict  # varies by type
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    engagement_score: float = 0.0
    is_control: bool = False
    
    @property
    def click_rate(self) -> float:
        return (self.clicks / self.impressions * 100) if self.impressions > 0 else 0.0
    
    @property
    def conversion_rate(self) -> float:
        return (self.conversions / self.impressions * 100) if self.impressions > 0 else 0.0


@dataclass
class ABTest:
    """A/B test configuration and results."""
    id: str
    name: str
    description: str
    location_id: str
    test_type: VariantType
    primary_metric: TestMetric
    variants: list[TestVariant] = field(default_factory=list)
    status: TestStatus = TestStatus.DRAFT
    traffic_split: float = 50.0  # percentage for variant B
    min_sample_size: int = 100
    confidence_level: float = 95.0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    winner_variant_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def total_impressions(self) -> int:
        return sum(v.impressions for v in self.variants)
    
    @property
    def is_statistically_significant(self) -> bool:
        """Check if results are statistically significant."""
        if len(self.variants) < 2:
            return False
        
        # Simple check: need minimum sample size
        for v in self.variants:
            if v.impressions < self.min_sample_size:
                return False
        
        # In production, use proper statistical tests (chi-squared, t-test)
        return True
    
    def get_winning_variant(self) -> Optional[TestVariant]:
        """Get the winning variant based on primary metric."""
        if not self.is_statistically_significant:
            return None
        
        if self.primary_metric == TestMetric.CLICKS:
            return max(self.variants, key=lambda v: v.click_rate)
        elif self.primary_metric == TestMetric.CONVERSIONS:
            return max(self.variants, key=lambda v: v.conversion_rate)
        else:
            return max(self.variants, key=lambda v: v.engagement_score)


class ABTestingService:
    """Service for managing A/B tests."""
    
    def __init__(self):
        # In production, use database
        self._tests: dict[str, ABTest] = {}
    
    def create_test(
        self,
        name: str,
        description: str,
        location_id: str,
        test_type: VariantType,
        primary_metric: TestMetric,
        control_content: dict,
        variant_content: dict,
        traffic_split: float = 50.0,
        min_sample_size: int = 100,
    ) -> ABTest:
        """Create a new A/B test."""
        test_id = str(uuid4())
        
        control = TestVariant(
            id=f"{test_id}_control",
            name="Control (A)",
            variant_type=test_type,
            content=control_content,
            is_control=True,
        )
        
        variant = TestVariant(
            id=f"{test_id}_variant",
            name="Variant (B)",
            variant_type=test_type,
            content=variant_content,
            is_control=False,
        )
        
        test = ABTest(
            id=test_id,
            name=name,
            description=description,
            location_id=location_id,
            test_type=test_type,
            primary_metric=primary_metric,
            variants=[control, variant],
            traffic_split=traffic_split,
            min_sample_size=min_sample_size,
        )
        
        self._tests[test_id] = test
        return test
    
    def start_test(self, test_id: str) -> ABTest:
        """Start an A/B test."""
        test = self._tests.get(test_id)
        if not test:
            raise ValueError(f"Test {test_id} not found")
        
        test.status = TestStatus.RUNNING
        test.start_date = datetime.now()
        return test
    
    def pause_test(self, test_id: str) -> ABTest:
        """Pause an A/B test."""
        test = self._tests.get(test_id)
        if not test:
            raise ValueError(f"Test {test_id} not found")
        
        test.status = TestStatus.PAUSED
        return test
    
    def complete_test(self, test_id: str) -> ABTest:
        """Complete an A/B test and determine winner."""
        test = self._tests.get(test_id)
        if not test:
            raise ValueError(f"Test {test_id} not found")
        
        test.status = TestStatus.COMPLETED
        test.end_date = datetime.now()
        
        winner = test.get_winning_variant()
        if winner:
            test.winner_variant_id = winner.id
        
        return test

    def delete_test(self, test_id: str) -> bool:
        """Delete an A/B test from in-memory storage."""
        return self._tests.pop(test_id, None) is not None

    def clear_tests(self) -> None:
        """Clear all tests. Useful for isolated tests."""
        self._tests.clear()

    def record_impression(self, test_id: str, variant_id: str) -> None:
        """Record an impression for a variant."""
        test = self._tests.get(test_id)
        if not test:
            return
        
        for variant in test.variants:
            if variant.id == variant_id:
                variant.impressions += 1
                break
    
    def record_click(self, test_id: str, variant_id: str) -> None:
        """Record a click for a variant."""
        test = self._tests.get(test_id)
        if not test:
            return
        
        for variant in test.variants:
            if variant.id == variant_id:
                variant.clicks += 1
                break
    
    def record_conversion(self, test_id: str, variant_id: str) -> None:
        """Record a conversion for a variant."""
        test = self._tests.get(test_id)
        if not test:
            return
        
        for variant in test.variants:
            if variant.id == variant_id:
                variant.conversions += 1
                break
    
    def get_variant_for_user(self, test_id: str, user_id: str) -> Optional[TestVariant]:
        """Get the variant to show a user (consistent assignment)."""
        test = self._tests.get(test_id)
        if not test or test.status != TestStatus.RUNNING:
            return None
        
        # Use hash for consistent assignment
        hash_value = hash(f"{test_id}_{user_id}") % 100
        
        if hash_value < test.traffic_split:
            # Return variant B
            return next((v for v in test.variants if not v.is_control), None)
        else:
            # Return control A
            return next((v for v in test.variants if v.is_control), None)
    
    def get_test(self, test_id: str) -> Optional[ABTest]:
        """Get a test by ID."""
        return self._tests.get(test_id)
    
    def list_tests(
        self,
        location_id: Optional[str] = None,
        status: Optional[TestStatus] = None,
    ) -> list[ABTest]:
        """List all tests, optionally filtered."""
        tests = list(self._tests.values())
        
        if location_id:
            tests = [t for t in tests if t.location_id == location_id]
        
        if status:
            tests = [t for t in tests if t.status == status]
        
        return sorted(tests, key=lambda t: t.created_at, reverse=True)
    
    def get_test_results(self, test_id: str) -> dict:
        """Get detailed test results."""
        test = self._tests.get(test_id)
        if not test:
            return {}
        
        results = {
            "test_id": test.id,
            "name": test.name,
            "status": test.status,
            "total_impressions": test.total_impressions,
            "is_significant": test.is_statistically_significant,
            "variants": [],
        }
        
        for variant in test.variants:
            results["variants"].append({
                "id": variant.id,
                "name": variant.name,
                "is_control": variant.is_control,
                "impressions": variant.impressions,
                "clicks": variant.clicks,
                "conversions": variant.conversions,
                "click_rate": round(variant.click_rate, 2),
                "conversion_rate": round(variant.conversion_rate, 2),
                "engagement_score": round(variant.engagement_score, 2),
            })
        
        if test.winner_variant_id:
            results["winner"] = test.winner_variant_id
            winner = next((v for v in test.variants if v.id == test.winner_variant_id), None)
            if winner:
                control = next((v for v in test.variants if v.is_control), None)
                if control and control.click_rate > 0:
                    improvement = ((winner.click_rate - control.click_rate) / control.click_rate) * 100
                    results["improvement_percent"] = round(improvement, 1)
        
        return results
    
    def generate_test_suggestions(
        self,
        location_id: str,
        content_type: str,
    ) -> list[dict]:
        """Generate A/B test suggestions based on content type."""
        suggestions = []
        
        if content_type == "post":
            suggestions = [
                {
                    "type": VariantType.TITLE,
                    "name": "Urgency vs Standard Title",
                    "description": "Test if a more urgent title increases engagement",
                    "control": "Weekend Special: 20% Off",
                    "variant": "Weekend Special: Save 20% Today",
                },
                {
                    "type": VariantType.CTA,
                    "name": "CTA Button Text",
                    "description": "Test different call-to-action phrases",
                    "control": "Learn More",
                    "variant": "Book Now",
                },
                {
                    "type": VariantType.POSTING_TIME,
                    "name": "Morning vs Evening",
                    "description": "Test optimal posting time",
                    "control": "9:00 AM",
                    "variant": "6:00 PM",
                },
                {
                    "type": VariantType.IMAGE,
                    "name": "Food Close-up vs Ambiance",
                    "description": "Test which image style performs better",
                    "control": "Close-up food shot",
                    "variant": "Restaurant ambiance shot",
                },
            ]
        
        return suggestions


# Pre-built test templates
TEST_TEMPLATES = {
    "emoji_title": {
        "name": "Emoji in Title",
        "description": "Test if emojis increase engagement",
        "type": VariantType.TITLE,
        "metric": TestMetric.ENGAGEMENT,
    },
    "cta_button": {
        "name": "CTA Button Text",
        "description": "Test different call-to-action phrases",
        "type": VariantType.CTA,
        "metric": TestMetric.CLICKS,
    },
    "posting_time": {
        "name": "Posting Time",
        "description": "Find the optimal time to post",
        "type": VariantType.POSTING_TIME,
        "metric": TestMetric.ENGAGEMENT,
    },
    "image_style": {
        "name": "Image Style",
        "description": "Test different image styles",
        "type": VariantType.IMAGE,
        "metric": TestMetric.CLICKS,
    },
    "hashtag_count": {
        "name": "Hashtag Strategy",
        "description": "Test hashtag quantity and relevance",
        "type": VariantType.HASHTAGS,
        "metric": TestMetric.ENGAGEMENT,
    },
}
