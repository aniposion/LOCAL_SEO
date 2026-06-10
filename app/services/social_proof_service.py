"""Social proof card generation service."""

import io
import logging
from datetime import timedelta
from typing import Optional
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now_naive
from app.integrations.llm import LLMAdapter
from app.models.social_proof import SocialProofCard, SocialProofStatus
from app.schemas.social_proof import (
    AutoGenerateCardsRequest,
    GenerateCardRequest,
    SocialProofHistoryResponse,
    SocialProofCardCreate,
    SocialProofMetrics,
)
from app.services.notification import NotificationService
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


class SocialProofService:
    """Generate social proof cards from customer reviews."""

    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMAdapter()
        self.storage = StorageService()
        self.notification_service = NotificationService(db)

    async def generate_card(self, request: GenerateCardRequest) -> SocialProofCard:
        """Generate a single social proof card."""
        card_title = await self._extract_key_phrase(request.review_text)
        card_text = self._format_review_text(request.review_text, max_length=150)
        image_prompt = await self._generate_image_prompt(
            review_text=request.review_text,
            business_name=await self._get_business_name(request.location_id),
            custom_prompt=request.custom_prompt,
        )
        background_url = await self._generate_background_image(image_prompt)

        card_data = SocialProofCardCreate(
            location_id=request.location_id,
            review_id=request.review_id,
            review_author=request.review_author,
            review_rating=request.review_rating,
            review_text=request.review_text,
            review_date=request.review_date,
            card_title=card_title,
            card_text=card_text,
            image_prompt=image_prompt,
            layout_style=request.layout_style,
        )

        card = SocialProofCard(**card_data.model_dump())
        card.background_image_url = background_url
        card.status = SocialProofStatus.DRAFT
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)

        try:
            card.final_card_url = await self._compose_card(card)
            card.status = SocialProofStatus.PENDING
            self.db.commit()
            self.db.refresh(card)
            await self._send_approval_notification(card)
        except Exception as exc:
            logger.error("Error composing social proof card %s: %s", card.id, exc)
            card.status = SocialProofStatus.DRAFT
            self.db.commit()

        return card

    async def _extract_key_phrase(self, review_text: str) -> str:
        """Extract a concise title from a review."""
        prompt = f'''Extract the most impactful phrase from this review in at most 6 words.

Review: "{review_text}"

Return only the phrase.'''
        try:
            response = await self.llm.generate(prompt)
            return response.strip().strip('"').strip("'")[:50] or "Customer Favorite"
        except Exception as exc:
            logger.error("Error extracting key phrase: %s", exc)
            return "Customer Favorite"

    def _format_review_text(self, review_text: str, max_length: int = 150) -> str:
        """Trim review text for visual display."""
        text = review_text.strip()
        if len(text) <= max_length:
            return text

        trimmed = text[:max_length]
        last_period = trimmed.rfind('.')
        if last_period > 50:
            return trimmed[: last_period + 1]
        return trimmed.rsplit(' ', 1)[0] + '...'

    async def _generate_image_prompt(
        self,
        review_text: str,
        business_name: str,
        custom_prompt: Optional[str] = None,
    ) -> str:
        """Generate an image prompt for the card background."""
        if custom_prompt:
            return custom_prompt

        prompt = f'''Create a short image prompt in under 50 words for a social proof card background.

Business: {business_name}
Review: "{review_text}"

Focus on atmosphere, product quality, and an Instagram-ready commercial look.
Return only the prompt.'''
        try:
            response = await self.llm.generate(prompt)
            return response.strip()[:200]
        except Exception as exc:
            logger.error("Error generating image prompt: %s", exc)
            return f"Professional branded background for {business_name} with warm lighting"

    async def _generate_background_image(self, prompt: str) -> Optional[str]:
        """Generate and upload a background image when image generation is available."""
        try:
            import google.genai as genai

            client = genai.Client(api_key=settings.gemini_api_key)
            response = client.models.generate_images(
                model="imagen-3.0-generate-001",
                prompt=prompt,
                number_of_images=1,
                aspect_ratio="1:1",
                safety_filter_level="block_some",
            )

            if not response.generated_images:
                return None

            image_data = response.generated_images[0]._image_bytes
            filename = f"social_proof/bg_{utc_now_naive().timestamp()}.png"
            return await self.storage.upload_bytes(
                file_bytes=image_data,
                filename=filename,
                content_type="image/png",
            )
        except Exception as exc:
            logger.warning("Image generation unavailable, using local background: %s", exc)
            return None

    async def _compose_card(self, card: SocialProofCard) -> str:
        """Compose a final social proof card image."""
        bg_image = await self._load_background_image(card)
        overlay = Image.new("RGBA", bg_image.size, (0, 0, 0, 180))
        bg_image = bg_image.convert("RGBA")
        bg_image = Image.alpha_composite(bg_image, overlay)
        draw = ImageDraw.Draw(bg_image)

        title_font, text_font, author_font, small_font = self._load_fonts()

        draw.text((100, 150), '"', fill=card.text_color, font=title_font)

        if card.card_title:
            self._draw_multiline_text(
                draw=draw,
                text=card.card_title,
                position=(540, 250),
                font=title_font,
                fill=card.text_color,
                max_width=880,
                align="center",
            )

        self._draw_multiline_text(
            draw=draw,
            text=card.card_text or card.review_text,
            position=(540, 450),
            font=text_font,
            fill=card.text_color,
            max_width=880,
            align="center",
        )

        stars = '*' * max(1, min(card.review_rating, 5))
        draw.text((540, 750), stars, fill="#FFD700", font=text_font, anchor="mm")

        author_text = f"- {card.review_author or 'Customer'}"
        draw.text((540, 850), author_text, fill=card.text_color, font=author_font, anchor="mm")

        business_name = await self._get_business_name(card.location_id)
        footer_text = f"Google Review | {business_name}"
        draw.text((540, 950), footer_text, fill=card.text_color, font=small_font, anchor="mm")

        disclaimer = "Generated by AI - Subject to human review"
        draw.text((540, 1020), disclaimer, fill="#888888", font=small_font, anchor="mm")

        bg_image = bg_image.convert("RGB")
        output = io.BytesIO()
        bg_image.save(output, format="PNG", quality=95)
        output.seek(0)

        filename = f"social_proof/card_{card.id}_{utc_now_naive().timestamp()}.png"
        return await self.storage.upload_bytes(
            file_bytes=output.getvalue(),
            filename=filename,
            content_type="image/png",
        )

    async def _load_background_image(self, card: SocialProofCard) -> Image.Image:
        """Load remote background image or create a local fallback."""
        if not card.background_image_url:
            return Image.new("RGB", (1080, 1080), color=card.background_color)

        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(card.background_image_url)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content))
                if image.size != (1080, 1080):
                    image = image.resize((1080, 1080), Image.Resampling.LANCZOS)
                return image.convert("RGB")
        except Exception as exc:
            logger.warning("Could not load background image for card %s: %s", card.id, exc)
            return Image.new("RGB", (1080, 1080), color=card.background_color)

    def _load_fonts(self):
        """Load fonts with safe fallback."""
        try:
            return (
                ImageFont.truetype("arial.ttf", 72),
                ImageFont.truetype("arial.ttf", 48),
                ImageFont.truetype("arial.ttf", 36),
                ImageFont.truetype("arial.ttf", 24),
            )
        except Exception:
            return (
                ImageFont.load_default(),
                ImageFont.load_default(),
                ImageFont.load_default(),
                ImageFont.load_default(),
            )

    def _draw_multiline_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        position: tuple[int, int],
        font,
        fill: str,
        max_width: int,
        align: str = "center",
    ) -> None:
        """Draw wrapped multiline text."""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        y = position[1]
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_height = bbox[3] - bbox[1]
            if align == "center":
                draw.text((position[0], y), line, fill=fill, font=font, anchor="mm")
            else:
                draw.text((position[0], y), line, fill=fill, font=font)
            y += line_height + 10

    async def _get_business_name(self, location_id: UUID) -> str:
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == location_id).first()
        return location.business_name if location else "Our Business"

    async def _send_approval_notification(self, card: SocialProofCard) -> None:
        """Send approval notification for a newly generated card."""
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == card.location_id).first()
        if not location:
            return

        rating_stars = '*' * max(1, min(card.review_rating, 5))
        message = (
            "New social proof card is ready for review.\n\n"
            f"{rating_stars} review from {card.review_author or 'Customer'}\n"
            f"Title: {card.card_title or 'Social proof card'}\n\n"
            "Open the dashboard to approve or reject it before publishing."
        )

        await self.notification_service.send_notification(
            account_id=location.account_id,
            title="New Social Proof Card",
            message=message,
            notification_type="social_proof_card",
            data={"card_id": card.id, "card_url": card.final_card_url},
        )

    async def auto_generate_cards(self, request: AutoGenerateCardsRequest) -> list[SocialProofCard]:
        """Generate multiple cards from recent high-quality reviews."""
        from app.models.review_response import ReviewResponse

        start_date = utc_now_naive() - timedelta(days=request.days_back)
        reviews = (
            self.db.query(ReviewResponse)
            .filter(
                and_(
                    ReviewResponse.location_id == request.location_id,
                    ReviewResponse.review_rating >= request.min_rating,
                    ReviewResponse.created_at >= start_date,
                )
            )
            .order_by(desc(ReviewResponse.review_rating), desc(ReviewResponse.created_at))
            .limit(request.max_cards * 2)
            .all()
        )

        eligible_reviews = [
            review
            for review in reviews
            if review.review_text and len(review.review_text) >= request.min_text_length
        ]

        cards = []
        for review in eligible_reviews[: request.max_cards]:
            try:
                card_request = GenerateCardRequest(
                    location_id=request.location_id,
                    review_id=review.review_id,
                    review_author=review.review_author,
                    review_rating=review.review_rating,
                    review_text=review.review_text,
                    review_date=review.review_date,
                )
                cards.append(await self.generate_card(card_request))
            except Exception as exc:
                logger.error("Error generating card for review %s: %s", review.review_id, exc)
        return cards

    async def approve_card(
        self,
        card_id: int,
        account_id: UUID,
        publish_immediately: bool = False,
    ) -> SocialProofCard:
        """Approve a social proof card."""
        card = self.db.query(SocialProofCard).filter(SocialProofCard.id == card_id).first()
        if not card:
            raise ValueError(f"Card {card_id} not found")

        if publish_immediately:
            raise ValueError(
                "Direct social proof publishing is not wired yet. Approve the card and publish it manually from your channel workflow."
            )

        card.status = SocialProofStatus.APPROVED
        card.approved_by = account_id
        card.approved_at = utc_now_naive()
        self.db.commit()
        self.db.refresh(card)

        return card

    async def reject_card(self, card_id: int, account_id: UUID, reason: str) -> SocialProofCard:
        """Reject a social proof card."""
        card = self.db.query(SocialProofCard).filter(SocialProofCard.id == card_id).first()
        if not card:
            raise ValueError(f"Card {card_id} not found")

        card.status = SocialProofStatus.REJECTED
        card.approved_by = account_id
        card.approved_at = utc_now_naive()
        card.rejection_reason = reason
        self.db.commit()
        self.db.refresh(card)
        return card

    def get_pending_cards(
        self,
        location_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SocialProofCard]:
        """List pending cards."""
        query = self.db.query(SocialProofCard).filter(
            SocialProofCard.status == SocialProofStatus.PENDING
        )
        if location_id is not None:
            query = query.filter(SocialProofCard.location_id == location_id)
        return query.order_by(desc(SocialProofCard.created_at)).limit(limit).offset(offset).all()

    def _build_metrics(self, cards: list[SocialProofCard]) -> SocialProofMetrics:
        total_cards = len(cards)
        draft_count = sum(1 for card in cards if card.status == SocialProofStatus.DRAFT)
        pending_count = sum(1 for card in cards if card.status == SocialProofStatus.PENDING)
        approved_count = sum(1 for card in cards if card.status == SocialProofStatus.APPROVED)
        rejected_count = sum(1 for card in cards if card.status == SocialProofStatus.REJECTED)
        published_count = sum(1 for card in cards if card.status == SocialProofStatus.PUBLISHED)

        attention_cutoff = utc_now_naive() - timedelta(days=1)
        attention_required_count = sum(
            1
            for card in cards
            if card.status in {SocialProofStatus.DRAFT, SocialProofStatus.PENDING}
            and card.updated_at
            and card.updated_at < attention_cutoff
        )

        approval_rate = 0.0
        publish_rate = 0.0
        if total_cards:
            approval_rate = round(((approved_count + published_count) / total_cards) * 100, 1)
            publish_rate = round((published_count / total_cards) * 100, 1)

        last_published_at = max(
            [card.published_at for card in cards if card.published_at],
            default=None,
        )
        last_rejected_at = max(
            [card.updated_at for card in cards if card.status == SocialProofStatus.REJECTED and card.updated_at],
            default=None,
        )
        last_pending_at = max(
            [card.updated_at for card in cards if card.status == SocialProofStatus.PENDING and card.updated_at],
            default=None,
        )

        return SocialProofMetrics(
            total_cards=total_cards,
            draft_count=draft_count,
            pending_count=pending_count,
            approved_count=approved_count,
            rejected_count=rejected_count,
            published_count=published_count,
            attention_required_count=attention_required_count,
            approval_rate=approval_rate,
            publish_rate=publish_rate,
            last_published_at=last_published_at,
            last_rejected_at=last_rejected_at,
            last_pending_at=last_pending_at,
        )

    def get_history(
        self,
        location_id: UUID,
        status_filter: str = "all",
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SocialProofHistoryResponse:
        """Return paginated social proof card history and operational metrics."""
        base_query = self.db.query(SocialProofCard).filter(SocialProofCard.location_id == location_id)
        all_cards = base_query.order_by(desc(SocialProofCard.created_at)).all()

        cards_query = base_query
        filter_value = (status_filter or "all").lower()
        if filter_value not in {"all", "draft", "pending", "approved", "rejected", "published", "attention"}:
            raise ValueError(f"Invalid status filter: {status_filter}")

        if filter_value == "attention":
            attention_cutoff = utc_now_naive() - timedelta(days=1)
            cards_query = cards_query.filter(
                and_(
                    SocialProofCard.status.in_([SocialProofStatus.DRAFT, SocialProofStatus.PENDING]),
                    SocialProofCard.updated_at < attention_cutoff,
                )
            )
        elif filter_value != "all":
            status_map = {
                "draft": SocialProofStatus.DRAFT,
                "pending": SocialProofStatus.PENDING,
                "approved": SocialProofStatus.APPROVED,
                "rejected": SocialProofStatus.REJECTED,
                "published": SocialProofStatus.PUBLISHED,
            }
            cards_query = cards_query.filter(SocialProofCard.status == status_map[filter_value])

        if search:
            search_term = f"%{search.strip()}%"
            if search_term != "%%":
                cards_query = cards_query.filter(
                    or_(
                        SocialProofCard.card_title.ilike(search_term),
                        SocialProofCard.card_text.ilike(search_term),
                        SocialProofCard.review_author.ilike(search_term),
                        SocialProofCard.review_text.ilike(search_term),
                        SocialProofCard.rejection_reason.ilike(search_term),
                        SocialProofCard.platform_post_id.ilike(search_term),
                        SocialProofCard.published_to.ilike(search_term),
                        SocialProofCard.final_card_url.ilike(search_term),
                    )
                )

        total = cards_query.count()
        items = (
            cards_query.order_by(desc(SocialProofCard.created_at))
            .limit(limit)
            .offset(offset)
            .all()
        )

        return SocialProofHistoryResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            status_filter=filter_value,
            search=search,
            metrics=self._build_metrics(all_cards),
        )
