"""
Social Auto-Responder Service
Automatically respond to Instagram DMs and comments
"""
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from app.integrations.instagram import InstagramClient
from app.integrations.llm import LLMClient


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


class SocialResponderService:
    """Service for auto-responding to social media messages."""
    
    def __init__(self, instagram_token: Optional[str] = None):
        self.instagram_client = InstagramClient(instagram_token) if instagram_token else None
        self.llm = LLMClient()
        
        # Response templates by category
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
                "Thank you so much for your kind words! We really appreciate it. 🙏",
                "Thanks for the love! It means a lot to us. ❤️",
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
        if platform == "instagram" and self.instagram_client:
            try:
                # Fetch DMs from Instagram
                conversations = await self.instagram_client.get_conversations(limit=limit)
                
                messages = []
                for conv in conversations.get("data", []):
                    for msg in conv.get("messages", {}).get("data", []):
                        if not msg.get("is_echo"):  # Skip our own messages
                            messages.append(SocialMessage(
                                id=msg.get("id"),
                                platform="instagram",
                                type=ResponseType.DM,
                                sender_id=msg.get("from", {}).get("id"),
                                sender_name=msg.get("from", {}).get("username", "User"),
                                message=msg.get("message", ""),
                                created_at=datetime.fromisoformat(msg.get("created_time", datetime.now().isoformat())),
                            ))
                
                return messages
            except Exception as e:
                print(f"Error fetching Instagram messages: {e}")
        
        # Return demo data
        return [
            SocialMessage(
                id="dm1",
                platform="instagram",
                type=ResponseType.DM,
                sender_id="user1",
                sender_name="foodie_lover",
                message="Hi! What time do you close today?",
                created_at=datetime.now() - timedelta(minutes=30),
            ),
            SocialMessage(
                id="dm2",
                platform="instagram",
                type=ResponseType.DM,
                sender_id="user2",
                sender_name="local_explorer",
                message="Do you take reservations for groups?",
                created_at=datetime.now() - timedelta(hours=1),
            ),
            SocialMessage(
                id="comment1",
                platform="instagram",
                type=ResponseType.COMMENT,
                sender_id="user3",
                sender_name="happy_customer",
                message="This looks amazing! 😍",
                post_id="post123",
                created_at=datetime.now() - timedelta(hours=2),
            ),
        ]
    
    async def get_pending_comments(
        self,
        location_id: str,
        post_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[SocialMessage]:
        """Get pending comments that need responses."""
        if self.instagram_client:
            try:
                comments = await self.instagram_client.get_comments(post_id, limit=limit)
                
                return [
                    SocialMessage(
                        id=c.get("id"),
                        platform="instagram",
                        type=ResponseType.COMMENT,
                        sender_id=c.get("from", {}).get("id"),
                        sender_name=c.get("from", {}).get("username", "User"),
                        message=c.get("text", ""),
                        post_id=post_id,
                        created_at=datetime.fromisoformat(c.get("timestamp", datetime.now().isoformat())),
                    )
                    for c in comments.get("data", [])
                ]
            except Exception as e:
                print(f"Error fetching comments: {e}")
        
        return []
    
    def classify_message(self, message: str) -> str:
        """Classify message intent for template selection."""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["hi", "hello", "hey", "good morning", "good evening"]):
            return "greeting"
        elif any(word in message_lower for word in ["hour", "open", "close", "time"]):
            return "hours"
        elif any(word in message_lower for word in ["where", "location", "address", "find you", "directions"]):
            return "location"
        elif any(word in message_lower for word in ["thank", "love", "amazing", "great", "awesome", "❤", "😍", "🙏"]):
            return "thanks"
        elif any(word in message_lower for word in ["book", "reservation", "reserve", "appointment"]):
            return "booking"
        else:
            return "default"
    
    async def generate_response(
        self,
        message: SocialMessage,
        business_name: str,
        business_info: dict,
    ) -> str:
        """Generate an AI response for a message."""
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

            response = await self.llm.generate(prompt)
            return response
        except Exception as e:
            # Fallback to template
            category = self.classify_message(message.message)
            templates = self.templates.get(category, self.templates["default"])
            template = templates[0]
            
            return template.format(
                name=message.sender_name,
                address=business_info.get("address", "our location"),
                phone=business_info.get("phone", "our number"),
            )
    
    async def send_response(
        self,
        message: SocialMessage,
        response_text: str,
    ) -> AutoResponse:
        """Send a response to a message or comment."""
        try:
            if message.type == ResponseType.DM and self.instagram_client:
                await self.instagram_client.send_dm(message.sender_id, response_text)
            elif message.type == ResponseType.COMMENT and self.instagram_client:
                await self.instagram_client.reply_to_comment(message.id, response_text)
            
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=datetime.now(),
                success=True,
            )
        except Exception as e:
            print(f"Error sending response: {e}")
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=datetime.now(),
                success=False,
            )
    
    async def auto_respond_all(
        self,
        location_id: str,
        business_name: str,
        business_info: dict,
    ) -> list[AutoResponse]:
        """Auto-respond to all pending messages."""
        results = []
        
        # Get pending messages
        messages = await self.get_pending_messages(location_id)
        
        for message in messages:
            # Generate response
            response_text = await self.generate_response(
                message, business_name, business_info
            )
            
            # Send response
            result = await self.send_response(message, response_text)
            results.append(result)
        
        return results
    
    def get_response_stats(self, location_id: str, days: int = 7) -> dict:
        """Get auto-response statistics."""
        # In production, fetch from database
        return {
            "total_messages": 45,
            "auto_responded": 38,
            "manual_responses": 7,
            "avg_response_time_minutes": 2.5,
            "response_rate": 95.5,
            "sentiment_positive": 82,
            "sentiment_neutral": 15,
            "sentiment_negative": 3,
        }
