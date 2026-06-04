from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db.models import RepeatApplicationDraft
from app.db.session import SessionLocal
from app.services.bitrix24_client import Bitrix24Client
from app.services.client_application_service import ClientApplicationService
from app.services.repeat_deal_mapper import (
    DOCS_MODE_REUSE,
    DOCS_MODE_UPLOAD_NEW,
    build_repeat_deal_payload,
    repeat_available,
    repeat_preview,
    repeat_start_card,
)

ALLOWED_REPEAT_PERIODS = {30, 60, 90, 180, 365}
DRAFT_TTL = timedelta(minutes=60)
MAX_START_DATE_DAYS = 366 * 5
VILNIUS_TZ = ZoneInfo("Europe/Vilnius")


class RepeatApplicationError(ValueError):
    pass


@dataclass
class RepeatConfirmResult:
    request_id: str
    bitrix_deal_id: int
    public_status: str = "Заявка принята"


class RepeatApplicationService:
    def __init__(self, bitrix_client: Bitrix24Client):
        self.bitrix_client = bitrix_client
        self.client_applications = ClientApplicationService(bitrix_client)

    def start(
        self,
        telegram_user_id: int,
        old_deal_id: int,
        telegram_chat_id: int | None = None,
    ) -> dict:
        old_deal = self._verified_old_deal(telegram_user_id, old_deal_id, telegram_chat_id)
        if not repeat_available(old_deal):
            raise RepeatApplicationError("repeat_not_available")

        draft_id = f"rep_{uuid4().hex[:16]}"
        now = datetime.utcnow()
        with SessionLocal() as db:
            db.add(
                RepeatApplicationDraft(
                    id=draft_id,
                    telegram_user_id=telegram_user_id,
                    old_bitrix_deal_id=old_deal_id,
                    status="draft",
                    created_at=now,
                    updated_at=now,
                    expires_at=now + DRAFT_TTL,
                )
            )
            db.commit()
        self.client_applications.log_action(
            telegram_user_id, "repeat_application_started", old_deal_id
        )
        return repeat_start_card(draft_id, old_deal)

    def update(
        self,
        draft_id: str,
        telegram_user_id: int,
        new_start_date: str | None = None,
        new_period_days: int | None = None,
        docs_mode: str | None = None,
    ) -> dict:
        draft = self._get_active_draft(draft_id, telegram_user_id)
        if new_start_date is not None:
            draft.new_start_date = self._normalize_start_date(new_start_date)
        if new_period_days is not None:
            draft.new_period_days = self._validate_period(new_period_days)
        if docs_mode is not None:
            draft.docs_mode = self._validate_docs_mode(docs_mode)
        draft.updated_at = datetime.utcnow()
        with SessionLocal() as db:
            db.merge(draft)
            db.commit()
        return self.preview(draft_id, telegram_user_id)

    def preview(self, draft_id: str, telegram_user_id: int) -> dict:
        draft = self._get_active_draft(draft_id, telegram_user_id)
        old_deal = self._verified_old_deal(
            telegram_user_id, draft.old_bitrix_deal_id, None
        )
        if not draft.new_start_date or not draft.new_period_days or not draft.docs_mode:
            preview = repeat_preview(
                old_deal,
                draft.new_start_date or "",
                draft.new_period_days or 0,
                draft.docs_mode or "",
            )
            preview["complete"] = False
            return preview
        preview = repeat_preview(
            old_deal, draft.new_start_date, draft.new_period_days, draft.docs_mode
        )
        preview["complete"] = True
        return preview

    def confirm(
        self,
        draft_id: str,
        telegram_user_id: int,
        telegram_chat_id: int | None = None,
    ) -> RepeatConfirmResult:
        draft = self._get_active_draft(draft_id, telegram_user_id)
        if not draft.new_start_date or not draft.new_period_days or not draft.docs_mode:
            raise RepeatApplicationError("repeat_draft_incomplete")
        old_deal = self._verified_old_deal(
            telegram_user_id, draft.old_bitrix_deal_id, telegram_chat_id
        )
        if not repeat_available(old_deal):
            raise RepeatApplicationError("repeat_not_available")

        request_id = f"rep-{uuid4().hex[:12]}"
        payload = build_repeat_deal_payload(
            old_deal=old_deal,
            request_id=request_id,
            new_start_date=draft.new_start_date,
            new_period_days=draft.new_period_days,
            docs_mode=draft.docs_mode,
            telegram_chat_id=telegram_chat_id,
        )
        new_deal_id = self.bitrix_client.create_deal(payload)
        draft.status = "created"
        draft.updated_at = datetime.utcnow()
        with SessionLocal() as db:
            db.merge(draft)
            db.commit()
        self.client_applications.log_action(
            telegram_user_id, "repeat_application_confirmed", new_deal_id
        )
        return RepeatConfirmResult(request_id=request_id, bitrix_deal_id=new_deal_id)

    def _verified_old_deal(
        self,
        telegram_user_id: int,
        old_deal_id: int | str,
        telegram_chat_id: int | None = None,
    ) -> dict:
        old_deal = self.client_applications.get_client_deal(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            deal_id=old_deal_id,
        )
        if not old_deal:
            raise RepeatApplicationError("application_not_found")
        return old_deal

    def _get_active_draft(self, draft_id: str, telegram_user_id: int) -> RepeatApplicationDraft:
        with SessionLocal() as db:
            draft = db.scalar(
                select(RepeatApplicationDraft).where(
                    RepeatApplicationDraft.id == draft_id,
                    RepeatApplicationDraft.telegram_user_id == telegram_user_id,
                    RepeatApplicationDraft.status == "draft",
                )
            )
            if not draft:
                raise RepeatApplicationError("repeat_draft_not_found")
            if draft.expires_at <= datetime.utcnow():
                draft.status = "expired"
                db.commit()
                raise RepeatApplicationError("repeat_draft_expired")
            db.expunge(draft)
            return draft

    def _normalize_start_date(self, value: str) -> str:
        raw = str(value or "").strip()
        parsed: date | None = None
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            raise RepeatApplicationError("invalid_start_date")
        today = datetime.now(VILNIUS_TZ).date()
        if parsed < today:
            raise RepeatApplicationError("start_date_in_past")
        if parsed > today + timedelta(days=MAX_START_DATE_DAYS):
            raise RepeatApplicationError("start_date_too_far")
        return parsed.isoformat()

    def _validate_period(self, value: int) -> int:
        try:
            period = int(value)
        except (TypeError, ValueError) as exc:
            raise RepeatApplicationError("invalid_period") from exc
        if period not in ALLOWED_REPEAT_PERIODS:
            raise RepeatApplicationError("invalid_period")
        return period

    def _validate_docs_mode(self, value: str) -> str:
        docs_mode = str(value or "").strip()
        if docs_mode not in {DOCS_MODE_REUSE, DOCS_MODE_UPLOAD_NEW}:
            raise RepeatApplicationError("invalid_docs_mode")
        return docs_mode
