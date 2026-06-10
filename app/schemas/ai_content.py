"""P6: AI Content Generation schemas."""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ====================
# Content Generation
# ====================

class ContentGenerateRequest(BaseModel):
    """Request to generate AI content."""
    location_id: UUID
    
    # Content type
    content_type: Literal["post", "reply", "description", "faq"] = "post"
    
    # Context
    topic: Optional[str] = None  # Optional topic/theme
    occasion: Optional[str] = None  # Holiday, event, promotion
    keywords: list[str] = Field(default_factory=list)  # Keywords to include
    
    # Platform targeting
    platforms: list[str] = Field(default_factory=lambda: ["google"])
    
    # Tone override (uses vault default if not specified)
    tone: Optional[str] = None
    
    # Length preference
    length: Literal["short", "medium", "long"] = "medium"
    
    # Include CTA
    include_cta: bool = True
    cta_type: Optional[str] = None  # call, visit, book, order
    
    # Variations
    num_variations: int = Field(default=1, ge=1, le=5)
    
    # Language
    language: str = "en"


class GeneratedContent(BaseModel):
    """Single generated content item."""
    content: str
    platform: str
    
    # Analysis
    character_count: int
    word_count: int
    keywords_used: list[str]
    
    # Scores
    seo_score: int = Field(ge=0, le=100)
    readability_score: int = Field(ge=0, le=100)
    
    # Suggestions
    suggestions: list[str] = Field(default_factory=list)


class ContentGenerateResponse(BaseModel):
    """Response with generated content."""
    request_id: str
    location_id: UUID
    
    variations: list[GeneratedContent]
    
    # Generation metadata
    model_used: str
    tokens_used: int
    generation_time_ms: int
    
    created_at: datetime


# ====================
# Review Reply Generation
# ====================

class ReviewReplyRequest(BaseModel):
    """Request to generate review reply."""
    location_id: UUID
    
    # Review data
    reviewer_name: str
    star_rating: int = Field(ge=1, le=5)
    review_text: str
    
    # Reply preferences
    tone: Optional[str] = None  # grateful, professional, apologetic
    include_name: bool = True
    include_invitation: bool = True  # Invite to return
    
    # For negative reviews
    offer_resolution: bool = False
    resolution_type: Optional[str] = None  # refund, discount, contact


class ReviewReplyResponse(BaseModel):
    """Generated review reply."""
    reply: str
    
    # Analysis
    sentiment_detected: str  # positive, neutral, negative
    key_points_addressed: list[str]
    
    # Alternative replies
    alternatives: list[str] = Field(default_factory=list)
    
    model_used: str
    created_at: datetime


# ====================
# Content Analysis
# ====================

class ContentAnalyzeRequest(BaseModel):
    """Request to analyze content."""
    content: str
    location_id: Optional[UUID] = None  # For vault-based analysis
    
    # Analysis types
    check_seo: bool = True
    check_compliance: bool = True
    check_tone: bool = True
    check_readability: bool = True


class ComplianceIssue(BaseModel):
    """Content compliance issue."""
    type: str  # forbidden_phrase, exaggeration, misleading, legal_risk
    severity: Literal["low", "medium", "high"]
    text: str  # The problematic text
    suggestion: str  # Suggested fix
    position: Optional[int] = None  # Character position


class SEOAnalysis(BaseModel):
    """SEO analysis result."""
    score: int = Field(ge=0, le=100)
    
    keywords_found: list[str]
    keywords_missing: list[str]
    keyword_density: float
    
    has_cta: bool
    has_local_mention: bool
    
    suggestions: list[str]


class ToneAnalysis(BaseModel):
    """Tone analysis result."""
    detected_tone: str
    expected_tone: str
    match_score: int = Field(ge=0, le=100)
    
    issues: list[str]


class ReadabilityAnalysis(BaseModel):
    """Readability analysis result."""
    score: int = Field(ge=0, le=100)
    grade_level: str  # e.g., "8th grade"
    
    avg_sentence_length: float
    avg_word_length: float
    
    complex_words: list[str]
    suggestions: list[str]


class ContentAnalyzeResponse(BaseModel):
    """Content analysis response."""
    overall_score: int = Field(ge=0, le=100)
    is_safe_to_publish: bool
    needs_review: bool
    
    seo: Optional[SEOAnalysis] = None
    compliance: list[ComplianceIssue] = Field(default_factory=list)
    tone: Optional[ToneAnalysis] = None
    readability: Optional[ReadabilityAnalysis] = None
    
    # Auto-fix suggestion
    suggested_revision: Optional[str] = None
    
    analyzed_at: datetime


# ====================
# Bulk Generation
# ====================

class BulkGenerateRequest(BaseModel):
    """Request for bulk content generation."""
    location_id: UUID
    
    # Calendar period
    start_date: str  # YYYY-MM-DD
    end_date: str
    posts_per_week: int = Field(default=3, ge=1, le=7)
    
    # Content mix
    content_types: list[str] = Field(
        default_factory=lambda: ["promotional", "educational", "engagement", "seasonal"]
    )
    
    # Platforms
    platforms: list[str] = Field(default_factory=lambda: ["google", "instagram"])
    
    # Auto-schedule
    auto_schedule: bool = True
    preferred_times: list[str] = Field(
        default_factory=lambda: ["10:00", "14:00", "18:00"]
    )


class ScheduledPost(BaseModel):
    """Scheduled post from bulk generation."""
    content: str
    platform: str
    scheduled_for: datetime
    content_type: str
    
    seo_score: int
    status: str = "draft"  # draft, scheduled, needs_review


class BulkGenerateResponse(BaseModel):
    """Bulk generation response."""
    location_id: UUID
    
    posts: list[ScheduledPost]
    total_generated: int
    
    # Summary
    by_platform: dict[str, int]
    by_content_type: dict[str, int]
    
    created_at: datetime


# ====================
# Image Generation (Future)
# ====================

class ImageGenerateRequest(BaseModel):
    """Request to generate image."""
    location_id: UUID
    
    prompt: str
    style: Literal["photo", "illustration", "graphic"] = "photo"
    aspect_ratio: Literal["square", "landscape", "portrait"] = "square"
    
    # Brand colors
    use_brand_colors: bool = False


class ImageGenerateResponse(BaseModel):
    """Generated image response."""
    image_url: str
    prompt_used: str
    
    model_used: str
    created_at: datetime
