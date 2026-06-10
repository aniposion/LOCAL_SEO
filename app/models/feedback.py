"""Feedback models for approval workflow and brand voice learning."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.location import Location
    from app.models.post import Post


class FeedbackAction(str, enum.Enum):
    """Post feedback action types."""
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    APPROVED_WITH_EDITS = "approved_with_edits"


class RejectionReasonCode(BaseModel):
    """Structured rejection reason codes."""

    __tablename__ = "rejection_reason_codes"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 'tone', 'compliance', 'brand', 'content'

    # Tracking
    usage_count: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<RejectionReasonCode {self.code}>"


# Default rejection reason codes
DEFAULT_REJECTION_CODES = [
    ("tone_too_formal", "톤이 너무 딱딱함", "더 친근한 톤으로 수정", "tone"),
    ("tone_too_casual", "톤이 너무 가벼움", "더 전문적인 톤으로 수정", "tone"),
    ("price_mention", "가격 언급 금지 위반", "직접적인 가격 언급 제거", "compliance"),
    ("medical_claim", "의학적 효과 주장", "'효과' 대신 '경험'으로 수정", "compliance"),
    ("too_long", "내용이 너무 김", "간결하게 줄이기", "content"),
    ("too_short", "내용이 너무 짧음", "더 상세하게 작성", "content"),
    ("weak_cta", "CTA가 약함", "행동 유도 문구 강화", "content"),
    ("off_brand", "브랜드와 맞지 않음", "브랜드 톤에 맞게 수정", "brand"),
    ("wrong_hashtags", "해시태그 부적절", "타겟 해시태그로 수정", "content"),
    ("factual_error", "사실 관계 오류", "정확한 정보로 수정", "content"),
    ("competitor_mention", "경쟁사 언급", "경쟁사 언급 제거", "compliance"),
]


class PostFeedback(BaseModel):
    """Post feedback for learning and improvement."""

    __tablename__ = "post_feedback"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        index=True,
    )

    # Feedback action
    action: Mapped[FeedbackAction] = mapped_column(
        Enum(FeedbackAction), nullable=False
    )

    # Rejection reasons (array of codes)
    reason_codes: Mapped[list | None] = mapped_column(
        ARRAY(String(50)), nullable=True
    )
    free_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Edit diff for learning
    original_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    edited_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Learning status
    learned: Mapped[bool] = mapped_column(Boolean, default=False)
    learned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Who gave feedback
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="feedbacks")

    def __repr__(self) -> str:
        return f"<PostFeedback {self.action.value} post={self.post_id}>"


class BrandVoiceProfile(BaseModel):
    """Brand voice profile for content generation tuning."""

    __tablename__ = "brand_voice_profiles"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # Preferred/avoided terms
    preferred_terms: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)
    avoided_terms: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)

    # Tone settings (1=casual, 10=formal)
    tone_formal_level: Mapped[int] = mapped_column(Integer, default=5)
    tone_keywords: Mapped[list | None] = mapped_column(ARRAY(Text), nullable=True)

    # Compliance rules
    compliance_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {
    #   "no_price": true,
    #   "no_medical_claims": true,
    #   "max_length": 500,
    #   "required_disclaimer": "...",
    #   "industry_restrictions": ["healthcare", "finance"]
    # }

    # Industry-specific settings
    industry: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry_presets_applied: Mapped[bool] = mapped_column(Boolean, default=False)

    # Learning stats
    feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    last_learned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="brand_voice_profile")

    def __repr__(self) -> str:
        return f"<BrandVoiceProfile location={self.location_id} tone={self.tone_formal_level}>"

    @property
    def tone_description(self) -> str:
        """Get human-readable tone description."""
        if self.tone_formal_level <= 3:
            return "매우 친근한"
        elif self.tone_formal_level <= 5:
            return "친근한"
        elif self.tone_formal_level <= 7:
            return "전문적인"
        else:
            return "매우 포멀한"

    def to_prompt_instructions(self) -> str:
        """Convert profile to prompt instructions."""
        instructions = []

        if self.avoided_terms:
            instructions.append(f"절대 사용하지 마: {', '.join(self.avoided_terms[:10])}")

        if self.preferred_terms:
            instructions.append(f"선호 표현: {', '.join(self.preferred_terms[:10])}")

        if self.compliance_rules:
            if self.compliance_rules.get("no_medical_claims"):
                instructions.append("의학적 효과 주장 금지. '효과' 대신 '경험' 사용")
            if self.compliance_rules.get("no_price"):
                instructions.append("가격 직접 언급 금지")
            if max_len := self.compliance_rules.get("max_length"):
                instructions.append(f"최대 {max_len}자 이내")

        instructions.append(f"톤: {self.tone_description}")

        return "\n".join(instructions)


# Industry-specific compliance presets
INDUSTRY_COMPLIANCE_PRESETS = {
    "healthcare": {
        "no_medical_claims": True,
        "disclaimer_required": True,
        "disclaimer_text": "개인차가 있을 수 있습니다.",
        "avoided_terms": ["치료", "완치", "효과", "보장"],
        "preferred_terms": ["경험", "케어", "관리", "도움"],
    },
    "spa": {
        "no_medical_claims": True,
        "avoided_terms": ["치료", "효과", "피부 개선"],
        "preferred_terms": ["릴렉싱", "경험", "케어", "힐링"],
    },
    "restaurant": {
        "no_price": False,
        "avoided_terms": ["최고", "최상", "넘버원"],
        "preferred_terms": ["신선한", "정성", "특별한"],
    },
    "fitness": {
        "no_medical_claims": True,
        "avoided_terms": ["다이어트", "살빠짐", "효과 보장"],
        "preferred_terms": ["건강", "활력", "에너지", "라이프스타일"],
    },
    "default": {
        "no_medical_claims": False,
        "no_price": False,
        "avoided_terms": [],
        "preferred_terms": [],
    },
}
