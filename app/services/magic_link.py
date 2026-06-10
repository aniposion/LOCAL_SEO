"""Magic Link service for passwordless content approval."""

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class MagicLinkService:
    """
    Service for generating and validating magic links.

    Magic links allow content approval without login:
    - Include a signed, expiring token in each link.
    - Let customers approve, reject, or review content from the public flow.
    - Default token lifetime is 72 hours.
    """

    DEFAULT_EXPIRY_HOURS = 72

    ACTION_APPROVE = "approve"
    ACTION_REJECT = "reject"
    ACTION_EDIT = "edit"

    def __init__(self, db: Session | None = None):
        self.db = db
        self.secret_key = getattr(settings, "secret_key", None) or settings.jwt_secret

    def generate_token(
        self,
        post_id: UUID,
        action: str,
        account_id: UUID,
        expiry_hours: int = DEFAULT_EXPIRY_HOURS,
    ) -> str:
        """
        Generate a secure magic link token.

        Token format: {random_part}.{expiry}.{signature}
        Signature = HMAC(secret, post_id + action + account_id + expiry)
        """
        random_part = secrets.token_urlsafe(16)
        expiry = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        expiry_ts = int(expiry.timestamp())
        payload = f"{post_id}:{action}:{account_id}:{expiry_ts}:{random_part}"
        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:32]
        return f"{random_part}.{expiry_ts}.{signature}"

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

            if datetime.now(timezone.utc).timestamp() > expiry_ts:
                return {"valid": False, "error": "Token expired"}

            payload = f"{post_id}:{action}:{account_id}:{expiry_ts}:{random_part}"
            expected_signature = hmac.new(
                self.secret_key.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()[:32]

            if not hmac.compare_digest(provided_signature, expected_signature):
                return {"valid": False, "error": "Invalid signature"}

            return {"valid": True}

        except Exception as exc:
            logger.error("Token validation error: %s", exc)
            return {"valid": False, "error": "Token validation failed"}

    def generate_approval_links(
        self,
        post_id: UUID,
        account_id: UUID | None,
        base_url: str | None = None,
        approval_token: str | None = None,
    ) -> dict[str, str]:
        """
        Generate all approval action links for a post.

        When a persisted ``approval_token`` is available, prefer the live
        frontend review flow at ``/approve/{post_id}``. Legacy action-specific
        HMAC links remain available as a fallback for older callers.
        """
        base = base_url or settings.app_url or "https://app.localseooptimizer.com"

        if approval_token:
            review_url = f"{base}/approve/{post_id}?token={approval_token}"
            return {
                "approve_url": f"{review_url}&action=approve",
                "reject_url": f"{review_url}&action=reject",
                "review_url": review_url,
                "edit_url": review_url,
            }

        if account_id is None:
            raise ValueError("account_id is required when approval_token is not provided")

        approve_token = self.generate_token(post_id, self.ACTION_APPROVE, account_id)
        reject_token = self.generate_token(post_id, self.ACTION_REJECT, account_id)
        review_token = self.generate_token(post_id, self.ACTION_EDIT, account_id)

        return {
            "approve_url": f"{base}/approve/{post_id}?token={approve_token}&action=approve",
            "reject_url": f"{base}/approve/{post_id}?token={reject_token}&action=reject",
            "review_url": f"{base}/approve/{post_id}?token={review_token}",
            "edit_url": f"{base}/approve/{post_id}?token={review_token}&action=edit",
        }

    def generate_approval_email_content(
        self,
        post: Any,
        location: Any,
        links: dict[str, str],
    ) -> dict[str, str]:
        """Generate email content for approval notification."""
        location_name = str(getattr(location, "name", None) or "your location")
        post_title = str(getattr(post, "title", None) or "New Post")
        post_body = str(getattr(post, "body", "") or "")
        post_excerpt = f"{post_body[:300]}{'...' if len(post_body) > 300 else ''}"
        text_excerpt = f"{post_body[:500]}{'...' if len(post_body) > 500 else ''}"
        review_url = links.get("review_url") or links.get("edit_url") or links["approve_url"]

        subject = f"[Action Required] New content ready for {location_name}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #2563eb 0%, #0f766e 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f8f9fa; padding: 30px; }}
                .post-preview {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .post-title {{ font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
                .post-body {{ color: #555; line-height: 1.6; }}
                .buttons {{ display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }}
                .btn {{ display: inline-block; padding: 12px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; text-align: center; }}
                .btn-approve {{ background: #16a34a; color: white; }}
                .btn-reject {{ background: #dc2626; color: white; }}
                .btn-edit {{ background: #475569; color: white; }}
                .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>New Content Ready</h1>
                    <p>AI has generated new content for your review.</p>
                </div>

                <div class="content">
                    <p>Hi there,</p>
                    <p>We've created a new post for <strong>{escape(location_name)}</strong>. Please review it, then approve or reject it.</p>

                    <div class="post-preview">
                        <div class="post-title">{escape(post_title)}</div>
                        <div class="post-body">{escape(post_excerpt)}</div>
                    </div>

                    <div class="buttons">
                        <a href="{escape(links['approve_url'], quote=True)}" class="btn btn-approve">Approve</a>
                        <a href="{escape(review_url, quote=True)}" class="btn btn-edit">Review First</a>
                        <a href="{escape(links['reject_url'], quote=True)}" class="btn btn-reject">Reject</a>
                    </div>

                    <p style="margin-top: 20px; color: #666; font-size: 14px;">
                        This link expires in 72 hours. No login required.
                    </p>
                </div>

                <div class="footer">
                    <p>Local SEO Optimizer - Automated Google Maps Marketing</p>
                    <p>You're receiving this because content approval is enabled.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = (
            f"New Content Ready for {location_name}\n\n"
            "We've created a new post for your approval:\n\n"
            f"Title: {post_title}\n"
            "---\n"
            f"{text_excerpt}\n"
            "---\n\n"
            "Review or respond (no login required):\n"
            f"Approve: {links['approve_url']}\n"
            f"Review First: {review_url}\n"
            f"Reject: {links['reject_url']}\n\n"
            "This link expires in 72 hours.\n\n"
            "- Local SEO Optimizer Team"
        )

        return {
            "subject": subject,
            "html": html_body,
            "text": text_body,
        }


class ApprovalWorkflowService:
    """Service for handling content approval workflow via magic links."""

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
        from app.models.location import Location
        from app.models.post import Post, PostStatus

        post = self.db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return {"success": False, "error": "Post not found"}

        location = self.db.query(Location).filter(Location.id == post.location_id).first()
        if not location:
            return {"success": False, "error": "Location not found"}

        validation = self.magic_link.validate_token(
            token=token,
            post_id=post_id,
            action=action,
            account_id=location.account_id,
        )

        if not validation["valid"]:
            return {"success": False, "error": validation["error"]}

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

        if action == MagicLinkService.ACTION_REJECT:
            post.status = PostStatus.REJECTED
            self.db.commit()

            return {
                "success": True,
                "action": "rejected",
                "message": "Content rejected. We'll generate a new version.",
                "post_id": str(post_id),
            }

        if action == MagicLinkService.ACTION_EDIT:
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
        channel: str = "email",
        phone_number: str | None = None,
    ) -> dict[str, Any]:
        """
        Send approval notification via email or SMS with magic links.

        Args:
            post_id: The post to send notification for
            channel: "email" or "sms"
            phone_number: Required if channel is "sms"
        """
        from app.models.account import Account
        from app.models.location import Location
        from app.models.post import Post
        from app.services.notification import NotificationService

        post = self.db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return {"success": False, "error": "Post not found"}

        location = self.db.query(Location).filter(Location.id == post.location_id).first()
        if not location:
            return {"success": False, "error": "Location not found"}

        account = self.db.query(Account).filter(Account.id == location.account_id).first()
        if not account:
            return {"success": False, "error": "Account not found"}

        links = self.magic_link.generate_approval_links(
            post_id=post_id,
            account_id=account.id,
            approval_token=post.approval_token,
        )

        notification_service = NotificationService(self.db)

        if channel == "sms":
            target_phone = phone_number or getattr(account, "phone", None)
            if not target_phone:
                return {"success": False, "error": "No phone number available"}

            sms_content = self._generate_approval_sms_content(post, location, links)
            result = await notification_service.send_sms(
                to_phone=target_phone,
                message=sms_content,
                account_id=account.id,
            )

            return {
                "success": result.get("success", False),
                "channel": "sms",
                "sms_sent": result.get("success", False),
                "links": links,
                "error": result.get("error"),
            }

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
        location_name = str(getattr(location, "name", None) or "your location")
        post_title = str(getattr(post, "title", None) or "New Post")
        return (
            f"[{location_name}] Content approval requested\n\n"
            f"{post_title}\n\n"
            f"Approve: {links['approve_url']}\n\n"
            f"Reject: {links['reject_url']}\n\n"
            "Expires in 72 hours."
        )

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
