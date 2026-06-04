from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, select

from app.db.models import Application, Base, OperatorActionLog, OperatorInternalComment, OperatorTicket, OperatorTicketTransfer
from app.db.session import SessionLocal, engine

OPEN_TICKET_STATUSES = ("new", "in_progress", "waiting_client", "waiting_operator")
QUEUE_ACTIVE_STATUSES = ("new", "in_progress", "waiting_operator")
TICKET_REASON_TITLES = {
    "client_requested_operator": "клиент просит оператора",
    "faq_negative_feedback": "негативная оценка FAQ",
    "payment_confirmation_uploaded": "подтверждение оплаты",
    "payment_request": "запрос оплаты",
    "policy_status_request": "где мой полис",
    "document_correction_needed": "нужен документ",
    "bitrix_sync_failed": "ошибка Bitrix",
    "client_message": "сообщение клиента",
    "policy_delivery_request": "запрос отправки полиса",
    "repeat_application_review": "проверить повторное оформление",
    "repeat_docs_reuse_requested": "проверить старые документы",
    "duplicate_vin_detected": "дубль по VIN",
    "data_deletion_request": "запрос удаления данных",
    "suspicious_activity": "подозрительная активность",
}
TICKET_STATUS_TITLES = {
    "new": "новый",
    "in_progress": "в работе",
    "waiting_client": "ждём клиента",
    "waiting_operator": "клиент ждёт ответа",
    "closed": "закрыто",
    "cancelled": "отменено",
}
REASON_SLA_MINUTES = {
    "client_requested_operator": 10,
    "faq_negative_feedback": 10,
    "payment_confirmation_uploaded": 15,
    "payment_request": 15,
    "policy_status_request": 10,
    "document_correction_needed": 15,
    "bitrix_sync_failed": 5,
    "client_message": 10,
    "policy_delivery_request": 10,
    "repeat_application_review": 30,
    "repeat_docs_reuse_requested": 30,
    "duplicate_vin_detected": 15,
    "data_deletion_request": 60,
    "suspicious_activity": 15,
}
REASON_PRIORITIES = {
    "bitrix_sync_failed": "urgent",
    "payment_confirmation_uploaded": "high",
    "payment_request": "high",
    "policy_status_request": "high",
    "duplicate_vin_detected": "high",
    "data_deletion_request": "high",
    "suspicious_activity": "high",
}
PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2, "low": 3}


@dataclass
class TicketPayload:
    request_id: str
    telegram_user_id: int | None
    client_name: str
    client_phone: str
    preferred_language: str
    vehicle_type: str
    license_plate: str
    vin: str
    insurance_period_days: int
    insurance_start_date: str
    comment: str
    telegram_chat_id: int | None = None
    bitrix_deal_id: int | None = None
    bitrix_contact_id: int | None = None
    reason: str | None = None
    priority: str | None = None
    status: str = "new"
    last_message_preview: str | None = None
    internal_note: str | None = None


class OperatorTicketService:
    def __init__(self) -> None:
        Base.metadata.create_all(bind=engine)

    def create_ticket(self, data: TicketPayload) -> None:
        with SessionLocal() as db:
            ticket_payload = self._ticket_payload(data)
            db.merge(OperatorTicket(**ticket_payload))
            db.commit()

    def create_or_get_ticket(self, data: TicketPayload) -> tuple[OperatorTicket, bool]:
        with SessionLocal() as db:
            existing = self._open_ticket_query(
                data.telegram_user_id,
                data.bitrix_deal_id,
                data.reason,
            )
            ticket = db.scalars(existing).first() if existing is not None else None
            if ticket:
                db.expunge(ticket)
                return ticket, False
            model = OperatorTicket(**self._ticket_payload(data))
            db.merge(model)
            db.commit()
            created = db.get(OperatorTicket, data.request_id)
            if created:
                db.expunge(created)
                return created, True
            return model, True

    def _ticket_payload(self, data: TicketPayload) -> dict[str, Any]:
        now = datetime.utcnow()
        payload = data.__dict__.copy()
        payload.setdefault("first_response_deadline", now + timedelta(minutes=10))
        payload.setdefault("last_client_message_at", now)
        reason = payload.get("reason") or "client_requested_operator"
        payload["reason"] = reason
        payload["priority"] = payload.get("priority") or REASON_PRIORITIES.get(reason, "normal")
        payload["sla_due_at"] = now + timedelta(minutes=REASON_SLA_MINUTES.get(reason, 10))
        payload["last_message_preview"] = _preview(
            payload.get("last_message_preview") or payload.get("comment") or ""
        )
        model_fields = {column.name for column in OperatorTicket.__table__.columns}
        return {key: value for key, value in payload.items() if key in model_fields}

    def _open_ticket_query(
        self, telegram_user_id: int | None, bitrix_deal_id: int | None, reason: str | None
    ):
        if not reason:
            return None
        filters = [OperatorTicket.reason == reason, OperatorTicket.status.in_(OPEN_TICKET_STATUSES)]
        if bitrix_deal_id:
            filters.append(OperatorTicket.bitrix_deal_id == bitrix_deal_id)
        elif telegram_user_id:
            filters.append(OperatorTicket.telegram_user_id == telegram_user_id)
        else:
            return None
        return select(OperatorTicket).where(*filters).order_by(OperatorTicket.created_at.desc())

    def list_new(self) -> list[OperatorTicket]:
        return self.list_tickets("new")

    def list_tickets(self, filter_type: str = "new", operator_id: int | None = None, limit: int = 10) -> list[OperatorTicket]:
        now = datetime.utcnow()
        with SessionLocal() as db:
            stmt = select(OperatorTicket)
            if filter_type == "new":
                stmt = stmt.where(OperatorTicket.status == "new")
            elif filter_type == "mine":
                stmt = stmt.where(
                    OperatorTicket.operator_id == operator_id,
                    OperatorTicket.status.in_(("in_progress", "waiting_operator")),
                )
            elif filter_type == "waiting_operator":
                stmt = stmt.where(OperatorTicket.status == "waiting_operator")
            elif filter_type == "waiting_client":
                stmt = stmt.where(OperatorTicket.status == "waiting_client")
            elif filter_type == "sla":
                stmt = stmt.where(
                    OperatorTicket.status.in_(QUEUE_ACTIVE_STATUSES),
                    (OperatorTicket.sla_breach == True) | (OperatorTicket.sla_due_at <= now),
                )
            elif filter_type == "bitrix_errors":
                stmt = stmt.where(
                    OperatorTicket.reason == "bitrix_sync_failed",
                    OperatorTicket.status.in_(OPEN_TICKET_STATUSES),
                )
            else:
                stmt = stmt.where(OperatorTicket.status.in_(OPEN_TICKET_STATUSES))

            priority_case = case(PRIORITY_ORDER, value=OperatorTicket.priority, else_=9)
            stmt = stmt.order_by(
                OperatorTicket.sla_breach.desc(),
                priority_case.asc(),
                OperatorTicket.created_at.asc(),
            ).limit(limit)
            items = list(db.scalars(stmt))
            for item in items:
                db.expunge(item)
            return items

    def queue_counts(self, operator_id: int) -> dict[str, int]:
        now = datetime.utcnow()
        with SessionLocal() as db:
            all_items = list(db.scalars(select(OperatorTicket).where(OperatorTicket.status.in_(OPEN_TICKET_STATUSES))))
        return {
            "new": sum(1 for t in all_items if t.status == "new"),
            "mine": sum(1 for t in all_items if t.operator_id == operator_id and t.status in {"in_progress", "waiting_operator"}),
            "waiting_operator": sum(1 for t in all_items if t.status == "waiting_operator"),
            "sla": sum(1 for t in all_items if t.status in QUEUE_ACTIVE_STATUSES and (t.sla_breach or (t.sla_due_at and t.sla_due_at <= now))),
            "bitrix_errors": sum(1 for t in all_items if t.reason == "bitrix_sync_failed"),
            "waiting_client": sum(1 for t in all_items if t.status == "waiting_client"),
        }

    def set_status(self, request_id: str, status: str) -> bool:
        with SessionLocal() as db:
            ticket = db.get(OperatorTicket, request_id)
            if not ticket:
                return False
            ticket.status = status
            now = datetime.utcnow()
            if status == "closed":
                ticket.closed_at = now
            if status == "waiting_client":
                ticket.last_operator_message_at = now
            if status == "waiting_operator":
                ticket.last_client_message_at = now
            db.commit()
            return True

    def take_ticket(self, request_id: str, operator_id: int) -> tuple[bool, str]:
        with SessionLocal() as db:
            ticket = db.get(OperatorTicket, request_id)
            if not ticket:
                return False, "ticket_not_found"
            if ticket.operator_id and ticket.operator_id != operator_id:
                return False, "already_assigned"
            now = datetime.utcnow()
            ticket.previous_operator_id = ticket.operator_id if ticket.operator_id != operator_id else ticket.previous_operator_id
            ticket.operator_id = operator_id
            ticket.assigned_at = ticket.assigned_at or now
            ticket.assigned_by_operator_id = ticket.assigned_by_operator_id or operator_id
            ticket.status = "in_progress"
            ticket.taken_at = ticket.taken_at or now
            if not ticket.first_response_at:
                ticket.first_response_at = now
            db.commit()
            return True, "taken"

    def close_ticket(self, request_id: str, operator_id: int, close_reason: str = "resolved") -> bool:
        with SessionLocal() as db:
            ticket = db.get(OperatorTicket, request_id)
            if not ticket:
                return False
            if ticket.operator_id and ticket.operator_id != operator_id:
                return False
            ticket.status = "closed"
            ticket.closed_at = datetime.utcnow()
            ticket.close_reason = close_reason
            db.commit()
            return True

    def assign_operator_if_empty(self, request_id: str, operator_id: int) -> int | None:
        with SessionLocal() as db:
            ticket = db.get(OperatorTicket, request_id)
            if not ticket:
                return None
            if ticket.operator_id is None:
                now = datetime.utcnow()
                ticket.operator_id = operator_id
                ticket.assigned_at = ticket.assigned_at or now
                ticket.assigned_by_operator_id = ticket.assigned_by_operator_id or operator_id
                ticket.taken_at = ticket.taken_at or now
                db.commit()
                return operator_id
            return ticket.operator_id

    def get_ticket(self, request_id: str) -> OperatorTicket | None:
        with SessionLocal() as db:
            ticket = db.get(OperatorTicket, request_id)
            if ticket:
                db.expunge(ticket)
            return ticket

    def get_active_by_user(self, telegram_user_id: int) -> OperatorTicket | None:
        with SessionLocal() as db:
            ticket = db.scalars(
                select(OperatorTicket)
                .where(
                    OperatorTicket.telegram_user_id == telegram_user_id,
                    OperatorTicket.status.in_(("new", "in_progress", "waiting_client", "waiting_operator")),
                )
                .order_by(OperatorTicket.created_at.desc())
            ).first()
            if ticket:
                db.expunge(ticket)
            return ticket

    def get_open_by_deal_reason(
        self,
        bitrix_deal_id: int,
        reason: str,
        statuses: tuple[str, ...] = OPEN_TICKET_STATUSES,
    ) -> OperatorTicket | None:
        with SessionLocal() as db:
            ticket = db.scalars(
                select(OperatorTicket)
                .where(
                    OperatorTicket.bitrix_deal_id == bitrix_deal_id,
                    OperatorTicket.reason == reason,
                    OperatorTicket.status.in_(statuses),
                )
                .order_by(OperatorTicket.created_at.desc())
            ).first()
            if ticket:
                db.expunge(ticket)
            return ticket

    def get_client_username(self, telegram_user_id: int | None) -> str:
        if not telegram_user_id:
            return ""
        with SessionLocal() as db:
            username = db.scalars(
                select(Application.telegram_username)
                .where(
                    Application.telegram_user_id == telegram_user_id,
                    Application.telegram_username.is_not(None),
                )
                .order_by(Application.updated_at.desc())
            ).first()
        return str(username or "").strip()

    def mark_client_message(self, request_id: str, preview: str = "") -> None:
        with SessionLocal() as db:
            ticket = db.get(OperatorTicket, request_id)
            if not ticket:
                return
            ticket.last_client_message_at = datetime.utcnow()
            ticket.last_message_preview = _preview(preview) or ticket.last_message_preview
            if ticket.status == "waiting_client":
                ticket.status = "waiting_operator"
            db.commit()

    def log_action(
        self,
        request_id: str,
        operator_id: int,
        action: str,
        message: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        with SessionLocal() as db:
            db.add(
                OperatorActionLog(
                    request_id=request_id,
                    operator_id=operator_id,
                    action=action,
                    message=message,
                    details_json=json.dumps(details or {}, ensure_ascii=False) if details else None,
                )
            )
            db.commit()


    def can_transfer_ticket(
        self, request_id: str, operator_id: int, privileged_operator_ids: set[int] | None = None
    ) -> bool:
        ticket = self.get_ticket(request_id)
        if not ticket:
            return False
        if operator_id in (privileged_operator_ids or set()):
            return True
        return ticket.operator_id in (None, operator_id)

    def transfer_ticket(
        self,
        request_id: str,
        from_operator_id: int,
        to_operator_id: int | None,
        reason: str,
        privileged_operator_ids: set[int] | None = None,
    ) -> tuple[bool, str, OperatorTicket | None]:
        with SessionLocal() as db:
            ticket = db.get(OperatorTicket, request_id)
            if not ticket:
                return False, "ticket_not_found", None
            if (
                ticket.operator_id not in (None, from_operator_id)
                and from_operator_id not in (privileged_operator_ids or set())
            ):
                return False, "forbidden", None
            now = datetime.utcnow()
            old_operator_id = ticket.operator_id
            ticket.previous_operator_id = old_operator_id
            ticket.operator_id = to_operator_id
            ticket.assigned_at = now if to_operator_id else None
            ticket.assigned_by_operator_id = from_operator_id
            ticket.transfer_reason = reason
            ticket.transferred_at = now
            db.add(
                OperatorTicketTransfer(
                    ticket_id=request_id,
                    from_operator_id=old_operator_id,
                    to_operator_id=to_operator_id,
                    transferred_by_operator_id=from_operator_id,
                    reason=reason,
                    created_at=now,
                )
            )
            db.add(
                OperatorActionLog(
                    request_id=request_id,
                    operator_id=from_operator_id,
                    action="ticket_transferred",
                    details_json=json.dumps(
                        {
                            "from_operator_id": old_operator_id,
                            "to_operator_id": to_operator_id,
                            "reason": reason,
                        },
                        ensure_ascii=False,
                    ),
                )
            )
            db.commit()
            db.refresh(ticket)
            db.expunge(ticket)
            return True, "transferred", ticket

    def list_transfers(self, request_id: str, limit: int = 10) -> list[OperatorTicketTransfer]:
        with SessionLocal() as db:
            items = list(
                db.scalars(
                    select(OperatorTicketTransfer)
                    .where(OperatorTicketTransfer.ticket_id == request_id)
                    .order_by(OperatorTicketTransfer.created_at.desc())
                    .limit(limit)
                )
            )
            for item in items:
                db.expunge(item)
            return items

    def add_internal_comment(
        self,
        request_id: str,
        operator_id: int,
        comment_text: str,
        comment_type: str = "general",
        is_pinned: bool = False,
    ) -> OperatorInternalComment | None:
        text = str(comment_text or "").strip()
        if not text:
            return None
        with SessionLocal() as db:
            ticket = db.get(OperatorTicket, request_id)
            if not ticket:
                return None
            now = datetime.utcnow()
            comment = OperatorInternalComment(
                ticket_id=request_id,
                bitrix_deal_id=ticket.bitrix_deal_id,
                operator_id=operator_id,
                comment_text=text,
                comment_type=comment_type,
                is_pinned=is_pinned,
                created_at=now,
                updated_at=now,
            )
            db.add(comment)
            db.add(
                OperatorActionLog(
                    request_id=request_id,
                    operator_id=operator_id,
                    action="internal_comment_added",
                    details_json=json.dumps(
                        {"comment_type": comment_type, "is_pinned": is_pinned},
                        ensure_ascii=False,
                    ),
                )
            )
            db.commit()
            db.refresh(comment)
            db.expunge(comment)
            return comment

    def list_internal_comments(
        self, request_id: str, include_deleted: bool = False, limit: int = 20
    ) -> list[OperatorInternalComment]:
        with SessionLocal() as db:
            stmt = select(OperatorInternalComment).where(OperatorInternalComment.ticket_id == request_id)
            if not include_deleted:
                stmt = stmt.where(OperatorInternalComment.deleted_at.is_(None))
            stmt = stmt.order_by(
                OperatorInternalComment.is_pinned.desc(),
                OperatorInternalComment.created_at.desc(),
            ).limit(limit)
            items = list(db.scalars(stmt))
            for item in items:
                db.expunge(item)
            return items

    def pinned_internal_comments(self, request_id: str, limit: int = 3) -> list[OperatorInternalComment]:
        with SessionLocal() as db:
            items = list(
                db.scalars(
                    select(OperatorInternalComment)
                    .where(
                        OperatorInternalComment.ticket_id == request_id,
                        OperatorInternalComment.is_pinned == True,
                        OperatorInternalComment.deleted_at.is_(None),
                    )
                    .order_by(OperatorInternalComment.created_at.desc())
                    .limit(limit)
                )
            )
            for item in items:
                db.expunge(item)
            return items


def _preview(value: str, limit: int = 500) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]
