"""Social Auto-Responder Service."""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from app.integrations.instagram import InstagramClient
from app.integrations.llm import LLMClient

logger = logging.getLogger(__name__)


class ResponseType(str, Enum):
    DM = "dm"
    COMMENT = "comment"
    MENTION = "mention"


@dataclass
class SocialMessage:
    id: str
    platform: str
    type: ResponseType
    sender_id: str
    sender_name: str
    message: str
    post_id: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class AutoResponse:
    message_id: str
    response_text: str
    sent_at: datetime
    success: bool
    error_message: Optional[str] = None


class SocialResponderService:
    """Service for auto-responding to social media messages."""

    def __init__(self, instagram_credentials: Optional[dict] = None):
        self.instagram_client = InstagramClient(instagram_credentials) if instagram_credentials else None
        self.llm = LLMClient()
        self.last_generation_used_ai = True
        self.templates = {
            "greeting": [
                "Hi {name}! Thanks for reaching out. How can we help you today?",
                "Hello {name}! We appreciate your message. What can we do for you?",
            ],
            "hours": [
                "We're open Monday-Saturday 9AM-9PM and Sunday 10AM-6PM. Hope to see you soon!",
                "Our hours are Mon-Sat 9AM-9PM, Sun 10AM-6PM. Feel free to visit anytime!",
            ],
            "location": [
                "You can find us at {address}. We have free parking available!",
                "We're located at {address}. Can't wait to see you!",
            ],
            "thanks": [
                "Thank you so much for your kind words. We really appreciate it.",
                "Thanks for the love. It means a lot to us.",
            ],
            "booking": [
                "You can book with us by calling {phone} or visiting our website. We'd love to have you!",
                "For reservations, please call {phone} or book online. Looking forward to serving you!",
            ],
            "default": [
                "Thanks for your message! We'll get back to you shortly. In the meantime, feel free to call us at {phone}.",
                "Hi! Thanks for reaching out. We'll respond as soon as possible. You can also call us at {phone}.",
            ],
        }

    async def get_pending_messages(
        self,
        location_id: str,
        platform: str = "instagram",
        limit: int = 20,
    ) -> list[SocialMessage]:
        """Get pending messages that need responses."""
        if platform != "instagram" or not self.instagram_client:
            return []

        try:
            conversations = await self.instagram_client.get_conversations(limit=limit)
            messages: list[SocialMessage] = []
            for conv in conversations.get("data", []):
                for msg in conv.get("messages", {}).get("data", []):
                    if msg.get("is_echo"):
                        continue
                    messages.append(
                        SocialMessage(
                            id=msg.get("id"),
                            platform="instagram",
                            type=ResponseType.DM,
                            sender_id=msg.get("from", {}).get("id", ""),
                            sender_name=msg.get("from", {}).get("username", "User"),
                            message=msg.get("message", ""),
                            created_at=datetime.fromisoformat(
                                msg.get("created_time", datetime.now().isoformat())
                            ),
                        )
                    )
            return messages
        except Exception as exc:
            logger.warning("Error fetching Instagram messages: %s", exc, exc_info=True)
            return []

    async def get_pending_comments(
        self,
        location_id: str,
        post_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[SocialMessage]:
        """Get pending comments that need responses."""
        if not self.instagram_client:
            return []

        try:
            comments = await self.instagram_client.get_comments(post_id, limit=limit)
            return [
                SocialMessage(
                    id=item.get("id"),
                    platform="instagram",
                    type=ResponseType.COMMENT,
                    sender_id=item.get("from", {}).get("id", ""),
                    sender_name=item.get("from", {}).get("username", "User"),
                    message=item.get("text", ""),
                    post_id=post_id,
                    created_at=datetime.fromisoformat(
                        item.get("timestamp", datetime.now().isoformat())
                    ),
                )
                for item in comments.get("data", [])
            ]
        except Exception as exc:
            logger.warning("Error fetching comments: %s", exc, exc_info=True)
            return []

    def classify_message(self, message: str) -> str:
        """Classify message intent for template selection."""
        message_lower = message.lower()
        if any(word in message_lower for word in ["hi", "hello", "hey", "good morning", "good evening"]):
            return "greeting"
        if any(word in message_lower for word in ["hour", "open", "close", "time"]):
            return "hours"
        if any(word in message_lower for word in ["where", "location", "address", "find you", "directions"]):
            return "location"
        if any(word in message_lower for word in ["thank", "love", "amazing", "great", "awesome"]):
            return "thanks"
        if any(word in message_lower for word in ["book", "reservation", "reserve", "appointment"]):
            return "booking"
        return "default"

    def classify_sentiment(self, message: str) -> str:
        """Classify simple customer sentiment from message text."""
        message_lower = message.lower()
        positive_words = ["love", "great", "amazing", "awesome", "perfect", "thanks", "thank you", "good"]
        negative_words = ["bad", "hate", "terrible", "awful", "angry", "complaint", "upset", "refund", "problem"]

        if any(word in message_lower for word in negative_words):
            return "negative"
        if any(word in message_lower for word in positive_words):
            return "positive"
        return "neutral"

    async def classify_sentiment_model(self, message: str) -> str:
        """Classify sentiment with the LLM, then fall back to heuristics."""
        try:
            prompt = (
                "Classify the customer message sentiment as exactly one label: "
                "positive, neutral, or negative.\n"
                "Return only the label.\n\n"
                f"Message: {message}"
            )
            result = (await self.llm.generate(prompt)).strip().lower()
            if "negative" in result:
                return "negative"
            if "positive" in result:
                return "positive"
            if "neutral" in result:
                return "neutral"
        except Exception:
            pass
        return self.classify_sentiment(message)

    async def generate_response(
        self,
        message: SocialMessage,
        business_name: str,
        business_info: dict,
    ) -> str:
        """Generate an AI response for a message."""
        self.last_generation_used_ai = True
        try:
            prompt = f"""You are a friendly social media manager for {business_name}.

Business Info:
- Address: {business_info.get('address', 'N/A')}
- Phone: {business_info.get('phone', 'N/A')}
- Hours: {business_info.get('hours', 'Mon-Sat 9AM-9PM')}
- Category: {business_info.get('category', 'Local Business')}

Customer Message ({message.type.value}): {message.message}

Write a friendly, helpful response. Keep it short (1-2 sentences for comments, 2-3 for DMs).
Use emojis sparingly. Be professional but warm."""
            return await self.llm.generate(prompt)
        except Exception:
            self.last_generation_used_ai = False
            category = self.classify_message(message.message)
            template = self.templates.get(category, self.templates["default"])[0]
            return template.format(
                name=message.sender_name,
                address=business_info.get("address", "our location"),
                phone=business_info.get("phone", "our number"),
            )

    async def send_response(self, message: SocialMessage, response_text: str) -> AutoResponse:
        """Send a response to a message or comment."""
        sent_at = datetime.now()
        if not self.instagram_client:
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=sent_at,
                success=False,
                error_message="Instagram is not connected",
            )

        try:
            if message.type == ResponseType.DM:
                await self.instagram_client.send_dm(message.sender_id, response_text)
            elif message.type == ResponseType.COMMENT:
                await self.instagram_client.reply_to_comment(message.id, response_text)
            else:
                return AutoResponse(
                    message_id=message.id,
                    response_text=response_text,
                    sent_at=sent_at,
                    success=False,
                    error_message=f"Unsupported response type: {message.type.value}",
                )
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=sent_at,
                success=True,
            )
        except Exception as exc:
            logger.warning("Error sending social response: %s", exc, exc_info=True)
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=sent_at,
                success=False,
                error_message=str(exc),
            )

    async def auto_respond_all(
        self,
        location_id: str,
        business_name: str,
        business_info: dict,
    ) -> list[AutoResponse]:
        """Auto-respond to all pending messages."""
        results: list[AutoResponse] = []
        messages = await self.get_pending_messages(location_id)
        for message in messages:
            response_text = await self.generate_response(message, business_name, business_info)
            results.append(await self.send_response(message, response_text))
        return results

    def get_response_stats(self, location_id: str, days: int = 7) -> dict:
        """Get auto-response statistics."""
        return {
            "total_messages": 0,
            "auto_responded": 0,
            "manual_responses": 0,
            "avg_response_time_minutes": 0.0,
            "response_rate": 0.0,
            "sentiment_positive": 0,
            "sentiment_neutral": 0,
            "sentiment_negative": 0,
        }
