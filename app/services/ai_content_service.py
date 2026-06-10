"""P6: AI Content Generation service using Gemini/OpenAI."""

import json
import logging
import time
from collections.abc import Callable
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now_aware
from app.core.user_messages import integration_unavailable, workflow_failed
from app.models.vault import EntityVault
from app.schemas.ai_content import (
    ContentGenerateRequest,
    ContentGenerateResponse,
    GeneratedContent,
    ReviewReplyRequest,
    ReviewReplyResponse,
    ContentAnalyzeRequest,
    ContentAnalyzeResponse,
    SEOAnalysis,
    ToneAnalysis,
    ReadabilityAnalysis,
    ComplianceIssue,
)

logger = logging.getLogger(__name__)


class AIContentUnavailableError(RuntimeError):
    """Raised when no real AI content provider is available."""


class AIContentService:
    """Service for AI-powered content generation and analysis.
    
    Uses Gemini (default) or OpenAI for:
    - Post generation (GBP, Instagram, Facebook)
    - Review reply generation
    - Content analysis (SEO, compliance, tone)
    - Bulk content calendar generation
    """

    def __init__(self, db: Session):
        self.db = db
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        
        # Initialize client based on provider
        if self.provider == "gemini":
            self._init_gemini()
        else:
            self._init_openai()

    def _init_gemini(self):
        """Initialize Gemini client."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            self.client = genai.GenerativeModel(self.model)
            logger.info(f"Initialized Gemini with model {self.model}")
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini: {e}")
            self.client = None

    def _init_openai(self):
        """Initialize OpenAI client."""
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            logger.info(f"Initialized OpenAI with model {self.model}")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI: {e}")
            self.client = None

    # ====================
    # Content Generation
    # ====================

    async def generate_content(
        self,
        request: ContentGenerateRequest,
    ) -> ContentGenerateResponse:
        """Generate AI content for posts."""
        start_time = time.time()
        
        # Get entity vault for context
        vault = await self._get_vault(request.location_id)
        
        # Build prompt
        prompt = self._build_generation_prompt(request, vault)
        
        # Generate content
        variations = []
        total_tokens = 0
        
        for i in range(request.num_variations):
            result = await self._call_llm(prompt)
            content = result["content"]
            total_tokens += result.get("tokens", 0)
            
            # Analyze generated content
            analysis = self._analyze_generated_content(content, vault, request.keywords)
            
            variations.append(GeneratedContent(
                content=content,
                platform=request.platforms[0] if request.platforms else "google",
                character_count=len(content),
                word_count=len(content.split()),
                keywords_used=analysis["keywords_used"],
                seo_score=analysis["seo_score"],
                readability_score=analysis["readability_score"],
                suggestions=analysis["suggestions"],
            ))
        
        generation_time = int((time.time() - start_time) * 1000)
        
        return ContentGenerateResponse(
            request_id=str(uuid4()),
            location_id=request.location_id,
            variations=variations,
            model_used=self.model,
            tokens_used=total_tokens,
            generation_time_ms=generation_time,
            created_at=utc_now_aware(),
        )

    def _build_generation_prompt(
        self,
        request: ContentGenerateRequest,
        vault: Optional[EntityVault],
    ) -> str:
        """Build prompt for content generation."""
        # Base context
        context = []
        
        if vault:
            context.append(f"Business: {vault.business_name}")
            if vault.description:
                context.append(f"About: {vault.description}")
            if vault.services:
                services = ", ".join([s.get("name", "") for s in vault.services[:5]])
                context.append(f"Services: {services}")
            if vault.city and vault.state:
                context.append(f"Location: {vault.city}, {vault.state}")
            if vault.tone:
                context.append(f"Brand tone: {vault.tone}")
            if vault.primary_keywords:
                context.append(f"Keywords to use: {', '.join(vault.primary_keywords[:5])}")
            if vault.forbidden_phrases:
                context.append(f"Avoid these phrases: {', '.join(vault.forbidden_phrases[:5])}")
        
        context_str = "\n".join(context)
        
        # Length guidance
        length_guide = {
            "short": "50-100 characters",
            "medium": "150-250 characters",
            "long": "300-500 characters",
        }
        
        # Build prompt
        prompt = f"""You are a local business marketing expert. Generate a social media post.

BUSINESS CONTEXT:
{context_str}

REQUIREMENTS:
- Content type: {request.content_type}
- Target platform: {', '.join(request.platforms)}
- Length: {length_guide.get(request.length, '150-250 characters')}
- Tone: {request.tone or (vault.tone if vault else 'professional_friendly')}
- Language: {request.language}
"""
        
        if request.topic:
            prompt += f"- Topic: {request.topic}\n"
        
        if request.occasion:
            prompt += f"- Occasion: {request.occasion}\n"
        
        if request.keywords:
            prompt += f"- Include keywords: {', '.join(request.keywords)}\n"
        
        if request.include_cta:
            cta_text = f"Include a {request.cta_type or 'visit/call'} call-to-action"
            prompt += f"- {cta_text}\n"
        
        prompt += """
OUTPUT:
Generate ONLY the post content. No explanations, no quotes, just the post text.
Make it engaging, authentic, and optimized for local SEO.
"""
        
        return prompt

    # ====================
    # Review Reply Generation
    # ====================

    async def generate_review_reply(
        self,
        request: ReviewReplyRequest,
    ) -> ReviewReplyResponse:
        """Generate AI reply for a review."""
        # Get entity vault
        vault = await self._get_vault(request.location_id)
        
        # Detect sentiment
        sentiment = self._detect_sentiment(request.review_text, request.star_rating)
        
        # Build prompt
        prompt = self._build_reply_prompt(request, vault, sentiment)
        
        # Generate main reply
        result = await self._call_llm(prompt)
        main_reply = result["content"]

        # Generate alternatives
        alternatives = []
        if request.star_rating <= 3:  # For negative reviews, offer alternatives
            alt_prompt = prompt + "\nGenerate a different style of reply."
            try:
                alt_result = await self._call_llm(alt_prompt)
                alternatives.append(alt_result["content"])
            except AIContentUnavailableError:
                logger.info(
                    "Alternative review reply generation unavailable for location %s",
                    request.location_id,
                )

        # Extract key points addressed
        key_points = self._extract_key_points(request.review_text, main_reply)
        
        return ReviewReplyResponse(
            reply=main_reply,
            sentiment_detected=sentiment,
            key_points_addressed=key_points,
            alternatives=alternatives,
            model_used=self.model,
            created_at=utc_now_aware(),
        )

    def _build_reply_prompt(
        self,
        request: ReviewReplyRequest,
        vault: Optional[EntityVault],
        sentiment: str,
    ) -> str:
        """Build prompt for review reply."""
        business_name = vault.business_name if vault else "Our business"
        tone = request.tone or (vault.tone if vault else "professional_friendly")
        
        prompt = f"""You are responding to a customer review for {business_name}.

REVIEW:
- Reviewer: {request.reviewer_name}
- Rating: {request.star_rating}/5 stars
- Review: "{request.review_text}"

DETECTED SENTIMENT: {sentiment}

REQUIREMENTS:
- Tone: {tone}
- {"Include the reviewer's name" if request.include_name else "Do not use reviewer's name"}
- {"Invite them to return" if request.include_invitation else ""}
"""
        
        if request.offer_resolution and request.star_rating <= 3:
            prompt += f"""
- Offer resolution: {request.resolution_type or 'contact us to discuss'}
- Be apologetic but not defensive
- Focus on making things right
"""
        
        if sentiment == "positive":
            prompt += """
- Express genuine gratitude
- Highlight something specific they mentioned
- Keep it warm but professional
"""
        
        prompt += """
OUTPUT:
Generate ONLY the reply text. Keep it concise (2-4 sentences).
Do not use generic phrases like "Thank you for your feedback."
Be specific and authentic.
"""
        
        return prompt

    def _detect_sentiment(self, text: str, rating: int) -> str:
        """Detect review sentiment."""
        if rating >= 4:
            return "positive"
        elif rating <= 2:
            return "negative"
        else:
            # Check text for sentiment indicators
            negative_words = ["bad", "terrible", "awful", "disappointed", "worst", "never"]
            positive_words = ["good", "great", "love", "excellent", "best", "amazing"]
            
            text_lower = text.lower()
            neg_count = sum(1 for w in negative_words if w in text_lower)
            pos_count = sum(1 for w in positive_words if w in text_lower)
            
            if neg_count > pos_count:
                return "negative"
            elif pos_count > neg_count:
                return "positive"
            return "neutral"

    def _extract_key_points(self, review: str, reply: str) -> list[str]:
        """Extract key points addressed in reply."""
        key_points = []
        
        # Simple extraction based on common patterns
        review_lower = review.lower()
        reply_lower = reply.lower()
        
        topics = {
            "service": ["service", "staff", "employee", "help"],
            "quality": ["quality", "product", "food", "work"],
            "price": ["price", "cost", "expensive", "cheap", "value"],
            "wait": ["wait", "time", "slow", "fast", "quick"],
            "location": ["location", "parking", "find", "access"],
        }
        
        for topic, keywords in topics.items():
            if any(k in review_lower for k in keywords):
                if any(k in reply_lower for k in keywords):
                    key_points.append(topic)
        
        return key_points

    # ====================
    # Content Analysis
    # ====================

    async def analyze_content(
        self,
        request: ContentAnalyzeRequest,
        before_revision: Callable[[], None] | None = None,
    ) -> ContentAnalyzeResponse:
        """Analyze content for SEO, compliance, tone, and readability."""
        vault = None
        if request.location_id:
            vault = await self._get_vault(request.location_id)
        
        results = {
            "seo": None,
            "compliance": [],
            "tone": None,
            "readability": None,
        }
        
        # SEO Analysis
        if request.check_seo:
            results["seo"] = self._analyze_seo(request.content, vault)
        
        # Compliance Analysis
        if request.check_compliance:
            results["compliance"] = self._analyze_compliance(request.content, vault)
        
        # Tone Analysis
        if request.check_tone:
            results["tone"] = self._analyze_tone(request.content, vault)
        
        # Readability Analysis
        if request.check_readability:
            results["readability"] = self._analyze_readability(request.content)
        
        # Calculate overall score
        scores = []
        if results["seo"]:
            scores.append(results["seo"].score)
        if results["tone"]:
            scores.append(results["tone"].match_score)
        if results["readability"]:
            scores.append(results["readability"].score)
        
        overall_score = int(sum(scores) / len(scores)) if scores else 50
        
        # Determine if safe to publish
        has_high_severity = any(
            c.severity == "high" for c in results["compliance"]
        )
        is_safe = overall_score >= 60 and not has_high_severity
        needs_review = overall_score < 70 or len(results["compliance"]) > 0
        
        # Generate suggested revision if needed
        suggested_revision = None
        if not is_safe and results["compliance"]:
            if before_revision is not None:
                before_revision()
            suggested_revision = await self._generate_revision(
                request.content, results["compliance"]
            )
        
        return ContentAnalyzeResponse(
            overall_score=overall_score,
            is_safe_to_publish=is_safe,
            needs_review=needs_review,
            seo=results["seo"],
            compliance=results["compliance"],
            tone=results["tone"],
            readability=results["readability"],
            suggested_revision=suggested_revision,
            analyzed_at=utc_now_aware(),
        )

    def _analyze_seo(self, content: str, vault: Optional[EntityVault]) -> SEOAnalysis:
        """Analyze content for SEO optimization."""
        content_lower = content.lower()
        words = content.split()
        
        # Get expected keywords from vault
        expected_keywords = []
        if vault:
            expected_keywords = (vault.primary_keywords or []) + (vault.local_keywords or [])
        
        # Find which keywords are present
        keywords_found = [k for k in expected_keywords if k.lower() in content_lower]
        keywords_missing = [k for k in expected_keywords if k.lower() not in content_lower]
        
        # Calculate keyword density
        keyword_count = sum(content_lower.count(k.lower()) for k in keywords_found)
        keyword_density = (keyword_count / len(words)) * 100 if words else 0
        
        # Check for CTA
        cta_phrases = ["call", "visit", "book", "contact", "order", "schedule", "learn more"]
        has_cta = any(phrase in content_lower for phrase in cta_phrases)
        
        # Check for local mention
        local_terms = []
        if vault and vault.city:
            local_terms.append(vault.city.lower())
        has_local = any(term in content_lower for term in local_terms)
        
        # Calculate score
        score = 50  # Base score
        if keywords_found:
            score += min(len(keywords_found) * 10, 30)
        if has_cta:
            score += 10
        if has_local:
            score += 10
        if 1 <= keyword_density <= 3:
            score += 10
        
        # Generate suggestions
        suggestions = []
        if not keywords_found and expected_keywords:
            suggestions.append(f"Include keywords: {', '.join(expected_keywords[:3])}")
        if not has_cta:
            suggestions.append("Add a call-to-action")
        if not has_local and vault and vault.city:
            suggestions.append(f"Mention your location ({vault.city})")
        
        return SEOAnalysis(
            score=min(score, 100),
            keywords_found=keywords_found,
            keywords_missing=keywords_missing[:5],
            keyword_density=round(keyword_density, 2),
            has_cta=has_cta,
            has_local_mention=has_local,
            suggestions=suggestions,
        )

    def _analyze_compliance(
        self, content: str, vault: Optional[EntityVault]
    ) -> list[ComplianceIssue]:
        """Analyze content for compliance issues."""
        issues = []
        content_lower = content.lower()
        
        # Check forbidden phrases from vault
        if vault and vault.forbidden_phrases:
            for phrase in vault.forbidden_phrases:
                if phrase.lower() in content_lower:
                    pos = content_lower.find(phrase.lower())
                    issues.append(ComplianceIssue(
                        type="forbidden_phrase",
                        severity="high",
                        text=phrase,
                        suggestion=f"Remove or replace '{phrase}'",
                        position=pos,
                    ))
        
        # Check common problematic phrases
        exaggerations = [
            ("best", "Consider using 'excellent' or 'top-rated'"),
            ("guaranteed", "Avoid absolute guarantees unless legally supported"),
            ("#1", "Use 'leading' or 'trusted' instead"),
            ("cheapest", "Use 'affordable' or 'competitive pricing'"),
            ("100%", "Avoid absolute percentages unless verified"),
        ]
        
        for phrase, suggestion in exaggerations:
            if phrase.lower() in content_lower:
                issues.append(ComplianceIssue(
                    type="exaggeration",
                    severity="medium",
                    text=phrase,
                    suggestion=suggestion,
                ))
        
        return issues

    def _analyze_tone(
        self, content: str, vault: Optional[EntityVault]
    ) -> ToneAnalysis:
        """Analyze content tone."""
        expected_tone = vault.tone if vault else "professional_friendly"
        
        # Simple tone detection based on word patterns
        content_lower = content.lower()
        
        tone_indicators = {
            "professional": ["pleased", "provide", "service", "quality", "ensure"],
            "casual": ["hey", "awesome", "cool", "check out", "!"],
            "friendly": ["welcome", "happy", "love", "enjoy", "thanks"],
            "luxurious": ["exclusive", "premium", "exceptional", "bespoke", "curated"],
            "expert": ["expertise", "specialized", "certified", "professional", "experience"],
        }
        
        detected_scores = {}
        for tone, indicators in tone_indicators.items():
            score = sum(1 for i in indicators if i in content_lower)
            detected_scores[tone] = score
        
        detected_tone = max(detected_scores, key=detected_scores.get)
        
        # Calculate match score
        match_score = 100 if detected_tone in expected_tone else 70
        
        issues = []
        if detected_tone not in expected_tone:
            issues.append(f"Content appears {detected_tone}, expected {expected_tone}")
        
        return ToneAnalysis(
            detected_tone=detected_tone,
            expected_tone=expected_tone,
            match_score=match_score,
            issues=issues,
        )

    def _analyze_readability(self, content: str) -> ReadabilityAnalysis:
        """Analyze content readability."""
        sentences = content.replace("!", ".").replace("?", ".").split(".")
        sentences = [s.strip() for s in sentences if s.strip()]
        
        words = content.split()
        
        # Calculate metrics
        avg_sentence_length = len(words) / len(sentences) if sentences else 0
        avg_word_length = sum(len(w) for w in words) / len(words) if words else 0
        
        # Find complex words (3+ syllables, simplified check)
        complex_words = [w for w in words if len(w) > 10]
        
        # Calculate readability score (simplified Flesch-Kincaid-like)
        score = 100 - (avg_sentence_length * 1.5) - (avg_word_length * 5)
        score = max(0, min(100, score))
        
        # Determine grade level
        if score >= 80:
            grade = "6th grade"
        elif score >= 60:
            grade = "8th grade"
        elif score >= 40:
            grade = "10th grade"
        else:
            grade = "College"
        
        suggestions = []
        if avg_sentence_length > 20:
            suggestions.append("Consider shorter sentences")
        if complex_words:
            suggestions.append(f"Simplify words: {', '.join(complex_words[:3])}")
        
        return ReadabilityAnalysis(
            score=int(score),
            grade_level=grade,
            avg_sentence_length=round(avg_sentence_length, 1),
            avg_word_length=round(avg_word_length, 1),
            complex_words=complex_words[:5],
            suggestions=suggestions,
        )

    async def _generate_revision(
        self, content: str, issues: list[ComplianceIssue]
    ) -> Optional[str]:
        """Generate revised content fixing compliance issues."""
        issue_list = "\n".join([
            f"- {i.type}: '{i.text}' - {i.suggestion}"
            for i in issues
        ])
        
        prompt = f"""Revise this content to fix compliance issues:

ORIGINAL:
{content}

ISSUES TO FIX:
{issue_list}

OUTPUT:
Provide ONLY the revised content. Maintain the original meaning and style.
"""

        try:
            result = await self._call_llm(prompt)
        except AIContentUnavailableError:
            logger.info("Revision generation unavailable because AI provider is unavailable")
            return None

        return result["content"]

    # ====================
    # Helper Methods
    # ====================

    async def _get_vault(self, location_id: UUID) -> Optional[EntityVault]:
        """Get entity vault for location."""
        result = self.db.execute(
            select(EntityVault).where(EntityVault.location_id == location_id)
        )
        return result.scalar_one_or_none()

    async def _call_llm(self, prompt: str) -> dict:
        """Call LLM provider."""
        if not self.client:
            raise AIContentUnavailableError(
                integration_unavailable(
                    "AI content generation",
                    "the AI provider is not configured",
                    "Connect an AI provider in Integrations and try again",
                )
            )
        
        try:
            if self.provider == "gemini":
                response = self.client.generate_content(prompt)
                content = (response.text or "").strip()
                if not content:
                    raise AIContentUnavailableError(
                        workflow_failed(
                            "AI content generation returned no content",
                            "Try again in a few minutes or check the provider configuration",
                        )
                    )
                return {
                    "content": content,
                    "tokens": len(prompt.split()) + len(content.split()),
                }
            else:
                # OpenAI
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500,
                )
                content = (response.choices[0].message.content or "").strip()
                if not content:
                    raise AIContentUnavailableError(
                        workflow_failed(
                            "AI content generation returned no content",
                            "Try again in a few minutes or check the provider configuration",
                        )
                    )
                return {
                    "content": content,
                    "tokens": response.usage.total_tokens,
                }
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            if isinstance(e, AIContentUnavailableError):
                raise
            raise AIContentUnavailableError(
                integration_unavailable(
                    "AI content generation",
                    "the AI provider is unavailable",
                    "Connect an AI provider in Integrations and try again",
                )
            ) from e

    def _analyze_generated_content(
        self, content: str, vault: Optional[EntityVault], keywords: list[str]
    ) -> dict:
        """Quick analysis of generated content."""
        content_lower = content.lower()
        
        # Check keywords
        all_keywords = keywords.copy()
        if vault and vault.primary_keywords:
            all_keywords.extend(vault.primary_keywords)
        
        keywords_used = [k for k in all_keywords if k.lower() in content_lower]
        
        # Simple scores
        seo_score = 60 + min(len(keywords_used) * 10, 40)
        
        words = content.split()
        readability_score = 80 if len(words) < 50 else 70
        
        suggestions = []
        if not keywords_used and all_keywords:
            suggestions.append(f"Consider adding: {all_keywords[0]}")
        
        return {
            "keywords_used": keywords_used,
            "seo_score": min(seo_score, 100),
            "readability_score": readability_score,
            "suggestions": suggestions,
        }


def get_ai_content_service(db: Session) -> AIContentService:
    """Get AI content service instance."""
    return AIContentService(db)
