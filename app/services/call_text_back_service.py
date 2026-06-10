"""P3: Missed Call Text Back service - aligned with existing models."""

import logging
from datetime import timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.core.time import utc_now_aware
from app.models.calls import (
    CallLog,
    MessageDirection,
    SMSMessage,
    SMSThread,
    ThreadStatus,
    TwilioNumber,
)
from app.models.location import Location
from app.services.credits import CreditsService
from app.services.twilio_service import (
    TwilioDeliveryError,
    TwilioUnavailableError,
    get_twilio_service,
)

logger = logging.getLogger(__name__)


class SMSUsageLimitError(RuntimeError):
    """Raised when SMS usage is not allowed for the current account."""

    def __init__(self, detail: dict):
        super().__init__(detail.get("message") or "SMS usage limit exceeded")
        self.detail = detail


class MissedCallTextBackService:
    """Service for missed call text back feature using existing models."""

    def __init__(self, db: Session):
        self.db = db

    def get_settings(self, location_id: UUID) -> Optional[TwilioNumber]:
        return self.db.execute(
            select(TwilioNumber).where(TwilioNumber.location_id == location_id)
        ).scalar_one_or_none()

    def update_settings(
        self,
        location_id: UUID,
        enabled: bool = None,
        sms_template: str = None,
    ) -> Optional[TwilioNumber]:
        settings = self.get_settings(location_id)
        if not settings:
            return None

        if enabled is not None:
            settings.missed_call_sms_enabled = enabled
        if sms_template is not None:
            settings.sms_template = sms_template

        self.db.commit()
        self.db.refresh(settings)
        return settings

    def _resolve_account_id(self, location_id: UUID) -> UUID:
        account_id = self.db.execute(
            select(Location.account_id).where(Location.id == location_id)
        ).scalar_one_or_none()
        if not account_id:
            raise ValueError("Location owner not found")
        return account_id

    def _preview_sms_usage(self, account_id: UUID) -> None:
        result = CreditsService(self.db).preview_usage(str(account_id), "sms", 1)
        if result.get("allowed"):
            return

        raise SMSUsageLimitError(
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
            "SMS usage record failed after successful call text-back send for account %s: %s",
            account_id,
            result.get("reason"),
        )

    async def _notify_text_back_issue(
        self,
        *,
        account_id: UUID,
        location_id: UUID,
        caller_phone: str,
        call_log_id: UUID,
        notification_type: str,
        title: str,
        error_message: str,
    ) -> None:
        """Persist an operator-facing alert for missed-call text-back issues."""
        from app.services.notification import NotificationService

        await NotificationService(self.db).send_notification(
            account_id=account_id,
            title=title,
            message=(
                f"Missed-call text back for {caller_phone} at location {location_id} needs attention."
                f"\n\nReason: {error_message}"
            ),
            notification_type=notification_type,
            data={
                "url": "/dashboard/calls",
                "location_id": str(location_id),
                "call_log_id": str(call_log_id),
                "caller_phone": caller_phone,
                "error_message": error_message,
            },
        )

    async def handle_missed_call(
        self,
        location_id: UUID,
        caller_phone: str,
        twilio_call_sid: str,
        twilio_number_id: UUID,
    ) -> Optional[CallLog]:
        settings = self.get_settings(location_id)
        if not settings or not settings.missed_call_sms_enabled:
            logger.info("Text back disabled for location %s", location_id)
            return None

        call_log = CallLog(
            location_id=location_id,
            twilio_number_id=twilio_number_id,
            caller_number=caller_phone,
            call_status="no-answer",
            call_duration=0,
            twilio_call_sid=twilio_call_sid,
        )
        self.db.add(call_log)
        self.db.commit()
        self.db.refresh(call_log)

        settings.total_calls += 1
        settings.missed_calls += 1
        self.db.commit()

        await self._send_text_back(call_log, settings)
        return call_log

    async def _send_text_back(self, call_log: CallLog, settings: TwilioNumber):
        account_id: UUID | None = None
        try:
            account_id = self._resolve_account_id(call_log.location_id)
            message = settings.sms_template.format(
                business_name="Business",
                forward_to=settings.forward_to,
            )
            self._preview_sms_usage(account_id)

            result = await get_twilio_service().send_sms(
                to=call_log.caller_number,
                body=message,
                from_number=settings.twilio_number,
            )

            call_log.sms_sent = True
            call_log.sms_sent_at = utc_now_aware()
            call_log.sms_message_sid = result.get("sid")
            settings.sms_sent += 1

            thread = self._get_or_create_thread(
                call_log.location_id,
                call_log.caller_number,
                settings.twilio_number,
            )
            call_log.thread_id = thread.id

            sms_message = SMSMessage(
                thread_id=thread.id,
                direction=MessageDirection.OUTBOUND,
                body=message,
                status=result.get("status", "sent"),
                twilio_message_sid=result.get("sid"),
            )
            self.db.add(sms_message)
            thread.last_message_at = utc_now_aware()
            self.db.commit()
            self._record_sms_usage(account_id)
            logger.info("Text back sent for call %s", call_log.id)
        except SMSUsageLimitError as exc:
            logger.warning("Skipped text back for call %s: %s", call_log.id, exc)
            if account_id is not None:
                await self._notify_text_back_issue(
                    account_id=account_id,
                    location_id=call_log.location_id,
                    caller_phone=call_log.caller_number,
                    call_log_id=call_log.id,
                    notification_type="missed_call_text_back_skipped",
                    title="Missed call text-back skipped",
                    error_message=str(exc),
                )
        except (TwilioUnavailableError, TwilioDeliveryError) as exc:
            logger.error("Failed to send text back for call %s: %s", call_log.id, exc)
            if account_id is not None:
                await self._notify_text_back_issue(
                    account_id=account_id,
                    location_id=call_log.location_id,
                    caller_phone=call_log.caller_number,
                    call_log_id=call_log.id,
                    notification_type="missed_call_text_back_failed",
                    title="Missed call text-back failed",
                    error_message=str(exc),
                )
        except Exception as exc:
            logger.error("Failed to send text back for call %s: %s", call_log.id, exc)
            if account_id is not None:
                await self._notify_text_back_issue(
                    account_id=account_id,
                    location_id=call_log.location_id,
                    caller_phone=call_log.caller_number,
                    call_log_id=call_log.id,
                    notification_type="missed_call_text_back_failed",
                    title="Missed call text-back failed",
                    error_message=str(exc),
                )

    def get_call_logs(
        self,
        location_id: UUID,
        status: Optional[str] = None,
        days: int = 30,
        limit: int = 50,
    ) -> list[CallLog]:
        cutoff = utc_now_aware() - timedelta(days=days)
        query = select(CallLog).where(
            and_(CallLog.location_id == location_id, CallLog.created_at >= cutoff)
        )
        if status:
            query = query.where(CallLog.call_status == status)
        query = query.order_by(desc(CallLog.created_at)).limit(limit)
        return list(self.db.execute(query).scalars().all())

    def get_call_stats(self, location_id: UUID, days: int = 30) -> dict:
        cutoff = utc_now_aware() - timedelta(days=days)

        total = self.db.execute(
            select(func.count(CallLog.id)).where(
                and_(CallLog.location_id == location_id, CallLog.created_at >= cutoff)
            )
        ).scalar() or 0

        missed = self.db.execute(
            select(func.count(CallLog.id)).where(
                and_(
                    CallLog.location_id == location_id,
                    CallLog.created_at >= cutoff,
                    CallLog.call_status.in_(["no-answer", "busy"]),
                )
            )
        ).scalar() or 0

        text_backs = self.db.execute(
            select(func.count(CallLog.id)).where(
                and_(
                    CallLog.location_id == location_id,
                    CallLog.created_at >= cutoff,
                    CallLog.sms_sent.is_(True),
                )
            )
        ).scalar() or 0

        return {
            "total_calls": total,
            "missed_calls": missed,
            "answered_calls": total - missed,
            "text_backs_sent": text_backs,
            "text_back_rate": round((text_backs / missed * 100) if missed > 0 else 0, 1),
        }

    def _get_or_create_thread(
        self,
        location_id: UUID,
        customer_phone: str,
        twilio_number: str,
    ) -> SMSThread:
        thread = self.db.execute(
            select(SMSThread).where(
                and_(
                    SMSThread.location_id == location_id,
                    SMSThread.customer_phone == customer_phone,
                )
            )
        ).scalar_one_or_none()

        if not thread:
            thread = SMSThread(
                location_id=location_id,
                customer_phone=customer_phone,
                twilio_number=twilio_number,
                status=ThreadStatus.OPEN,
            )
            self.db.add(thread)
            self.db.commit()
            self.db.refresh(thread)
        return thread

    def get_threads(
        self,
        location_id: UUID,
        status: Optional[ThreadStatus] = None,
        limit: int = 50,
    ) -> list[SMSThread]:
        query = select(SMSThread).where(SMSThread.location_id == location_id)
        if status:
            query = query.where(SMSThread.status == status)
        query = query.order_by(desc(SMSThread.last_message_at)).limit(limit)
        return list(self.db.execute(query).scalars().all())

    def get_thread_messages(self, thread_id: UUID, limit: int = 100) -> list[SMSMessage]:
        return list(
            self.db.execute(
                select(SMSMessage)
                .where(SMSMessage.thread_id == thread_id)
                .order_by(SMSMessage.created_at)
                .limit(limit)
            ).scalars().all()
        )

    async def send_sms(self, thread_id: UUID, body: str) -> SMSMessage:
        thread = self.db.execute(
            select(SMSThread).where(SMSThread.id == thread_id)
        ).scalar_one_or_none()
        if not thread:
            raise ValueError("Thread not found")

        account_id = self._resolve_account_id(thread.location_id)
        self._preview_sms_usage(account_id)

        result = await get_twilio_service().send_sms(
            to=thread.customer_phone,
            body=body,
            from_number=thread.twilio_number,
        )

        message = SMSMessage(
            thread_id=thread_id,
            direction=MessageDirection.OUTBOUND,
            body=body,
            status=result.get("status", "sent"),
            twilio_message_sid=result.get("sid"),
        )
        self.db.add(message)
        thread.last_message_at = utc_now_aware()

        self.db.commit()
        self.db.refresh(message)
        self._record_sms_usage(account_id)
        return message


def get_call_text_back_service(db: Session) -> MissedCallTextBackService:
    """Get service instance."""
    return MissedCallTextBackService(db)
