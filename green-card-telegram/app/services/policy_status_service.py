from __future__ import annotations

from uuid import uuid4

from app.services.bitrix24_client import (
    POLICY_FILES_FIELD,
    POLICY_NUMBER_FIELD,
    POLICY_STATUS_FIELD,
    POLICY_STATUS_VALUES,
)
from app.services.bitrix_deal_mapper import safe_deal_card
from app.services.client_application_service import ClientApplicationService
from app.services.operator_message_formatter import operator_language_line
from app.services.operator_notifier_service import OperatorNotifierService
from app.services.operator_ticket_service import OperatorTicketService, TicketPayload
from app.services.policy_status_mapper import (
    OPEN_POLICY_TICKET_STATUSES,
    POLICY_STATUS_REQUEST_REASON,
    PolicyTicketResult,
    build_policy_client_message,
    detect_policy_delay,
    policy_status_actions,
    public_policy_status,
    should_create_policy_ticket,
    _has_policy_file,
    _single_value,
)


class PolicyStatusError(ValueError):
    pass


class PolicyStatusService:
    def __init__(self, client_applications: ClientApplicationService):
        self.client_applications = client_applications
        self.ticket_service = OperatorTicketService()

    def check(
        self,
        telegram_user_id: int,
        deal_id: int,
        telegram_chat_id: int | None = None,
        preferred_language: str = "ru",
        client_name: str = "",
        notify_operator: bool = True,
    ) -> dict:
        deal = self.client_applications.get_client_deal(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            deal_id=deal_id,
        )
        if not deal:
            raise PolicyStatusError("application_not_found")

        card = safe_deal_card(deal)
        policy_status = _single_value(deal.get(POLICY_STATUS_FIELD))
        policy_number = _single_value(deal.get(POLICY_NUMBER_FIELD)) or None
        has_policy_file = _has_policy_file(deal.get(POLICY_FILES_FIELD))
        is_delayed = detect_policy_delay(deal, has_policy_file=has_policy_file)

        ticket = PolicyTicketResult(created=False, already_open=False)
        if should_create_policy_ticket(deal, has_policy_file=has_policy_file, is_delayed=is_delayed):
            ticket = self._create_or_get_ticket(
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                deal=deal,
                card=card,
                is_delayed=is_delayed,
                preferred_language=preferred_language,
                client_name=client_name,
                notify_operator=notify_operator,
            )

        message = build_policy_client_message(
            deal=deal,
            card=card,
            policy_status=policy_status,
            has_policy_file=has_policy_file,
            is_delayed=is_delayed,
            ticket=ticket,
        )
        self.client_applications.log_action(
            telegram_user_id, "policy_status_checked", int(card["deal_id"]) if card.get("deal_id") else None
        )
        return {
            "deal_id": card.get("deal_id"),
            "request_number": card.get("request_number"),
            "public_status": public_policy_status(policy_status, has_policy_file),
            "policy_number": policy_number,
            "has_policy_file": has_policy_file,
            "is_delayed": is_delayed,
            "operator_ticket_created": ticket.created,
            "operator_ticket_already_open": ticket.already_open,
            "message": message,
            "actions": policy_status_actions(
                deal=deal,
                has_policy_file=has_policy_file,
                is_delayed=is_delayed,
            ),
        }

    def _create_or_get_ticket(
        self,
        telegram_user_id: int,
        telegram_chat_id: int | None,
        deal: dict,
        card: dict,
        is_delayed: bool,
        preferred_language: str,
        client_name: str,
        notify_operator: bool,
    ) -> PolicyTicketResult:
        deal_id = int(card["deal_id"])
        existing = self.ticket_service.get_open_by_deal_reason(
            deal_id, POLICY_STATUS_REQUEST_REASON, OPEN_POLICY_TICKET_STATUSES
        )
        if existing:
            return PolicyTicketResult(created=False, already_open=True, request_id=existing.request_id)

        request_id = f"policy-{deal_id}-{uuid4().hex[:8]}"
        self.ticket_service.create_ticket(
            TicketPayload(
                request_id=request_id,
                telegram_user_id=telegram_user_id,
                telegram_chat_id=telegram_chat_id,
                bitrix_deal_id=deal_id,
                reason=POLICY_STATUS_REQUEST_REASON,
                client_name=client_name,
                client_phone="",
                preferred_language=preferred_language,
                vehicle_type=str(card.get("product_type") or "OC graniczne (border insurance)"),
                license_plate=str(card.get("vehicle_plate_masked") or ""),
                vin="",
                insurance_period_days=int(card.get("insurance_period_days") or 0),
                insurance_start_date=str(card.get("insurance_start_date") or ""),
                comment=f"Где мой полис? Bitrix deal {deal_id}. Delayed: {'yes' if is_delayed else 'no'}",
            )
        )
        if notify_operator:
            self._notify_operator(request_id, deal, card, is_delayed, preferred_language)
        return PolicyTicketResult(created=True, already_open=False, request_id=request_id)

    def _notify_operator(self, request_id: str, deal: dict, card: dict, is_delayed: bool, lang: str) -> None:
        status_id = _single_value(deal.get(POLICY_STATUS_FIELD))
        status_title = POLICY_STATUS_VALUES.get(status_id, status_id or "—")
        OperatorNotifierService().notify_new_ticket(
            "🧾 Клиент спрашивает: «Где мой полис?»\n\n"
            f"ID тикета: {request_id}\n"
            f"Заявка: {card.get('request_number') or '—'}\n"
            f"Сделка Bitrix: {card.get('deal_id') or '—'}\n"
            f"Авто: {card.get('vehicle_plate_masked') or '—'}\n"
            f"Дата начала: {card.get('insurance_start_date') or '—'}\n"
            f"Статус сделки: {card.get('public_status') or '—'}\n"
            f"Статус полиса: {status_title}\n"
            f"Файл полиса: {'есть' if _has_policy_file(deal.get(POLICY_FILES_FIELD)) else 'отсутствует'}\n"
            f"Задержка: {'да' if is_delayed else 'нет'}\n"
            f"{operator_language_line(lang)}",
        )
