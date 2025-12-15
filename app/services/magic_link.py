"""Magic Link service for passwordless content approval."""

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class MagicLinkService:
    """
    Service for generating and validating magic links.
    
    Magic Links allow content approval without login:
    - 보안 토큰이 포함된 링크로 원클릭 승인
    - 별도 로그인 과정 없이 처리
    - 토큰은 시간 제한 있음 (기본 72시간)
    """

    # Token expiration time
    DEFAULT_EXPIRY_HOURS = 72

    # Action types
    ACTION_APPROVE = "approve"
    ACTION_REJECT = "reject"
    ACTION_EDIT = "edit"

    def __init__(self, db: Session | None = None):
        self.db = db
        self.secret_key = settings.secret_key

    def generate_token(
        self,
        post_id: UUID,
        action: str,
        account_id: UUID,
        expiry_hours: int = DEFAULT_EXPIRY_HOURS,
    ) -> str:
        """
        Generate a secure magic link token.
        
        Token format: {random_part}.{signature}
        Signature = HMAC(secret, post_id + action + account_id + expiry)
        """
        # Generate random component
        random_part = secrets.token_urlsafe(16)

        # Calculate expiry timestamp
        expiry = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        expiry_ts = int(expiry.timestamp())

        # Create signature payload
        payload = f"{post_id}:{action}:{account_id}:{expiry_ts}:{random_part}"

        # Generate HMAC signature
        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:32]

        # Combine into token
        token = f"{random_part}.{expiry_ts}.{signature}"

        return token

    def validate_token(
        self,
        token: str,
        post_id: UUID,
        action: str,
        account_id: UUID,
    ) -> dict[str, Any]:
        """
        Validate a magic link token.
        
        Returns:
            {"valid": True/False, "error": str if invalid}
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return {"valid": False, "error": "Invalid token format"}

            random_part, expiry_ts_str, provided_signature = parts
            expiry_ts = int(expiry_ts_str)

            # Check expiry
            if datetime.now(timezone.utc).timestamp() > expiry_ts:
                return {"valid": False, "error": "Token expired"}

            # Recreate signature
            payload = f"{post_id}:{action}:{account_id}:{expiry_ts}:{random_part}"
            expected_signature = hmac.new(
                self.secret_key.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()[:32]

            # Constant-time comparison
            if not hmac.compare_digest(provided_signature, expected_signature):
                return {"valid": False, "error": "Invalid signature"}

            return {"valid": True}

        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return {"valid": False, "error": "Token validation failed"}

    def generate_approval_links(
        self,
        post_id: UUID,
        account_id: UUID,
        base_url: str | None = None,
    ) -> dict[str, str]:
        """
        Generate all approval action links for a post.
        
        Returns:
            {
                "approve_url": "...",
                "reject_url": "...",
                "edit_url": "...",
            }
        """
        base = base_url or settings.app_url or "https://app.localseooptimizer.com"

        approve_token = self.generate_token(post_id, self.ACTION_APPROVE, account_id)
        reject_token = self.generate_token(post_id, self.ACTION_REJECT, account_id)
        edit_token = self.generate_token(post_id, self.ACTION_EDIT, account_id)

        return {
            "approve_url": f"{base}/approve/{post_id}?token={approve_token}&action=approve",
            "reject_url": f"{base}/approve/{post_id}?token={reject_token}&action=reject",
            "edit_url": f"{base}/approve/{post_id}?token={edit_token}&action=edit",
        }

    def generate_approval_email_content(
        self,
        post: Any,
        location: Any,
        links: dict[str, str],
    ) -> dict[str, str]:
        """
        Generate email content for approval notification.
        """
        subject = f"[Action Required] New content ready for {location.name}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f8f9fa; padding: 30px; }}
                .post-preview {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .post-title {{ font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
                .post-body {{ color: #555; line-height: 1.6; }}
                .buttons {{ display: flex; gap: 10px; margin-top: 20px; }}
                .btn {{ display: inline-block; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; text-align: center; }}
                .btn-approve {{ background: #28a745; color: white; }}
                .btn-reject {{ background: #dc3545; color: white; }}
                .btn-edit {{ background: #6c757d; color: white; }}
                .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📝 New Content Ready</h1>
                    <p>AI has generated new content for your approval</p>
                </div>
                
                <div class="content">
                    <p>Hi there!</p>
                    <p>We've created a new post for <strong>{location.name}</strong>. Please review and approve it with one click.</p>
                    
                    <div class="post-preview">
                        <div class="post-title">{post.title or 'New Post'}</div>
                        <div class="post-body">{post.body[:300]}{'...' if len(post.body or '') > 300 else ''}</div>
                    </div>
                    
                    <div class="buttons">
                        <a href="{links['approve_url']}" class="btn btn-approve">✅ Approve & Publish</a>
                        <a href="{links['edit_url']}" class="btn btn-edit">✏️ Edit First</a>
                        <a href="{links['reject_url']}" class="btn btn-reject">❌ Reject</a>
                    </div>
                    
                    <p style="margin-top: 20px; color: #666; font-size: 14px;">
                        This link expires in 72 hours. No login required.
                    </p>
                </div>
                
                <div class="footer">
                    <p>Local SEO Optimizer - Automated Google Maps Marketing</p>
                    <p>You're receiving this because you have content approval enabled.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
New Content Ready for {location.name}

We've created a new post for your approval:

Title: {post.title or 'New Post'}
---
{post.body[:500]}
---

Click to approve (no login required):
✅ Approve: {links['approve_url']}
✏️ Edit: {links['edit_url']}
❌ Reject: {links['reject_url']}

This link expires in 72 hours.

- Local SEO Optimizer Team
        """

        return {
            "subject": subject,
            "html": html_body,
            "text": text_body,
        }


class ApprovalWorkflowService:
    """
    Service for handling content approval workflow via magic links.
    """

    def __init__(self, db: Session):
        self.db = db
        self.magic_link = MagicLinkService(db)

    async def process_approval_action(
        self,
        post_id: UUID,
        token: str,
        action: str,
    ) -> dict[str, Any]:
        """
        Process an approval action from a magic link.
        
        Args:
            post_id: The post to act on
            token: The magic link token
            action: approve, reject, or edit
        
        Returns:
            Result of the action
        """
        from app.models.post import Post, PostStatus

        # Get the post
        post = self.db.query(Post).filter(Post.id == post_id).first()

        if not post:
            return {"success": False, "error": "Post not found"}

        # Get account ID from post's location
        from app.models.location import Location
        location = self.db.query(Location).filter(
            Location.id == post.location_id
        ).first()

        if not location:
            return {"success": False, "error": "Location not found"}

        # Validate token
        validation = self.magic_link.validate_token(
            token=token,
            post_id=post_id,
            action=action,
            account_id=location.account_id,
        )

        if not validation["valid"]:
            return {"success": False, "error": validation["error"]}

        # Process action
        if action == MagicLinkService.ACTION_APPROVE:
            post.status = PostStatus.APPROVED
            post.approved_at = datetime.now(timezone.utc)
            self.db.commit()

            return {
                "success": True,
                "action": "approved",
                "message": "Content approved! It will be published shortly.",
                "post_id": str(post_id),
            }

        elif action == MagicLinkService.ACTION_REJECT:
            post.status = PostStatus.REJECTED
            self.db.commit()

            return {
                "success": True,
                "action": "rejected",
                "message": "Content rejected. We'll generate a new version.",
                "post_id": str(post_id),
            }

        elif action == MagicLinkService.ACTION_EDIT:
            # For edit, we return the post data for editing
            return {
                "success": True,
                "action": "edit",
                "message": "You can now edit this content.",
                "post_id": str(post_id),
                "post_data": {
                    "title": post.title,
                    "body": post.body,
                    "image_url": post.image_url,
                },
            }

        return {"success": False, "error": "Invalid action"}

    async def send_approval_notification(
        self,
        post_id: UUID,
        channel: str = "email",  # "email" or "sms"
        phone_number: str | None = None,
    ) -> dict[str, Any]:
        """
        Send approval notification via email or SMS with magic links.
        
        Args:
            post_id: The post to send notification for
            channel: "email" or "sms"
            phone_number: Required if channel is "sms"
        """
        from app.models.post import Post
        from app.models.location import Location
        from app.models.account import Account
        from app.services.notification import NotificationService

        # Get post and related data
        post = self.db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return {"success": False, "error": "Post not found"}

        location = self.db.query(Location).filter(
            Location.id == post.location_id
        ).first()
        if not location:
            return {"success": False, "error": "Location not found"}

        account = self.db.query(Account).filter(
            Account.id == location.account_id
        ).first()
        if not account:
            return {"success": False, "error": "Account not found"}

        # Generate magic links
        links = self.magic_link.generate_approval_links(
            post_id=post_id,
            account_id=account.id,
        )

        notification_service = NotificationService(self.db)

        if channel == "sms":
            # Send via SMS
            target_phone = phone_number or getattr(account, 'phone', None)
            if not target_phone:
                return {"success": False, "error": "No phone number available"}

            sms_content = self._generate_approval_sms_content(post, location, links)
            result = await notification_service.send_sms(
                to_phone=target_phone,
                message=sms_content,
            )

            return {
                "success": result.get("success", False),
                "channel": "sms",
                "sms_sent": result.get("success", False),
                "links": links,
                "error": result.get("error"),
            }

        else:
            # Send via Email (default)
            email_content = self.magic_link.generate_approval_email_content(
                post=post,
                location=location,
                links=links,
            )

            result = await notification_service.send_email(
                to_email=account.email,
                subject=email_content["subject"],
                html_body=email_content["html"],
                text_body=email_content["text"],
            )

            return {
                "success": result.get("success", False),
                "channel": "email",
                "email_sent": result.get("success", False),
                "links": links,
                "error": result.get("error"),
            }

    def _generate_approval_sms_content(
        self,
        post: Any,
        location: Any,
        links: dict[str, str],
    ) -> str:
        """Generate SMS content for approval notification."""
        # Keep SMS short (160 chars per segment)
        return f"""[{location.name}] 새 콘텐츠 승인 요청

{post.title or '새 포스트'}

✅ 승인: {links['approve_url']}

❌ 거절: {links['reject_url']}

72시간 내 응답"""

    async def send_approval_notification_multi(
        self,
        post_id: UUID,
        channels: list[str],
        phone_number: str | None = None,
    ) -> dict[str, Any]:
        """
        Send approval notification via multiple channels.
        
        Args:
            post_id: The post to send notification for
            channels: List of channels ["email", "sms"]
            phone_number: Required if "sms" in channels
        """
        results = {}

        for channel in channels:
            result = await self.send_approval_notification(
                post_id=post_id,
                channel=channel,
                phone_number=phone_number,
            )
            results[channel] = result

        return {
            "success": any(r.get("success") for r in results.values()),
            "results": results,
        }
