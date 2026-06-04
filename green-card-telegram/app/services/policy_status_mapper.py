from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.services.bitrix24_client import POLICY_FILES_FIELD, POLICY_NUMBER_FIELD, POLICY_STATUS_FIELD

POLICY_EXPECTED_AT_FIELD = "UF_CRM_POLICY_EXPECTED_AT"
POLICY_STATUS_REQUEST_REASON = "policy_status_request"
OPEN_POLICY_TICKET_STATUSES = ("new", "in_progress", "waiting_operator", "waiting_client")

POLICY_PUBLIC_MESSAGES = {
    "2607": "Полис действующий.",
    "2609": "Полис аннулирован. Мы передали запрос оператору для уточнения.",
    "2611": "Полис находится в процессе оформления.",
    "2613": "Срок действия полиса завершён.",
    "2643": "В системе отмечен дубликат полиса. Мы передали запрос оператору.",
    "2645": "Полис зарегистрирован.",
}
TICKET_REQUIRED_POLICY_STATUSES = {"2607", "2609", "2643"}
PAYMENT_WAITING_MARKERS = ("WAITING_PAYMENT", "INVOICE", "счет", "счёт", "ожидается оплата")
STAGE_SLA_MINUTES = {
    "PAYMENT_RECEIVED": 20,
    "ISSUING": 30,
    "POLICY_READY": 5,
}
DEFAULT_POLICY_SLA = timedelta(minutes=30)


@dataclass
class PolicyTicketResult:
    created: bool
    already_open: bool
    request_id: str | None = None


def public_policy_status(policy_status: str, has_policy_file: bool) -> str:
    if has_policy_file:
        return "Полис готов."
    return POLICY_PUBLIC_MESSAGES.get(policy_status, "Статус полиса уточняется.")


def build_policy_client_message(
    deal: dict,
    card: dict,
    policy_status: str,
    has_policy_file: bool,
    is_delayed: bool,
    ticket: PolicyTicketResult,
) -> str:
    request_number = card.get("request_number") or "заявка"
    if has_policy_file:
        return (
            "Полис готов.\n\n"
            f"Заявка: {request_number}\n"
            "Статус: полис готов.\n\n"
            "Вы можете получить файл полиса в Telegram."
        )

    if ticket.already_open:
        return (
            "Запрос оператору уже создан. Мы сообщим вам, когда статус изменится.\n\n"
            f"Заявка: {request_number}\n"
            f"Текущий статус: {public_policy_status(policy_status, False)}"
        )

    if _single_value(deal.get(POLICY_NUMBER_FIELD)):
        return (
            "Полис оформлен, но файл ещё не прикреплён. Мы передали запрос оператору.\n\n"
            f"Заявка: {request_number}"
        )

    if _is_waiting_payment(deal):
        return (
            "По этой заявке полис ещё не может быть выпущен, потому что оплата не подтверждена.\n\n"
            "После оплаты загрузите подтверждение."
        )

    if ticket.created or is_delayed:
        return (
            "Полис ещё не готов, срок обработки превышен.\n\n"
            "Мы передали запрос оператору. Вам ответят в этом чате."
        )

    return (
        "Полис ещё оформляется.\n\n"
        f"Заявка: {request_number}\n"
        f"Текущий статус: {public_policy_status(policy_status, False)}\n\n"
        "Обычно это занимает некоторое время после проверки документов и оплаты."
    )


def policy_status_actions(deal: dict, has_policy_file: bool, is_delayed: bool) -> dict[str, bool]:
    waiting_payment = _is_waiting_payment(deal)
    return {
        "get_policy": has_policy_file,
        "send_to_email": has_policy_file,
        "upload_payment": waiting_payment,
        "check_later": not has_policy_file and not is_delayed and not waiting_payment,
        "contact_operator": True,
        "back_to_applications": True,
    }


def should_create_policy_ticket(deal: dict, has_policy_file: bool, is_delayed: bool) -> bool:
    if has_policy_file or _is_waiting_payment(deal):
        return False
    policy_status = _single_value(deal.get(POLICY_STATUS_FIELD))
    if _single_value(deal.get(POLICY_NUMBER_FIELD)):
        return True
    if policy_status in TICKET_REQUIRED_POLICY_STATUSES:
        return True
    if policy_status and policy_status not in POLICY_PUBLIC_MESSAGES:
        return True
    return is_delayed


def detect_policy_delay(deal: dict, has_policy_file: bool) -> bool:
    if has_policy_file or _is_waiting_payment(deal):
        return False
    expected_at = _parse_datetime(deal.get(POLICY_EXPECTED_AT_FIELD))
    if expected_at:
        return datetime.now(timezone.utc) > expected_at
    if _single_value(deal.get(POLICY_NUMBER_FIELD)):
        return True

    created_at = _parse_datetime(deal.get("DATE_CREATE"))
    if not created_at:
        return False
    stage = str(deal.get("STAGE_ID") or "").upper()
    for marker, minutes in STAGE_SLA_MINUTES.items():
        if marker in stage:
            return datetime.now(timezone.utc) - created_at > timedelta(minutes=minutes)
    policy_status = _single_value(deal.get(POLICY_STATUS_FIELD))
    if policy_status in {"2607", "2645"}:
        return datetime.now(timezone.utc) - created_at > timedelta(minutes=5)
    if policy_status in {"2609", "2643"}:
        return True
    return datetime.now(timezone.utc) - created_at > DEFAULT_POLICY_SLA


def _is_waiting_payment(deal: dict) -> bool:
    text = " ".join(str(value or "").casefold() for value in (deal.get("STAGE_ID"), deal.get("TITLE")))
    return any(marker.casefold() in text for marker in PAYMENT_WAITING_MARKERS)


def _has_policy_file(value) -> bool:
    if isinstance(value, list):
        return any(bool(item) for item in value)
    return bool(value)


def _single_value(value) -> str:
    if isinstance(value, dict):
        value = value.get("VALUE") or value.get("value") or value.get("ID") or value.get("id")
    if isinstance(value, list):
        return _single_value(value[0]) if value else ""
    return str(value or "").strip()


def _parse_datetime(value) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for candidate in (raw, raw.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
