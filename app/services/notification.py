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
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.post import Post
from app.services.credits import CreditsService
from app.services.email_service import EmailDeliveryError, EmailService, EmailUnavailableError
from app.services.twilio_service import (
    TwilioDeliveryError,
    TwilioUnavailableError,
    get_twilio_service,
)

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    """Supported notification channels."""

    KAKAO = "kakao"
    SLACK = "slack"
    EMAIL = "email"
    SMS = "sms"


class NotificationSMSLimitError(RuntimeError):
    """Raised when an SMS notification exceeds usage limits."""

    def __init__(self, detail: dict[str, Any]):
        super().__init__(detail.get("message") or "SMS notification limit exceeded")
        self.detail = detail


class NotificationService:
    """Service for sending approval notifications."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _preview_sms_usage(self, account_id: UUID) -> None:
        result = CreditsService(self.db).preview_usage(str(account_id), "sms", 1)
        if result.get("allowed"):
            return

        raise NotificationSMSLimitError(
            {
                "error": "Rate limit exceeded",
                "message": result.get("reason"),
                "remaining_daily": result.get("remaining_daily", 0),
                "remaining_monthly": result.get("remaining_monthly", 0),
                "cooldown_seconds": result.get("cooldown_remaining_seconds", 0),
                "overage_available": result.get("overage_available", False),
                "overage_cost_cents": result.get("overage_cost_cents", 0),
            }
        )

    def _record_sms_usage(self, account_id: UUID) -> None:
        result = CreditsService(self.db).use_credits(str(account_id), "sms", 1)
        if result.get("allowed"):
            return

        logger.warning(
            "SMS notification usage record failed after successful send for account %s: %s",
            account_id,
            result.get("reason"),
        )

    def _persist_notification_event(
        self,
        *,
        account_id: UUID,
        notification_type: str,
        title: str,
        message: str,
        url: str | None = None,
    ) -> NotificationEvent | None:
        """Persist one inbox event for a generic notification."""
        try:
            event = NotificationEvent(
                account_id=account_id,
                type=notification_type,
                title=title,
                body=message,
                url=url,
                read=False,
            )
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            return event
        except Exception as exc:
            logger.warning("Failed to persist notification event for %s: %s", account_id, exc)
            self.db.rollback()
            return None

    async def send_notification(
        self,
        account_id: UUID,
        title: str,
        message: str,
        notification_type: str,
        data: dict[str, Any] | None = None,
        channel_override: str | None = None,
    ) -> dict[str, Any]:
        """Send a generic notification using the account's preferred channel."""
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            logger.warning("Notification target account not found: %s", account_id)
            return {"success": False, "error": "account_not_found"}

        channel_pref = (channel_override or account.notification_channel or "email").lower()
        text_body = f"{title}\n\n{message}"
        data = data or {}
        event = self._persist_notification_event(
            account_id=account_id,
            notification_type=notification_type,
            title=title,
            message=message,
            url=data.get("url") if isinstance(data.get("url"), str) else None,
        )
        notification_event_id = event.id if event else None

        try:
            if channel_pref == "sms" and account.phone:
                result = await self.send_sms(account.phone, text_body[:1000], account_id=account.id)
            elif channel_pref == "both":
                email_result = await self.send_email(
                    to_email=account.email,
                    subject=title,
                    html_body=f"<h2>{title}</h2><p>{message.replace(chr(10), '<br>')}</p>",
                    text_body=text_body,
                )
                sms_result = (
                    await self.send_sms(account.phone, text_body[:1000], account_id=account.id)
                    if account.phone
                    else {"success": False}
                )
                result = {
                    "success": bool(email_result.get("success") or sms_result.get("success")),
                    "email": email_result,
                    "sms": sms_result,
                }
            elif channel_pref == "slack":
                if settings.slack_webhook_url:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            settings.slack_webhook_url,
                            json={"text": f"{title}\n{message}"},
                        )
                    result = {"success": response.status_code == 200}
                else:
                    result = {"success": False, "error": "slack_not_configured"}
            else:
                result = await self.send_email(
                    to_email=account.email,
                    subject=title,
                    html_body=f"<h2>{title}</h2><p>{message.replace(chr(10), '<br>')}</p>",
                    text_body=text_body,
                )
        except Exception as e:
            logger.error("Generic notification failed for %s: %s", account_id, e)
            self._write_delivery_log(
                account_id=account_id,
                channel=channel_pref,
                delivery_status="failed",
                failure_reason=str(e),
                notification_event_id=notification_event_id,
            )
            return {"success": False, "error": str(e), "type": notification_type, "data": data}

        self._write_delivery_log(
            account_id=account_id,
            channel=channel_pref,
            delivery_status="delivered" if result.get("success") else "failed",
            failure_reason=result.get("error"),
            notification_event_id=notification_event_id,
        )
        return {"type": notification_type, "data": data, **result}

    def _write_delivery_log(
        self,
        account_id: UUID,
        channel: str,
        delivery_status: str,
        failure_reason: str | None = None,
        notification_event_id: UUID | None = None,
    ) -> None:
        """Persist a delivery audit record. Failures here are non-fatal."""
        try:
            now = datetime.now(timezone.utc)
            log = NotificationDeliveryLog(
                account_id=account_id,
                notification_event_id=notification_event_id,
                channel=channel,
                delivery_status=delivery_status,
                failure_reason=failure_reason,
                attempted_at=now,
                delivered_at=now if delivery_status == "delivered" else None,
            )
            self.db.add(log)
            self.db.commit()
        except Exception as exc:
            logger.warning("Failed to write delivery log for %s: %s", account_id, exc)
            self.db.rollback()

    def send_inbox_notification(
        self,
        *,
        account_id: UUID,
        title: str,
        message: str,
        notification_type: str,
        url: str | None = None,
    ) -> dict[str, Any]:
        """Persist an inbox-only notification and its delivery audit row."""
        event = self._persist_notification_event(
            account_id=account_id,
            notification_type=notification_type,
            title=title,
            message=message,
            url=url,
        )
        if event is None:
            return {
                "success": False,
                "error": "notification_persist_failed",
                "type": notification_type,
            }

        self._write_delivery_log(
            account_id=account_id,
            channel="inbox",
            delivery_status="delivered",
            notification_event_id=event.id,
        )
        return {
            "success": True,
            "notification_id": str(event.id),
            "type": notification_type,
        }

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
                logger.warning("Unknown notification channel: %s", channel)
                return False

            if success:
                post.notification_sent = True
                post.notification_channel = channel.value
                post.notification_sent_at = datetime.now(timezone.utc)
                self.db.commit()

            return success
        except Exception as e:
            logger.error("Failed to send notification: %s", e)
            return False

    def _build_public_approval_links(self, post: Post) -> dict[str, str]:
        """Build the live frontend approval links for a pending post."""
        review_url = f"{settings.app_url}/approve/{post.id}?token={post.approval_token}"
        return {
            "approve_url": f"{review_url}&action=approve",
            "reject_url": f"{review_url}&action=reject",
            "review_url": review_url,
        }

    async def _send_kakao_notification(self, post: Post, account: Account) -> bool:
        """Send KakaoTalk notification via Kakao API."""
        kakao_token = getattr(settings, "kakao_api_token", None)
        if not kakao_token:
            logger.warning("Kakao API token not configured")
            return False

        links = self._build_public_approval_links(post)
        approval_url = links["approve_url"]
        reject_url = links["reject_url"]
        message = self._build_approval_message(post, approval_url, reject_url)

        try:
            async with httpx.AsyncClient() as client:
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
                            "button_title": "Approve",
                        }
                    },
                )

                if response.status_code == 200:
                    logger.info("Kakao notification sent for post %s", post.id)
                    return True

                logger.error("Kakao API error: %s", response.text)
                return False
        except Exception as e:
            logger.error("Kakao notification failed: %s", e)
            return False

    async def _send_slack_notification(self, post: Post, account: Account) -> bool:
        """Send Slack notification via webhook."""
        slack_webhook_url = getattr(settings, "slack_webhook_url", None)
        if not slack_webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False

        links = self._build_public_approval_links(post)
        approval_url = links["approve_url"]
        reject_url = links["reject_url"]
        review_url = links["review_url"]

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "New content approval request",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Platform*\n{post.platform.value}"},
                    {"type": "mrkdwn", "text": f"*Location*\n{post.location.name if post.location else 'N/A'}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Title*\n{post.title or '(untitled)'}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Preview*\n{(post.body or '')[:300]}{'...' if post.body and len(post.body) > 300 else ''}",
                },
            },
        ]

        if post.ai_image_url:
            blocks.append(
                {
                    "type": "image",
                    "image_url": post.ai_image_url,
                    "alt_text": "Generated image preview",
                }
            )

        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                        "style": "primary",
                        "url": approval_url,
                        "action_id": "approve_post",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                        "style": "danger",
                        "url": reject_url,
                        "action_id": "reject_post",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Review First", "emoji": True},
                        "url": review_url,
                        "action_id": "review_post",
                    },
                ],
            }
        )

        payload = {
            "blocks": blocks,
            "text": f"Approval request: {post.title or post.platform.value}",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(slack_webhook_url, json=payload)

                if response.status_code == 200:
                    logger.info("Slack notification sent for post %s", post.id)
                    return True

                logger.error("Slack webhook error: %s", response.text)
                return False
        except Exception as e:
            logger.error("Slack notification failed: %s", e)
            return False

    async def _send_email_notification(self, post: Post, account: Account) -> bool:
        """Send email notification."""
        if not settings.smtp_host:
            logger.warning("SMTP not configured")
            return False

        links = self._build_public_approval_links(post)
        approval_url = links["approve_url"]
        reject_url = links["reject_url"]
        review_url = links["review_url"]

        subject = f"[Approval Request] New content for {post.platform.value}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">New content approval request</h2>

            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Platform:</strong> {post.platform.value}</p>
                <p><strong>Location:</strong> {post.location.name if post.location else 'N/A'}</p>
                <p><strong>Title:</strong> {post.title or '(untitled)'}</p>
            </div>

            <div style="background: #fff; border: 1px solid #ddd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3>Preview</h3>
                <p>{(post.body or '')[:500]}{'...' if post.body and len(post.body) > 500 else ''}</p>
            </div>

            {"<img src='" + post.ai_image_url + "' style='max-width: 100%; border-radius: 8px;' />" if post.ai_image_url else ""}

            <div style="margin: 30px 0; text-align: center;">
                <a href="{approval_url}" style="background: #4CAF50; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 0 10px;">Approve</a>
                <a href="{review_url}" style="background: #6b7280; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 0 10px;">Review First</a>
                <a href="{reject_url}" style="background: #f44336; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 0 10px;">Reject</a>
            </div>

            <p style="color: #666; font-size: 12px;">This email was sent automatically by Local SEO Optimizer.</p>
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

            logger.info("Email notification sent for post %s", post.id)
            return True
        except Exception as e:
            logger.error("Email notification failed: %s", e)
            return False

    def _build_approval_message(self, post: Post, approval_url: str, reject_url: str) -> str:
        """Build approval message text."""
        return (
            "New content approval request\n\n"
            f"Platform: {post.platform.value}\n"
            f"Location: {post.location.name if post.location else 'N/A'}\n"
            f"Title: {post.title or '(untitled)'}\n\n"
            f"Preview:\n{(post.body or '')[:200]}{'...' if post.body and len(post.body) > 200 else ''}\n\n"
            f"Approve: {approval_url}\n"
            f"Reject: {reject_url}\n"
        )

    async def _send_sms_notification(self, post: Post, account: Account) -> bool:
        """Send SMS notification via Twilio."""
        phone_number = getattr(account, "phone", None)
        if not phone_number:
            logger.warning("No phone number for account %s", account.id)
            return False

        from app.services.magic_link import MagicLinkService

        magic_link = MagicLinkService()
        links = magic_link.generate_approval_links(
            post_id=post.id,
            account_id=account.id,
            approval_token=post.approval_token,
        )

        message = (
            "[Local SEO Optimizer]\n"
            "Approval request\n\n"
            f"{post.title or post.platform.value}\n\n"
            f"Approve: {links['approve_url']}\n\n"
            f"Reject: {links['reject_url']}\n\n"
            "Please respond within 72 hours."
        )

        result = await self.send_sms(phone_number, message, account_id=account.id)
        if result.get("success"):
            logger.info("SMS notification sent for post %s: %s", post.id, result.get("message_sid"))
            return True
        logger.error("SMS notification failed for post %s: %s", post.id, result.get("error"))
        return False

    def _normalize_email_send_result(self, provider: str, result: dict[str, Any] | None) -> dict[str, Any]:
        """Normalize helper payloads to the public email delivery contract."""
        normalized = dict(result or {})
        normalized.setdefault("provider", provider)
        normalized.setdefault("success", "error" not in normalized)
        return normalized

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> dict:
        """Send a generic email using SMTP first, then SendGrid when available."""
        smtp_error: str | None = None

        if settings.smtp_host:
            try:
                return self._normalize_email_send_result(
                    "smtp",
                    await self._send_email_via_smtp(
                        to_email=to_email,
                        subject=subject,
                        html_body=html_body,
                        text_body=text_body,
                    ),
                )
            except (EmailDeliveryError, EmailUnavailableError) as exc:
                smtp_error = str(exc)
                logger.error("SMTP email send failed for %s: %s", to_email, exc)

        if settings.sendgrid_api_key:
            try:
                return self._normalize_email_send_result(
                    "sendgrid",
                    await self._send_email_via_sendgrid(
                        to_email=to_email,
                        subject=subject,
                        html_body=html_body,
                    ),
                )
            except (EmailUnavailableError, EmailDeliveryError) as exc:
                sendgrid_error = str(exc)
                logger.error("SendGrid email send failed for %s: %s", to_email, exc)
                if smtp_error:
                    return {"success": False, "error": f"SMTP failed: {smtp_error}; SendGrid failed: {sendgrid_error}"}
                return {"success": False, "error": sendgrid_error}

        if smtp_error:
            return {"success": False, "error": smtp_error}

        logger.warning("Email delivery is not configured")
        return {"success": False, "error": "Email delivery is not configured"}

    async def _send_email_via_smtp(
        self,
        *,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> dict:
        """Send email via SMTP."""
        if not settings.smtp_host:
            raise EmailUnavailableError("SMTP is not configured")

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

            logger.info("Email sent to %s via SMTP", to_email)
            return {"success": True, "provider": "smtp"}
        except Exception as exc:
            raise EmailDeliveryError(str(exc)) from exc

    async def _send_email_via_sendgrid(
        self,
        *,
        to_email: str,
        subject: str,
        html_body: str,
    ) -> dict:
        """Send email via SendGrid."""
        result = await EmailService().send_email(
            to=to_email,
            subject=subject,
            html_content=html_body,
            from_email=settings.sendgrid_from_email or settings.email_from,
            from_name=settings.app_name,
        )
        logger.info("Email sent to %s via SendGrid", to_email)
        return {
            "success": True,
            "provider": "sendgrid",
            "message_id": result.get("message_id"),
            "status_code": result.get("status_code"),
        }

    async def send_sms(
        self,
        to_phone: str,
        message: str,
        account_id: UUID | None = None,
    ) -> dict:
        """Send a generic SMS via Twilio."""
        try:
            if account_id is not None:
                self._preview_sms_usage(account_id)

            result = await get_twilio_service().send_sms(
                to=to_phone,
                body=message,
            )
            if account_id is not None:
                self._record_sms_usage(account_id)

            logger.info("SMS sent to %s: %s", to_phone, result.get("sid"))
            return {
                "success": True,
                "message_sid": result.get("sid"),
                "status": result.get("status"),
            }
        except NotificationSMSLimitError as exc:
            logger.warning("SMS send blocked by usage limit for account %s: %s", account_id, exc)
            return {
                "success": False,
                "error": exc.detail.get("message"),
                "error_code": "rate_limit_exceeded",
                **exc.detail,
            }
        except (TwilioUnavailableError, TwilioDeliveryError) as exc:
            logger.error("SMS send failed: %s", exc)
            return {"success": False, "error": str(exc)}
        except Exception as e:
            logger.error("SMS send failed: %s", e)
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

        status = "approved" if approved else "rejected"
        message = (
            f"Content was {status}.\n\n"
            f"Platform: {post.platform.value}\n"
            f"Title: {post.title or '(untitled)'}"
        )

        if not approved and post.rejection_reason:
            message += f"\n\nReason: {post.rejection_reason}"

        try:
            if channel == NotificationChannel.SLACK:
                slack_webhook_url = getattr(settings, "slack_webhook_url", None)
                if slack_webhook_url:
                    async with httpx.AsyncClient() as client:
                        await client.post(slack_webhook_url, json={"text": message})
            return True
        except Exception as e:
            logger.error("Failed to send approval result notification: %s", e)
            return False
