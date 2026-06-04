from __future__ import annotations

from typing import Any

from app.services.bitrix24_client import (
    DOCS_REUSE_REQUESTED_FIELD,
    LICENSE_PLATE_FIELD,
    PRODUCT_TYPE_FIELD,
    REPEAT_FROM_DEAL_FIELD,
    REPEAT_MODE_FIELD,
    REQUEST_ID_FIELD,
    SHOW_IN_TELEGRAM_FIELD,
    TELEGRAM_CHAT_ID_FIELD,
)
from app.utils.masking import mask_plate

COUNTRY_FIELD = "UF_CRM_1686152306664"
INSURANCE_START_FIELD = "UF_CRM_1686152149204"
INSURANCE_PERIOD_FIELD = "UF_CRM_1686152209741"
VEHICLE_TYPE_FIELD = "UF_CRM_1686152567597"
VIN_FIELD = "UF_CRM_1686152659867"
BRAND_MODEL_FIELD = "UF_CRM_1686152515152"
MANUFACTURE_YEAR_FIELD = "UF_CRM_1686152614718"
ENGINE_TYPE_FIELD = "UF_CRM_1686152745455"
ENGINE_CAPACITY_FIELD = "UF_CRM_1686152831791"
ENGINE_POWER_FIELD = "UF_CRM_1686152861297"
POWER_UNIT_FIELD = "UF_CRM_1686152902186"

REPEAT_SOURCE_FIELDS = [
    COUNTRY_FIELD,
    VEHICLE_TYPE_FIELD,
    LICENSE_PLATE_FIELD,
    VIN_FIELD,
    BRAND_MODEL_FIELD,
    MANUFACTURE_YEAR_FIELD,
    ENGINE_TYPE_FIELD,
    ENGINE_CAPACITY_FIELD,
    ENGINE_POWER_FIELD,
    POWER_UNIT_FIELD,
]
REPEAT_REQUIRED_FIELDS = [COUNTRY_FIELD, VEHICLE_TYPE_FIELD, LICENSE_PLATE_FIELD]
BLOCKED_STAGE_IDS = {"LOSE"}
BLOCKED_POLICY_STATUS_IDS = {"2609", "2643"}
DOCS_MODE_REUSE = "reuse"
DOCS_MODE_UPLOAD_NEW = "upload_new"
DOCS_MODE_TITLES = {
    DOCS_MODE_REUSE: "использовать документы из предыдущей заявки",
    DOCS_MODE_UPLOAD_NEW: "загрузить новые документы",
}

COUNTRY_TITLES = {
    "529": "Армения",
    "531": "Азербайджан",
    "123": "Беларусь",
    "523": "Грузия",
    "385": "Казахстан",
    "125": "Россия",
    "2253": "Турция",
    "519": "Украина",
    "525": "Узбекистан",
    "521": "Молдова",
    "411": "Другая страна",
}
VEHICLE_TYPE_TITLES = {
    "127": "Легковой автомобиль",
    "453": "Грузовой автомобиль",
    "217": "Мотоцикл",
    "131": "Автобус",
    "129": "Прицеп",
    "457": "Спецтехника",
    "car": "Легковой автомобиль",
    "truck": "Грузовой автомобиль",
    "moto": "Мотоцикл",
    "bus": "Автобус",
    "trailer": "Прицеп",
    "special": "Спецтехника",
}


def repeat_available(deal: dict[str, Any]) -> bool:
    if not _is_visible_in_telegram(deal):
        return False
    if not _is_green_card_product(deal):
        return False
    if str(deal.get("STAGE_ID") or "") in BLOCKED_STAGE_IDS:
        return False
    if _single_value(deal.get("UF_CRM_1718956082020")) in BLOCKED_POLICY_STATUS_IDS:
        return False
    return all(_clean(deal.get(field)) for field in REPEAT_REQUIRED_FIELDS)


def repeat_start_card(draft_id: str, old_deal: dict[str, Any]) -> dict[str, Any]:
    return {
        "draft_id": draft_id,
        "vehicle_plate_masked": mask_plate(_clean(old_deal.get(LICENSE_PLATE_FIELD))),
        "vehicle_type": vehicle_type_title(old_deal.get(VEHICLE_TYPE_FIELD)),
        "registration_country": country_title(old_deal.get(COUNTRY_FIELD)),
        "need_start_date": True,
        "need_period": True,
    }


def repeat_preview(
    old_deal: dict[str, Any], new_start_date: str, new_period_days: int, docs_mode: str
) -> dict[str, Any]:
    return {
        "product": "Green Card",
        "vehicle_plate_masked": mask_plate(_clean(old_deal.get(LICENSE_PLATE_FIELD))),
        "vehicle_type": vehicle_type_title(old_deal.get(VEHICLE_TYPE_FIELD)),
        "registration_country": country_title(old_deal.get(COUNTRY_FIELD)),
        "new_start_date": new_start_date,
        "new_period_days": new_period_days,
        "docs_mode": docs_mode,
        "docs_mode_title": docs_mode_title(docs_mode),
    }


def build_repeat_deal_payload(
    old_deal: dict[str, Any],
    request_id: str,
    new_start_date: str,
    new_period_days: int,
    docs_mode: str,
    telegram_chat_id: int | None = None,
) -> dict[str, Any]:
    old_deal_id = _clean(old_deal.get("ID"))
    masked_plate = mask_plate(_clean(old_deal.get(LICENSE_PLATE_FIELD))) or "—"
    fields: dict[str, Any] = {
        "TITLE": f"Повторное оформление Green Card / {masked_plate} / {new_start_date}",
        "CONTACT_ID": old_deal.get("CONTACT_ID"),
        "COMPANY_ID": old_deal.get("COMPANY_ID"),
        INSURANCE_START_FIELD: new_start_date,
        INSURANCE_PERIOD_FIELD: new_period_days,
        REQUEST_ID_FIELD: request_id,
        SHOW_IN_TELEGRAM_FIELD: "1",
        PRODUCT_TYPE_FIELD: "Green Card",
        REPEAT_FROM_DEAL_FIELD: old_deal_id,
        REPEAT_MODE_FIELD: "repeat",
        DOCS_REUSE_REQUESTED_FIELD: "1" if docs_mode == DOCS_MODE_REUSE else "0",
    }
    if telegram_chat_id:
        fields[TELEGRAM_CHAT_ID_FIELD] = telegram_chat_id
    for field in REPEAT_SOURCE_FIELDS:
        fields[field] = old_deal.get(field)

    fields["COMMENTS"] = _repeat_comment(old_deal_id, docs_mode)
    return {key: value for key, value in fields.items() if value not in (None, "")}


def docs_mode_title(docs_mode: str | None) -> str:
    return DOCS_MODE_TITLES.get(str(docs_mode or ""), "не выбран")


def country_title(value: Any) -> str:
    raw = _single_value(value)
    return COUNTRY_TITLES.get(raw, raw or "—")


def vehicle_type_title(value: Any) -> str:
    raw = _single_value(value)
    return VEHICLE_TYPE_TITLES.get(raw, raw or "—")


def _repeat_comment(old_deal_id: str, docs_mode: str) -> str:
    base = f"Повторное оформление на основании сделки №{old_deal_id}."
    if docs_mode == DOCS_MODE_REUSE:
        return (
            f"{base} Клиент просит использовать документы из сделки №{old_deal_id}. "
            "Оператору необходимо проверить документы перед выпуском полиса."
        )
    return f"{base} Клиент выбрал загрузку новых документов/проверку оператором."


def _is_visible_in_telegram(deal: dict[str, Any]) -> bool:
    value = str(deal.get(SHOW_IN_TELEGRAM_FIELD) or "1").strip().lower()
    return value not in {"0", "n", "false", "no"}


def _is_green_card_product(deal: dict[str, Any]) -> bool:
    value = _single_value(deal.get(PRODUCT_TYPE_FIELD))
    return not value or value.casefold() == "green card"


def _single_value(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("VALUE") or value.get("value") or value.get("ID") or value.get("id")
    if isinstance(value, list):
        return _single_value(value[0]) if value else ""
    return _clean(value)


def _clean(value: Any) -> str:
    return str(value or "").strip()
