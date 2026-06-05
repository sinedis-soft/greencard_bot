from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.db.models import DataDeletionRequest, TelegramBitrixLink
from app.db.session import SessionLocal
from app.services.operator_ticket_service import OperatorTicketService, TicketPayload


class DataDeletionRequestService:
    def __init__(self, ticket_service: OperatorTicketService | None = None) -> None:
        self.ticket_service = ticket_service or OperatorTicketService()

    def create_request(
        self,
        telegram_user_id: int,
        telegram_chat_id: int | None = None,
        bitrix_contact_id: int | None = None,
        client_bot: str = "default",
    ) -> DataDeletionRequest:
        with SessionLocal() as db:
            existing = db.scalar(
                select(DataDeletionRequest).where(
                    DataDeletionRequest.telegram_user_id == telegram_user_id,
                    DataDeletionRequest.status.in_(("new", "in_review")),
                ).order_by(DataDeletionRequest.requested_at.desc())
            )
            if existing:
                db.expunge(existing)
                return existing
            if bitrix_contact_id is None:
                link = db.scalar(select(TelegramBitrixLink).where(TelegramBitrixLink.telegram_user_id == telegram_user_id))
                bitrix_contact_id = link.bitrix_contact_id if link else None
            request = DataDeletionRequest(
                request_id=f"DEL-{uuid4().hex[:12].upper()}",
                telegram_user_id=telegram_user_id,
                bitrix_contact_id=bitrix_contact_id,
                status="new",
            )
            db.add(request)
            db.commit()
            db.refresh(request)
            db.expunge(request)

        self.ticket_service.create_or_get_ticket(
            TicketPayload(
                request_id=request.request_id,
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                bitrix_contact_id=bitrix_contact_id,
                reason="data_deletion_request",
                priority="high",
                client_name="",
                client_phone="",
                preferred_language="ru",
                vehicle_type="",
                license_plate="",
                vin="",
                insurance_period_days=0,
                insurance_start_date="",
                comment="Клиент запросил удаление/анонимизацию данных. Проверьте юридические основания хранения в Bitrix и локальной БД.",
                last_message_preview="Запрос на удаление данных.",
                client_bot=client_bot,
            )
        )
        return request
