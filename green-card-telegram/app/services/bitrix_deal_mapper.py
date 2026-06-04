from __future__ import annotations

from typing import Any

from app.services.bitrix24_client import (
    LICENSE_PLATE_FIELD,
    POLICY_FILES_FIELD,
    POLICY_NUMBER_FIELD,
    POLICY_STATUS_FIELD,
    POLICY_STATUS_VALUES,
    REQUEST_ID_FIELD,
)
from app.services.repeat_deal_mapper import repeat_available
from app.utils.masking import mask_plate

INSURANCE_START_FIELD = "UF_CRM_1686152149204"
INSURANCE_PERIOD_FIELD = "UF_CRM_1686152209741"
VEHICLE_TYPE_FIELD = "UF_CRM_1686152567597"

STAGE_PUBLIC_STATUS = {
    "NEW": "Заявка принята",
    "PREPARATION": "Документы проверяются",
    "WAITING_PAYMENT": "Ожидается оплата",
    "PAYMENT_RECEIVED": "Оплата получена",
    "ISSUING": "Полис оформляется",
    "POLICY_READY": "Полис готов",
    "WON": "Полис отправлен",
    "LOSE": "Заявка закрыта",
}

PAYMENT_STATUS_MARKERS = ("оплат", "payment", "invoice", "счет", "счёт")
POLICY_READY_STATUSES = {"Действующий", "Зарегистрирован", "Полис готов", "Полис отправлен"}


def public_status_text(deal: dict[str, Any]) -> str:
    policy_status = _single_value(deal.get(POLICY_STATUS_FIELD))
    if policy_status:
        return POLICY_STATUS_VALUES.get(str(policy_status), "Статус уточняется")
    stage_id = str(deal.get("STAGE_ID") or "")
    return STAGE_PUBLIC_STATUS.get(stage_id, "Заявка обрабатывается")


def safe_deal_card(deal: dict[str, Any]) -> dict[str, Any]:
    status = public_status_text(deal)
    title = _clean(deal.get("TITLE"))
    request_number = _clean(deal.get(REQUEST_ID_FIELD)) or title or f"Заявка {deal.get('ID')}"
    return {
        "deal_id": _int_or_none(deal.get("ID")),
        "request_number": request_number,
        "product_type": "Green Card",
        "vehicle_plate_masked": mask_plate(_clean(deal.get(LICENSE_PLATE_FIELD))),
        "insurance_start_date": _clean(deal.get(INSURANCE_START_FIELD)) or None,
        "insurance_period_days": _int_or_none(deal.get(INSURANCE_PERIOD_FIELD)),
        "vehicle_type": _clean(deal.get(VEHICLE_TYPE_FIELD)) or None,
        "public_status": status,
        "created_at": _clean(deal.get("DATE_CREATE")) or None,
        "actions": {
            "open": True,
            "contact_operator": True,
            "upload_payment": _can_upload_payment(deal, status),
            "get_policy": _has_policy_files(deal) or status in POLICY_READY_STATUSES,
            "repeat": repeat_available(deal),
            "policy_status": True,
        },
    }


def safe_deal_text(card: dict[str, Any], index: int | None = None) -> str:
    prefix = f"{index}. " if index is not None else ""
    parts = [f"{prefix}{card.get('request_number') or 'Заявка'}"]
    parts.extend(
        [
            f"Тип: {card.get('product_type') or 'Green Card'}",
            f"Авто: {card.get('vehicle_plate_masked') or '—'}",
            f"Дата начала: {card.get('insurance_start_date') or '—'}",
            f"Срок: {_period_text(card.get('insurance_period_days'))}",
            f"Статус: {card.get('public_status') or 'Заявка обрабатывается'}",
            f"Создана: {card.get('created_at') or '—'}",
        ]
    )
    return "\n".join(parts)


def _can_upload_payment(deal: dict[str, Any], status: str) -> bool:
    text = " ".join(
        str(value or "").casefold()
        for value in (deal.get("TITLE"), deal.get("STAGE_ID"), status)
    )
    return any(marker in text for marker in PAYMENT_STATUS_MARKERS)


def _has_policy_files(deal: dict[str, Any]) -> bool:
    value = deal.get(POLICY_FILES_FIELD)
    if isinstance(value, list):
        return bool(value)
    return bool(value)


def _single_value(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("VALUE") or value.get("value") or value.get("ID") or value.get("id")
    if isinstance(value, list):
        return _single_value(value[0]) if value else ""
    return _clean(value)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _int_or_none(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _period_text(value: Any) -> str:
    days = _int_or_none(value)
    if days is None:
        return "—"
    return f"{days} дней"
