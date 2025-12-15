"""Notification service for approval workflow."""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.account import Account
from app.models.post import Post

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    """Supported notification channels."""

    KAKAO = "kakao"
    SLACK = "slack"
    EMAIL = "email"
    SMS = "sms"  # Twilio SMS


class NotificationService:
    """Service for sending approval notifications."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def send_approval_request(
        self,
        post: Post,
        account: Account,
        channel: NotificationChannel = NotificationChannel.SLACK,
    ) -> bool:
        """Send approval request notification."""
        try:
            if channel == NotificationChannel.KAKAO:
                success = await self._send_kakao_notification(post, account)
            elif channel == NotificationChannel.SLACK:
                success = await self._send_slack_notification(post, account)
            elif channel == NotificationChannel.EMAIL:
                success = await self._send_email_notification(post, account)
            elif channel == NotificationChannel.SMS:
                success = await self._send_sms_notification(post, account)
            else:
                logger.warning(f"Unknown notification channel: {channel}")
                return False

            if success:
                post.notification_sent = True
                post.notification_channel = channel.value
                post.notification_sent_at = datetime.now(timezone.utc)
                self.db.commit()

            return success

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    async def _send_kakao_notification(self, post: Post, account: Account) -> bool:
        """Send KakaoTalk notification via Kakao API."""
        kakao_token = getattr(settings, 'kakao_api_token', None)
        if not kakao_token:
            logger.warning("Kakao API token not configured")
            return False

        approval_url = f"{settings.app_url}/posts/{post.id}/approve?token={post.approval_token}"
        reject_url = f"{settings.app_url}/posts/{post.id}/reject?token={post.approval_token}"

        # Kakao 알림톡 템플릿 메시지
        message = self._build_approval_message(post, approval_url, reject_url)

        try:
            async with httpx.AsyncClient() as client:
                # 카카오 알림톡 API 호출
                response = await client.post(
                    "https://kapi.kakao.com/v2/api/talk/memo/default/send",
                    headers={
                        "Authorization": f"Bearer {kakao_token}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={
                        "template_object": {
                            "object_type": "text",
                            "text": message,
                            "link": {
                                "web_url": approval_url,
                                "mobile_web_url": approval_url,
                            },
                            "button_title": "승인하기",
                        }
                    },
                )

                if response.status_code == 200:
                    logger.info(f"Kakao notification sent for post {post.id}")
                    return True
                else:
                    logger.error(f"Kakao API error: {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Kakao notification failed: {e}")
            return False

    async def _send_slack_notification(self, post: Post, account: Account) -> bool:
        """Send Slack notification via webhook."""
        slack_webhook_url = getattr(settings, 'slack_webhook_url', None)
        if not slack_webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False

        approval_url = f"{settings.app_url}/posts/{post.id}/approve?token={post.approval_token}"
        reject_url = f"{settings.app_url}/posts/{post.id}/reject?token={post.approval_token}"

        # Slack Block Kit 메시지
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📝 새 콘텐츠 승인 요청",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*플랫폼:*\n{post.platform.value}"},
                    {"type": "mrkdwn", "text": f"*위치:*\n{post.location.name if post.location else 'N/A'}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*제목:*\n{post.title or '(제목 없음)'}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*내용 미리보기:*\n{(post.body or '')[:300]}{'...' if post.body and len(post.body) > 300 else ''}",
                },
            },
        ]

        # AI 생성 이미지가 있으면 표시
        if post.ai_image_url:
            blocks.append({
                "type": "image",
                "image_url": post.ai_image_url,
                "alt_text": "AI 생성 이미지",
            })

        # 승인/거절 버튼
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ 승인", "emoji": True},
                    "style": "primary",
                    "url": approval_url,
                    "action_id": "approve_post",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ 거절", "emoji": True},
                    "style": "danger",
                    "url": reject_url,
                    "action_id": "reject_post",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📝 수정", "emoji": True},
                    "url": f"{settings.app_url}/posts/{post.id}/edit",
                    "action_id": "edit_post",
                },
            ],
        })

        payload = {
            "blocks": blocks,
            "text": f"새 콘텐츠 승인 요청: {post.title or post.platform.value}",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(slack_webhook_url, json=payload)

                if response.status_code == 200:
                    logger.info(f"Slack notification sent for post {post.id}")
                    return True
                else:
                    logger.error(f"Slack webhook error: {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return False

    async def _send_email_notification(self, post: Post, account: Account) -> bool:
        """Send email notification."""
        if not settings.smtp_host:
            logger.warning("SMTP not configured")
            return False

        approval_url = f"{settings.app_url}/posts/{post.id}/approve?token={post.approval_token}"
        reject_url = f"{settings.app_url}/posts/{post.id}/reject?token={post.approval_token}"

        subject = f"[승인 요청] 새 콘텐츠 - {post.platform.value}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">📝 새 콘텐츠 승인 요청</h2>
            
            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>플랫폼:</strong> {post.platform.value}</p>
                <p><strong>위치:</strong> {post.location.name if post.location else 'N/A'}</p>
                <p><strong>제목:</strong> {post.title or '(제목 없음)'}</p>
            </div>
            
            <div style="background: #fff; border: 1px solid #ddd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3>내용 미리보기</h3>
                <p>{(post.body or '')[:500]}{'...' if post.body and len(post.body) > 500 else ''}</p>
            </div>
            
            {"<img src='" + post.ai_image_url + "' style='max-width: 100%; border-radius: 8px;' />" if post.ai_image_url else ""}
            
            <div style="margin: 30px 0; text-align: center;">
                <a href="{approval_url}" style="background: #4CAF50; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 0 10px;">✅ 승인</a>
                <a href="{reject_url}" style="background: #f44336; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 0 10px;">❌ 거절</a>
            </div>
            
            <p style="color: #666; font-size: 12px;">이 이메일은 Local SEO Optimizer에서 자동 발송되었습니다.</p>
        </body>
        </html>
        """

        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.email_from
            msg["To"] = account.email

            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                if settings.smtp_user and settings.smtp_password:
                    server.starttls()
                    server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.email_from, account.email, msg.as_string())

            logger.info(f"Email notification sent for post {post.id}")
            return True

        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False

    def _build_approval_message(self, post: Post, approval_url: str, reject_url: str) -> str:
        """Build approval message text."""
        return f"""📝 새 콘텐츠 승인 요청

플랫폼: {post.platform.value}
위치: {post.location.name if post.location else 'N/A'}
제목: {post.title or '(제목 없음)'}

내용:
{(post.body or '')[:200]}{'...' if post.body and len(post.body) > 200 else ''}

승인하기: {approval_url}
거절하기: {reject_url}
"""

    async def _send_sms_notification(self, post: Post, account: Account) -> bool:
        """Send SMS notification via Twilio."""
        from twilio.rest import Client

        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            logger.warning("Twilio not configured")
            return False

        # Get phone number from account
        phone_number = getattr(account, 'phone', None)
        if not phone_number:
            logger.warning(f"No phone number for account {account.id}")
            return False

        # Generate magic link
        from app.services.magic_link import MagicLinkService
        magic_link = MagicLinkService()
        links = magic_link.generate_approval_links(
            post_id=post.id,
            account_id=account.id,
        )

        # Build SMS message (keep it short for SMS)
        message = f"""[Local SEO Optimizer]
새 콘텐츠 승인 요청

{post.title or post.platform.value}

✅ 승인: {links['approve_url']}

❌ 거절: {links['reject_url']}

72시간 내 응답 필요"""

        try:
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            
            sms = client.messages.create(
                body=message,
                from_=settings.twilio_phone_number,
                to=phone_number,
            )

            logger.info(f"SMS notification sent for post {post.id}: {sms.sid}")
            return True

        except Exception as e:
            logger.error(f"SMS notification failed: {e}")
            return False

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> dict:
        """Send a generic email."""
        if not settings.smtp_host:
            logger.warning("SMTP not configured")
            return {"success": False, "error": "SMTP not configured"}

        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.email_from
            msg["To"] = to_email

            if text_body:
                msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                if settings.smtp_user and settings.smtp_password:
                    server.starttls()
                    server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.email_from, to_email, msg.as_string())

            logger.info(f"Email sent to {to_email}")
            return {"success": True}

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return {"success": False, "error": str(e)}

    async def send_sms(
        self,
        to_phone: str,
        message: str,
    ) -> dict:
        """Send a generic SMS via Twilio."""
        from twilio.rest import Client

        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            logger.warning("Twilio not configured")
            return {"success": False, "error": "Twilio not configured"}

        try:
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            
            sms = client.messages.create(
                body=message,
                from_=settings.twilio_phone_number,
                to=to_phone,
            )

            logger.info(f"SMS sent to {to_phone}: {sms.sid}")
            return {"success": True, "message_sid": sms.sid}

        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            return {"success": False, "error": str(e)}

    async def send_approval_result(
        self,
        post: Post,
        account: Account,
        approved: bool,
        channel: NotificationChannel | None = None,
    ) -> bool:
        """Send notification about approval result."""
        channel = channel or NotificationChannel(post.notification_channel) if post.notification_channel else NotificationChannel.SLACK

        status = "승인됨 ✅" if approved else "거절됨 ❌"
        message = f"콘텐츠가 {status}\n\n플랫폼: {post.platform.value}\n제목: {post.title or '(제목 없음)'}"

        if not approved and post.rejection_reason:
            message += f"\n\n거절 사유: {post.rejection_reason}"

        try:
            if channel == NotificationChannel.SLACK:
                slack_webhook_url = getattr(settings, 'slack_webhook_url', None)
                if slack_webhook_url:
                    async with httpx.AsyncClient() as client:
                        await client.post(slack_webhook_url, json={"text": message})
            return True
        except Exception as e:
            logger.error(f"Failed to send approval result notification: {e}")
            return False
