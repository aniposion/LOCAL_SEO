"""
Brand Voice Service - Learning from feedback and applying to content generation.
P1 Priority Feature
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback import (
    BrandVoiceProfile,
    FeedbackAction,
    INDUSTRY_COMPLIANCE_PRESETS,
    PostFeedback,
    RejectionReasonCode,
)
from app.models.post import Post

logger = logging.getLogger(__name__)


class BrandVoiceService:
    """Service for brand voice learning and application."""

    def __init__(self, db: Session):
        self.db = db

    async def get_or_create_profile(self, location_id: UUID) -> BrandVoiceProfile:
        """Get or create brand voice profile for a location."""
        stmt = select(BrandVoiceProfile).where(
            BrandVoiceProfile.location_id == location_id
        )
        result = self.db.execute(stmt)
        profile = result.scalar_one_or_none()

        if not profile:
            profile = BrandVoiceProfile(
                location_id=location_id,
                preferred_terms=[],
                avoided_terms=[],
                tone_formal_level=5,  # Default: neutral
                compliance_rules={},
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)

        return profile

    async def learn_from_feedback(
        self,
        location_id: UUID,
        feedback: PostFeedback,
    ):
        """
        Learn brand voice preferences from post feedback.
        
        Args:
            location_id: Location UUID
            feedback: PostFeedback with rejection codes and edits
        """
        profile = await self.get_or_create_profile(location_id)

        # Learn from rejection reason codes
        if feedback.reason_codes:
            await self._learn_from_codes(profile, feedback.reason_codes)

        # Learn from edit diff
        if feedback.original_content and feedback.edited_content:
            await self._learn_from_diff(
                profile,
                feedback.original_content,
                feedback.edited_content,
            )

        # Update stats
        profile.feedback_count += 1
        profile.last_learned_at = datetime.now()

        # Mark feedback as learned
        feedback.learned = True
        feedback.learned_at = datetime.now()

        self.db.commit()
        logger.info(f"Learned from feedback for location {location_id}")

    async def _learn_from_codes(
        self,
        profile: BrandVoiceProfile,
        reason_codes: list[str],
    ):
        """Apply learnings from rejection reason codes."""
        
        for code in reason_codes:
            if code == "tone_too_formal":
                # Make tone more casual
                profile.tone_formal_level = max(1, profile.tone_formal_level - 1)
                
            elif code == "tone_too_casual":
                # Make tone more formal
                profile.tone_formal_level = min(10, profile.tone_formal_level + 1)
                
            elif code == "medical_claim":
                # Add compliance rule
                if not profile.compliance_rules:
                    profile.compliance_rules = {}
                profile.compliance_rules["no_medical_claims"] = True
                
                # Add common medical terms to avoided list
                medical_terms = ["효과", "치료", "완치", "개선", "보장"]
                profile.avoided_terms = list(
                    set((profile.avoided_terms or []) + medical_terms)
                )
                
            elif code == "price_mention":
                if not profile.compliance_rules:
                    profile.compliance_rules = {}
                profile.compliance_rules["no_price"] = True
                
            elif code == "too_long":
                if not profile.compliance_rules:
                    profile.compliance_rules = {}
                # Reduce max length if set, or set a default
                current_max = profile.compliance_rules.get("max_length", 1000)
                profile.compliance_rules["max_length"] = int(current_max * 0.8)
                
            elif code == "off_brand":
                # This requires specific terms from the edit diff
                pass
                
            # Update reason code usage count
            await self._increment_reason_code_usage(code)

    async def _learn_from_diff(
        self,
        profile: BrandVoiceProfile,
        original: dict,
        edited: dict,
    ):
        """Extract preferred/avoided terms from edit diff."""
        
        original_text = self._extract_text(original)
        edited_text = self._extract_text(edited)

        # Find removed terms (should avoid)
        removed = self._find_removed_terms(original_text, edited_text)
        if removed:
            profile.avoided_terms = list(
                set((profile.avoided_terms or []) + removed)
            )[:50]  # Limit to 50 terms

        # Find added terms (preferred)
        added = self._find_added_terms(original_text, edited_text)
        if added:
            profile.preferred_terms = list(
                set((profile.preferred_terms or []) + added)
            )[:50]

        # Clean up: remove terms that appear in both lists
        if profile.preferred_terms and profile.avoided_terms:
            profile.preferred_terms = [
                t for t in profile.preferred_terms
                if t not in profile.avoided_terms
            ]

    def _extract_text(self, content: dict) -> str:
        """Extract text from content dict."""
        parts = []
        if "title" in content:
            parts.append(content["title"])
        if "body" in content:
            parts.append(content["body"])
        if "caption" in content:
            parts.append(content["caption"])
        return " ".join(parts)

    def _find_removed_terms(
        self, original: str, edited: str
    ) -> list[str]:
        """Find significant terms that were removed."""
        original_words = set(original.lower().split())
        edited_words = set(edited.lower().split())
        
        removed = original_words - edited_words
        
        # Filter out common words and short words
        significant = [
            w for w in removed
            if len(w) >= 3 and w not in self._get_stop_words()
        ]
        
        return significant[:10]  # Limit per feedback

    def _find_added_terms(
        self, original: str, edited: str
    ) -> list[str]:
        """Find significant terms that were added."""
        original_words = set(original.lower().split())
        edited_words = set(edited.lower().split())
        
        added = edited_words - original_words
        
        significant = [
            w for w in added
            if len(w) >= 3 and w not in self._get_stop_words()
        ]
        
        return significant[:10]

    def _get_stop_words(self) -> set[str]:
        """Common words to ignore."""
        return {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "as", "is", "was", "are",
            "were", "been", "be", "have", "has", "had", "do", "does",
            "did", "will", "would", "could", "should", "may", "might",
            "이", "그", "저", "것", "수", "등", "및", "또는", "그리고",
        }

    async def _increment_reason_code_usage(self, code: str):
        """Increment usage count for rejection reason code."""
        stmt = select(RejectionReasonCode).where(RejectionReasonCode.code == code)
        result = self.db.execute(stmt)
        reason = result.scalar_one_or_none()
        
        if reason:
            reason.usage_count += 1

    async def apply_industry_preset(
        self,
        location_id: UUID,
        industry: str,
    ) -> BrandVoiceProfile:
        """Apply industry-specific compliance preset."""
        profile = await self.get_or_create_profile(location_id)
        
        preset = INDUSTRY_COMPLIANCE_PRESETS.get(
            industry.lower(),
            INDUSTRY_COMPLIANCE_PRESETS["default"]
        )

        # Merge preset with existing settings
        profile.industry = industry
        profile.industry_presets_applied = True

        # Compliance rules
        if not profile.compliance_rules:
            profile.compliance_rules = {}
        profile.compliance_rules.update({
            k: v for k, v in preset.items()
            if k not in ["avoided_terms", "preferred_terms"]
        })

        # Terms
        if "avoided_terms" in preset:
            profile.avoided_terms = list(
                set((profile.avoided_terms or []) + preset["avoided_terms"])
            )
        if "preferred_terms" in preset:
            profile.preferred_terms = list(
                set((profile.preferred_terms or []) + preset["preferred_terms"])
            )

        self.db.commit()
        self.db.refresh(profile)
        
        logger.info(f"Applied {industry} preset to location {location_id}")
        return profile

    async def generate_prompt_instructions(
        self, location_id: UUID
    ) -> str:
        """Generate prompt instructions from brand voice profile."""
        profile = await self.get_or_create_profile(location_id)
        return profile.to_prompt_instructions()

    async def apply_to_prompt(
        self,
        location_id: UUID,
        base_prompt: str,
    ) -> str:
        """
        Apply brand voice profile to content generation prompt.
        
        Args:
            location_id: Location UUID
            base_prompt: Original prompt
            
        Returns:
            Enhanced prompt with brand voice instructions
        """
        instructions = await self.generate_prompt_instructions(location_id)
        
        if not instructions:
            return base_prompt

        return f"""{base_prompt}

[브랜드 가이드라인]
{instructions}

위 가이드라인을 반드시 준수하세요."""

    async def record_feedback(
        self,
        post_id: UUID,
        action: FeedbackAction,
        reason_codes: list[str] | None = None,
        free_text: str | None = None,
        original_content: dict | None = None,
        edited_content: dict | None = None,
        created_by: UUID | None = None,
    ) -> PostFeedback:
        """
        Record post feedback for learning.
        
        Args:
            post_id: Post UUID
            action: Feedback action (approved, rejected, edited)
            reason_codes: List of rejection reason codes
            free_text: Free text comment
            original_content: Original content dict
            edited_content: Edited content dict
            created_by: User who gave feedback
            
        Returns:
            Created PostFeedback
        """
        # Calculate diff summary if content was edited
        diff_summary = None
        if original_content and edited_content:
            diff_summary = self._generate_diff_summary(
                original_content, edited_content
            )

        feedback = PostFeedback(
            post_id=post_id,
            action=action,
            reason_codes=reason_codes,
            free_text=free_text,
            original_content=original_content,
            edited_content=edited_content,
            diff_summary=diff_summary,
            created_by=created_by,
        )

        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)

        # Auto-learn if feedback includes useful data
        if reason_codes or (original_content and edited_content):
            post = self.db.get(Post, post_id)
            if post:
                await self.learn_from_feedback(post.location_id, feedback)

        return feedback

    def _generate_diff_summary(
        self, original: dict, edited: dict
    ) -> str:
        """Generate human-readable diff summary."""
        changes = []

        for key in set(list(original.keys()) + list(edited.keys())):
            orig_val = original.get(key, "")
            edit_val = edited.get(key, "")

            if orig_val != edit_val:
                if isinstance(orig_val, str) and isinstance(edit_val, str):
                    orig_len = len(orig_val)
                    edit_len = len(edit_val)
                    if edit_len < orig_len * 0.8:
                        changes.append(f"{key}: 줄임")
                    elif edit_len > orig_len * 1.2:
                        changes.append(f"{key}: 늘림")
                    else:
                        changes.append(f"{key}: 수정됨")
                else:
                    changes.append(f"{key}: 변경됨")

        return "; ".join(changes) if changes else "변경 없음"

    async def get_profile_stats(self, location_id: UUID) -> dict[str, Any]:
        """Get brand voice profile statistics."""
        profile = await self.get_or_create_profile(location_id)

        return {
            "feedback_count": profile.feedback_count,
            "tone_level": profile.tone_formal_level,
            "tone_description": profile.tone_description,
            "avoided_terms_count": len(profile.avoided_terms or []),
            "preferred_terms_count": len(profile.preferred_terms or []),
            "compliance_rules": profile.compliance_rules,
            "industry": profile.industry,
            "last_learned_at": profile.last_learned_at,
        }
