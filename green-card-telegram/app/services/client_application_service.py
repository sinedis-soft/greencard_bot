from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.db.models import ClientActionLog, TelegramBitrixLink
from app.db.session import SessionLocal
from app.services.bitrix24_client import (
    Bitrix24Client,
    SHOW_IN_TELEGRAM_FIELD,
    TELEGRAM_CHAT_ID_FIELD,
    TELEGRAM_USER_ID_FIELD,
)
from app.services.bitrix_deal_mapper import safe_deal_card


class ClientApplicationService:
    def __init__(self, bitrix_client: Bitrix24Client):
        self.bitrix_client = bitrix_client

    def get_or_resolve_bitrix_contact_id(
        self, telegram_user_id: int, telegram_chat_id: int | None = None
    ) -> int | None:
        with SessionLocal() as db:
            link = db.scalar(
                select(TelegramBitrixLink).where(
                    TelegramBitrixLink.telegram_user_id == telegram_user_id
                )
            )
            if link and link.bitrix_contact_id:
                if telegram_chat_id and link.telegram_chat_id != telegram_chat_id:
                    link.telegram_chat_id = telegram_chat_id
                    link.updated_at = datetime.utcnow()
                    db.commit()
                return int(link.bitrix_contact_id)

        contact = self.bitrix_client.find_contact_by_telegram_identity(
            user_id=telegram_user_id
        )
        if not contact or not contact.get("ID"):
            return None

        contact_id = int(contact["ID"])
        chat_id = telegram_chat_id or _int_or_none(contact.get(TELEGRAM_CHAT_ID_FIELD)) or telegram_user_id
        with SessionLocal() as db:
            link = db.scalar(
                select(TelegramBitrixLink).where(
                    TelegramBitrixLink.telegram_user_id == telegram_user_id
                )
            )
            now = datetime.utcnow()
            if link:
                link.telegram_chat_id = chat_id
                link.bitrix_contact_id = contact_id
                link.last_verified_at = now
            else:
                db.add(
                    TelegramBitrixLink(
                        telegram_user_id=telegram_user_id,
                        telegram_chat_id=chat_id,
                        bitrix_contact_id=contact_id,
                        last_verified_at=now,
                    )
                )
            db.commit()
        return contact_id

    def list_my_applications(
        self, telegram_user_id: int, telegram_chat_id: int | None = None, limit: int = 10
    ) -> dict[str, Any]:
        self.log_action(telegram_user_id, "my_applications_opened")
        contact_id = self.get_or_resolve_bitrix_contact_id(telegram_user_id, telegram_chat_id)
        if not contact_id:
            return {"items": [], "total": 0}

        try:
            deals = self.bitrix_client.list_deals_by_contact_id(
                contact_id, limit=limit, show_in_telegram_only=True
            )
        except RuntimeError as exc:
            if SHOW_IN_TELEGRAM_FIELD not in str(exc):
                raise
            deals = self.bitrix_client.list_deals_by_contact_id(
                contact_id, limit=limit, show_in_telegram_only=False
            )

        items = [safe_deal_card(deal) for deal in deals]
        return {"items": items, "total": len(items)}

    def get_client_deal(
        self, telegram_user_id: int, deal_id: int | str, telegram_chat_id: int | None = None
    ) -> dict[str, Any] | None:
        contact_id = self.get_or_resolve_bitrix_contact_id(telegram_user_id, telegram_chat_id)
        if not contact_id:
            return None
        deal = self.bitrix_client.get_deal(deal_id)
        if not deal:
            return None
        if str(deal.get("CONTACT_ID") or "") != str(contact_id):
            return None
        show_value = str(deal.get(SHOW_IN_TELEGRAM_FIELD) or "1").strip().lower()
        if show_value in {"0", "n", "false", "no"}:
            return None
        self.log_action(telegram_user_id, "application_opened", _int_or_none(deal_id))
        return deal

    def log_action(
        self, telegram_user_id: int, action: str, bitrix_deal_id: int | None = None
    ) -> None:
        with SessionLocal() as db:
            db.add(
                ClientActionLog(
                    telegram_user_id=telegram_user_id,
                    action=action,
                    bitrix_deal_id=bitrix_deal_id,
                )
            )
            db.commit()


def _int_or_none(value: object) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
