from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.db.models import ApplicationDraft, CalculatorLead, NotificationPreference, ReminderTask
from app.db.session import SessionLocal
from app.services.blocked_user_service import BlockedUserService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

REMINDER_STATUS_PENDING = "pending"
REMINDER_STATUS_SENT = "sent"
REMINDER_STATUS_CANCELLED = "cancelled"
REMINDER_STATUS_FAILED = "failed"
REMINDER_STATUS_EXPIRED = "expired"

REMINDER_TYPES = {
    "policy_expires_3_days",
    "policy_expires_today",
    "calculator_followup",
    "draft_30_minutes",
    "draft_24_hours",
    "draft_close_3_days",
}

REMINDER_EVENT_KEYS = {
    reminder_type: reminder_type for reminder_type in REMINDER_TYPES
}

SAFE_CONTEXT_DENYLIST = {
    "passport",
    "passport_series",
    "passport_number",
    "passport_series_number",
    "phone",
    "email",
    "vin",
    "full_vin",
    "license_plate",
    "plate",
    "full_plate",
}


class ReminderService:
    """Stores delayed service reminders and dispatches them through NotificationService."""

    def __init__(
        self,
        notification_service: NotificationService | None = None,
        blocked_user_service: BlockedUserService | None = None,
    ) -> None:
        self.notification_service = notification_service or NotificationService()
        self.blocked_user_service = blocked_user_service or BlockedUserService()

    def create_reminder(
        self,
        telegram_user_id: int,
        telegram_chat_id: int,
        reminder_type: str,
        scheduled_at: datetime,
        context: dict[str, Any] | None = None,
        bitrix_deal_id: int | None = None,
        request_id: str | None = None,
        dedupe_key: str | None = None,
    ) -> ReminderTask:
        if reminder_type not in REMINDER_TYPES:
            raise ValueError(f"Unsupported reminder_type: {reminder_type}")

        context_json = self._dump_safe_context(context or {})
        now = datetime.utcnow()
        with SessionLocal() as db:
            if dedupe_key:
                existing = db.scalar(
                    select(ReminderTask).where(
                        ReminderTask.dedupe_key == dedupe_key,
                        ReminderTask.status.in_([REMINDER_STATUS_PENDING, REMINDER_STATUS_SENT]),
                    )
                )
                if existing:
                    db.expunge(existing)
                    return existing

            task = ReminderTask(
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                reminder_type=reminder_type,
                status=REMINDER_STATUS_PENDING,
                bitrix_deal_id=bitrix_deal_id,
                request_id=request_id,
                dedupe_key=dedupe_key,
                scheduled_at=scheduled_at,
                context_json=context_json,
                created_at=now,
                updated_at=now,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            db.expunge(task)
            return task

    def create_policy_expiration_reminders(
        self,
        telegram_user_id: int,
        telegram_chat_id: int,
        bitrix_deal_id: int,
        request_id: str | None,
        vehicle_plate_masked: str,
        end_date: date | datetime,
        product_type: str = "green_card",
        language: str = "ru",
    ) -> list[ReminderTask]:
        policy_end = end_date.date() if isinstance(end_date, datetime) else end_date
        context = {
            "vehicle_plate_masked": vehicle_plate_masked,
            "end_date": policy_end.strftime("%d.%m.%Y"),
            "product_type": product_type,
            "language": language,
            "request_id": request_id or "",
        }
        tasks = []
        for reminder_type, scheduled_date in (
            ("policy_expires_3_days", policy_end - timedelta(days=3)),
            ("policy_expires_today", policy_end),
        ):
            scheduled_at = datetime.combine(scheduled_date, time(hour=9))
            tasks.append(
                self.create_reminder(
                    telegram_user_id=telegram_user_id,
                    telegram_chat_id=telegram_chat_id,
                    reminder_type=reminder_type,
                    scheduled_at=scheduled_at,
                    context=context,
                    bitrix_deal_id=bitrix_deal_id,
                    request_id=request_id,
                    dedupe_key=f"{reminder_type}:{bitrix_deal_id}",
                )
            )
        return tasks

    def create_calculator_followup(
        self,
        telegram_user_id: int,
        telegram_chat_id: int,
        vehicle_type: str | None,
        insurance_period_days: int | None,
        estimated_price: Decimal | float | int | str | None,
        currency: str | None,
        product_type: str = "green_card",
        language: str = "ru",
        delay_minutes: int = 45,
    ) -> CalculatorLead:
        now = datetime.utcnow()
        price = Decimal(str(estimated_price)) if estimated_price is not None else None
        with SessionLocal() as db:
            existing_leads = db.scalars(
                select(CalculatorLead).where(
                    CalculatorLead.telegram_user_id == telegram_user_id,
                    CalculatorLead.status == "calculated",
                )
            ).all()
            for existing in existing_leads:
                existing.status = "cancelled"
                existing.cancelled_at = now
                self._cancel_tasks_with_context(db, "calculator_lead_id", existing.id, now)

            lead = CalculatorLead(
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                product_type=product_type,
                vehicle_type=vehicle_type,
                insurance_period_days=insurance_period_days,
                estimated_price=price,
                currency=currency,
                status="calculated",
                created_at=now,
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)
            lead_id = lead.id
            db.expunge(lead)

        context = {
            "calculator_lead_id": lead_id,
            "product_type": product_type,
            "vehicle_type": vehicle_type or "car",
            "period_days": insurance_period_days or "",
            "estimated_price": str(price) if price is not None else "",
            "currency": currency or "",
            "language": language,
        }
        self.create_reminder(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            reminder_type="calculator_followup",
            scheduled_at=now + timedelta(minutes=delay_minutes),
            context=context,
            dedupe_key=f"calculator_followup:{lead_id}",
        )
        return lead

    def create_application_draft(
        self,
        telegram_user_id: int,
        telegram_chat_id: int,
        product_type: str = "green_card",
        source_channel: str = "telegram_bot",
        current_step: str | None = None,
        safe_context: dict[str, Any] | None = None,
        language: str = "ru",
    ) -> ApplicationDraft:
        now = datetime.utcnow()
        draft_id = f"draft-{telegram_user_id}-{uuid.uuid4().hex[:12]}"
        context = self._safe_context({"product_type": product_type, "language": language, **(safe_context or {})})
        with SessionLocal() as db:
            active_drafts = db.scalars(
                select(ApplicationDraft).where(
                    ApplicationDraft.telegram_user_id == telegram_user_id,
                    ApplicationDraft.status == "active",
                )
            ).all()
            for active in active_drafts:
                active.status = "cancelled"
                active.closed_at = now
                active.encrypted_payload = None
                active.updated_at = now
                self._cancel_tasks_with_context(db, "draft_id", active.draft_id, now)

            draft = ApplicationDraft(
                draft_id=draft_id,
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                product_type=product_type,
                source_channel=source_channel,
                status="active",
                current_step=current_step,
                safe_context_json=json.dumps(context, ensure_ascii=False),
                created_at=now,
                updated_at=now,
                expires_at=now + timedelta(days=3),
            )
            db.add(draft)
            db.commit()
            db.refresh(draft)
            db.expunge(draft)

        reminder_context = {**context, "draft_id": draft_id}
        for reminder_type, delay in (
            ("draft_30_minutes", timedelta(minutes=30)),
            ("draft_24_hours", timedelta(hours=24)),
            ("draft_close_3_days", timedelta(days=3)),
        ):
            self.create_reminder(
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                reminder_type=reminder_type,
                scheduled_at=now + delay,
                context=reminder_context,
                dedupe_key=f"{reminder_type}:{draft_id}",
            )
        return draft

    def mark_calculator_converted(self, telegram_user_id: int) -> None:
        now = datetime.utcnow()
        with SessionLocal() as db:
            leads = db.scalars(
                select(CalculatorLead).where(
                    CalculatorLead.telegram_user_id == telegram_user_id,
                    CalculatorLead.status == "calculated",
                )
            ).all()
            for lead in leads:
                lead.status = "converted"
                lead.converted_at = now
                self._cancel_tasks_with_context(db, "calculator_lead_id", lead.id, now)
            db.commit()

    def complete_active_drafts(self, telegram_user_id: int) -> None:
        self._finish_active_drafts(telegram_user_id, "completed")

    def cancel_active_drafts(self, telegram_user_id: int) -> None:
        self._finish_active_drafts(telegram_user_id, "cancelled")

    def set_notification_preferences(
        self,
        telegram_user_id: int,
        allow_service_notifications: bool | None = None,
        allow_marketing_notifications: bool | None = None,
    ) -> NotificationPreference:
        now = datetime.utcnow()
        with SessionLocal() as db:
            preference = db.scalar(
                select(NotificationPreference).where(NotificationPreference.telegram_user_id == telegram_user_id)
            )
            if not preference:
                preference = NotificationPreference(
                    telegram_user_id=telegram_user_id,
                    allow_service_notifications=True,
                    allow_marketing_notifications=False,
                    created_at=now,
                    updated_at=now,
                )
                db.add(preference)
            if allow_service_notifications is not None:
                preference.allow_service_notifications = allow_service_notifications
            if allow_marketing_notifications is not None:
                preference.allow_marketing_notifications = allow_marketing_notifications
            preference.updated_at = now
            db.commit()
            db.refresh(preference)
            db.expunge(preference)
            return preference

    def process_due(self, limit: int = 100) -> dict[str, int]:
        now = datetime.utcnow()
        with SessionLocal() as db:
            tasks = db.scalars(
                select(ReminderTask)
                .where(ReminderTask.status == REMINDER_STATUS_PENDING, ReminderTask.scheduled_at <= now)
                .order_by(ReminderTask.scheduled_at.asc())
                .limit(limit)
            ).all()
            stats = {"sent": 0, "cancelled": 0, "failed": 0, "skipped": 0}
            for task in tasks:
                status = self._process_task(db, task, now)
                stats[status] = stats.get(status, 0) + 1
            db.commit()
            return stats

    def _process_task(self, db, task: ReminderTask, now: datetime) -> str:
        if not self._allows_service_notifications(db, task.telegram_user_id):
            self._cancel_task(task, now)
            return "cancelled"
        if self.blocked_user_service.is_blocked(task.telegram_user_id):
            self._cancel_task(task, now)
            return "cancelled"
        if not self._is_task_relevant(db, task, now):
            self._cancel_task(task, now)
            return "cancelled"

        context = self._loads_context(task.context_json)
        language = str(context.get("language") or "ru")
        result = self.notification_service.send(
            event_key=REMINDER_EVENT_KEYS[task.reminder_type],
            recipient_type="client",
            recipient_id=str(task.telegram_chat_id),
            channel="client_telegram",
            language=language,
            context=context,
            dedupe_key=task.dedupe_key or f"{task.reminder_type}:{task.id}",
        )
        if result.status in {"sent", "skipped"}:
            task.status = REMINDER_STATUS_SENT if result.status == "sent" else REMINDER_STATUS_EXPIRED
            task.sent_at = now if result.status == "sent" else None
            task.updated_at = now
            return result.status
        task.status = REMINDER_STATUS_FAILED
        task.updated_at = now
        return "failed"

    def _is_task_relevant(self, db, task: ReminderTask, now: datetime) -> bool:
        context = self._loads_context(task.context_json)
        if task.reminder_type == "calculator_followup":
            lead_id = context.get("calculator_lead_id")
            lead = db.get(CalculatorLead, int(lead_id)) if lead_id else None
            return bool(lead and lead.status == "calculated")

        if task.reminder_type.startswith("draft_"):
            draft_id = context.get("draft_id")
            draft = db.scalar(select(ApplicationDraft).where(ApplicationDraft.draft_id == draft_id)) if draft_id else None
            if not draft or draft.status != "active":
                return False
            if task.reminder_type == "draft_close_3_days":
                draft.status = "closed"
                draft.closed_at = now
                draft.encrypted_payload = None
                draft.updated_at = now
            return True

        if task.reminder_type.startswith("policy_expires"):
            return self._policy_task_relevant(task)

        return True

    def _policy_task_relevant(self, task: ReminderTask) -> bool:
        if not task.telegram_chat_id or not task.bitrix_deal_id:
            return False
        from app.core.config import get_settings
        from app.services.bitrix24_client import POLICY_STATUS_FIELD, SHOW_IN_TELEGRAM_FIELD, Bitrix24Client

        try:
            deal = Bitrix24Client(get_settings().bitrix24_webhook_url).get_deal(task.bitrix_deal_id)
        except Exception as exc:
            logger.warning("policy_reminder_bitrix_check_failed deal_id=%s error=%s", task.bitrix_deal_id, exc)
            return True
        if not deal:
            return False
        show_in_telegram = deal.get(SHOW_IN_TELEGRAM_FIELD)
        if str(show_in_telegram).upper() in {"N", "FALSE", "0"}:
            return False
        policy_status = str(deal.get(POLICY_STATUS_FIELD) or "").strip().lower()
        return policy_status not in {"2609", "аннулирован", "cancelled", "canceled"}

    def _finish_active_drafts(self, telegram_user_id: int, status: str) -> None:
        now = datetime.utcnow()
        with SessionLocal() as db:
            drafts = db.scalars(
                select(ApplicationDraft).where(
                    ApplicationDraft.telegram_user_id == telegram_user_id,
                    ApplicationDraft.status == "active",
                )
            ).all()
            for draft in drafts:
                draft.status = status
                draft.updated_at = now
                if status == "completed":
                    draft.completed_at = now
                elif status == "cancelled":
                    draft.closed_at = now
                draft.encrypted_payload = None
                self._cancel_tasks_with_context(db, "draft_id", draft.draft_id, now)
            db.commit()

    def _cancel_tasks_with_context(self, db, key: str, value: Any, now: datetime) -> None:
        tasks = db.scalars(select(ReminderTask).where(ReminderTask.status == REMINDER_STATUS_PENDING)).all()
        for task in tasks:
            context = self._loads_context(task.context_json)
            if str(context.get(key)) == str(value):
                self._cancel_task(task, now)

    def _cancel_task(self, task: ReminderTask, now: datetime) -> None:
        task.status = REMINDER_STATUS_CANCELLED
        task.cancelled_at = now
        task.updated_at = now

    def _allows_service_notifications(self, db, telegram_user_id: int) -> bool:
        preference = db.scalar(select(NotificationPreference).where(NotificationPreference.telegram_user_id == telegram_user_id))
        return True if preference is None else bool(preference.allow_service_notifications)

    def _dump_safe_context(self, context: dict[str, Any]) -> str:
        return json.dumps(self._safe_context(context), ensure_ascii=False, default=str)

    def _safe_context(self, context: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in context.items():
            if key.lower() in SAFE_CONTEXT_DENYLIST:
                continue
            safe[key] = value
        return safe

    def _loads_context(self, context_json: str | None) -> dict[str, Any]:
        if not context_json:
            return {}
        try:
            loaded = json.loads(context_json)
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}
