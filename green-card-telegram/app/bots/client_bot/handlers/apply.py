import locale as pylocale
import logging
import re
import tempfile

from datetime import datetime, date, time, timedelta
from pathlib import Path


from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_calendar import (
    DialogCalendar,
    DialogCalendarCallback,
    SimpleCalendar,
    SimpleCalendarCallback,
    get_user_locale,
)


from app.bots.client_bot.keyboards.apply import (
    company_confirm_keyboard,
    company_select_keyboard,
    consent_keyboard,
    countries_keyboard,
    data_actual_keyboard,
    fuel_types_keyboard,
    finalize_vehicle_keyboard,
    periods_keyboard,
    policyholder_type_keyboard,
    power_units_keyboard,
    prefill_next_keyboard,
    skip_comment_keyboard,

    techpass_changed_keyboard,
    vehicle_types_keyboard,
    vehicle_docs_complete_keyboard,
)
from app.core.config import app_root
from app.schemas.application import ApplicationCreate
from app.services.i18n_service import I18nService
from app.services.bitrix_file_service import BitrixFileService
from app.services.bitrix24_client import (
    PRODUCT_TYPE_FIELD,
    SHOW_IN_TELEGRAM_FIELD,
    TELEGRAM_CHAT_ID_FIELD,
    TELEGRAM_USERNAME_FIELD,
    TELEGRAM_USER_ID_FIELD,
)
from app.bots.client_bot.menu_actions import menu_action_for_text
from app.services.lead_service import LeadService
from app.services.operator_notifier_service import OperatorNotifierService
from app.validation import (
    is_latin_name,
    is_license_plate,
    is_license_plate_long,
    is_passport_number,
    is_vin,
    normalize_license_plate,
    normalize_passport,
    normalize_vin,
)

router = Router()
logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

BITRIX_COUNTRY_MAP = {
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
    "США": "Другая страна",
    "Великобритания": "Другая страна",
    "USA": "Другая страна",
    "United Kingdom": "Другая страна",
    "other country (Другая страна)": "Другая страна",
}
EUROPOLIS_COMPANY_COUNTRY_FIELD = "UF_CRM_1720721997376"
EUROPOLIS_COMPANY_COUNTRY_IDS = {
    "беларусь": "2685",
    "россия": "2687",
    "казахстан": "2689",
    "грузия": "2691",
    "литва": "2693",
    "латвия": "2695",
    "польша": "2697",
    "украина": "2699",
    "узбекистан": "2701",
    "кыргыстан": "2703",
    "кыргызстан": "2703",
    "монголия": "2705",
    "молдова": "2707",
    "азербайджан": "2709",
    "чехия": "2711",
    "великобритания": "3021",
    "великобрита́ния": "3021",
    "другое": "2713",
    "другая страна": "2713",
    "сша": "2713",
    "usa": "2713",
    "united states": "2713",
    "united kingdom": "3021",
    "германия": "3025",
    "испания": "3027",
    "китай": "3031",
    "финляндия": "3033",
    "турция": "3035",
}
EUROPOLIS_COMPANY_COUNTRY_TITLES = {
    "2685": "Беларусь",
    "2687": "Россия",
    "2689": "Казахстан",
    "2691": "Грузия",
    "2693": "Литва",
    "2695": "Латвия",
    "2697": "Польша",
    "2699": "Украина",
    "2701": "Узбекистан",
    "2703": "Кыргыстан",
    "2705": "Монголия",
    "2707": "Молдова",
    "2709": "Азербайджан",
    "2711": "Чехия",
    "3021": "Великобритания",
    "2713": "Другое",
    "3025": "Германия",
    "3027": "Испания",
    "3031": "Китай",
    "3033": "Финляндия",
    "3035": "Турция",
}


def _normalize_country_key(value: object) -> str:
    return str(value or "").strip().lower().replace("́", "")


def _europolis_company_country_id(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.isdigit():
        return raw
    return EUROPOLIS_COMPANY_COUNTRY_IDS.get(_normalize_country_key(raw), "2713")


def _europolis_company_country_title(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.isdigit():
        return EUROPOLIS_COMPANY_COUNTRY_TITLES.get(raw, raw)
    return raw


BITRIX_VTYPE_MAP = {
    "127": "Легковой",
    "453": "Грузовой",
    "217": "Мотоцикл",
    "131": "Автобус",
    "129": "Прицеп",
}
BITRIX_POWER_UNIT_MAP = {"145": "Киловат", "147": "Лошадиные силы"}
BITRIX_FUEL_MAP = {
    "133": "Бензин",
    "135": "Дизель",
    "137": "Газ / бензин",
    "139": "Электро",
    "141": "Гибрид",
    "petrol": "Бензин",
    "diesel": "Дизель",
    "gas": "Газ / бензин",
    "gasoline": "Газ / бензин",
    "electric": "Электро",
    "hybrid": "Гибрид",
}
FUEL_TYPES = {"Бензин", "Дизель", "Газ / бензин", "Электро", "Гибрид"}
POWER_UNITS = {"Лошадиные силы", "Киловат"}
CALENDAR_LOCALES = {
    "be": "be_BY",
    "by": "be_BY",
    "en": "en_US",
    "fa": "fa_IR",
    "hy": "hy_AM",
    "ka": "ka_GE",
    "kk": "kk_KZ",
    "mn": "mn_MN",
    "ro": "ro_RO",
    "ru": "ru_RU",
    "tr": "tr_TR",
    "uk": "uk_UA",
    "uz": "uz_UZ",
}
INSURANCE_START_MAX_DAYS = 366 * 5



def _is_europolis_data(data: dict) -> bool:
    return data.get("client_bot") == "europolis"


def _is_europolis_bot(bot) -> bool:
    return getattr(bot, "client_bot_code", "default") == "europolis"


def _text_or_default(i18n: I18nService, lang: str, key: str, default: str) -> str:
    text = i18n.get_text(lang, key)
    return default if text == key else text

def _map_bitrix_enum(value: object, mapping: dict[str, str]) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    return mapping.get(raw, raw)



def _bitrix_ids_match(left: object, right: object) -> bool:
    if left is None or right is None:
        return False
    return str(left).strip() == str(right).strip()


def _normalize_passport(value: object) -> str:
    return normalize_passport(value)


def _contact_state_data(contact: dict) -> dict:
    return {
        "first_name": str(contact.get("NAME", "")).strip(),
        "last_name": str(contact.get("LAST_NAME", "")).strip(),
        "birth_date": _birthdate_to_ddmmyyyy(str(contact.get("BIRTHDATE", "")).strip()),
        "registration_address": str(contact.get("ADDRESS", "")).strip(),
        "phone": _extract_multifield(contact.get("PHONE")),
        "email": _extract_multifield(contact.get("EMAIL")),
        "passport": _normalize_passport(contact.get("UF_CRM_CONTACT_1686145698592", "")),
        "bitrix_contact_id": contact.get("ID"),
        "bitrix_company_id": contact.get("COMPANY_ID"),
        "bitrix_company_ids": _company_ids_from_contact(contact),
    }


def _company_state_data(company: dict) -> dict:
    return {
        "company_title": str(company.get("TITLE", "")).strip(),
        "company_inn": str(company.get("UF_CRM_COMPANY_1692911328252", "")).strip(),
        "company_ceo_title": str(company.get("UF_CRM_1709019814756", "")).strip(),
        "company_ceo_full_name": str(company.get("UF_CRM_1709019759168", "")).strip(),
        "company_country": _europolis_company_country_title(company.get(EUROPOLIS_COMPANY_COUNTRY_FIELD, "")),
        "company_phone": _extract_multifield(company.get("PHONE")),
        "company_email": _extract_multifield(company.get("EMAIL")),
        "bitrix_company_id": company.get("ID"),
    }


def _company_ids_from_contact(contact: dict) -> list[str]:
    raw_ids = contact.get("COMPANY_IDS")
    ids: list[str] = []
    if isinstance(raw_ids, list):
        for item in raw_ids:
            if isinstance(item, dict):
                value = item.get("VALUE") or item.get("ID") or item.get("id")
            else:
                value = item
            if str(value or "").strip():
                ids.append(str(value).strip())
    elif str(raw_ids or "").strip():
        ids.append(str(raw_ids).strip())

    fallback = str(contact.get("COMPANY_ID") or "").strip()
    if fallback and fallback not in ids:
        ids.append(fallback)
    return ids


def _company_by_id(companies: list[dict], company_id: str | int | None) -> dict | None:
    target = str(company_id or "").strip()
    for company in companies:
        if str(company.get("ID") or "").strip() == target:
            return company
    return None


def _company_ids_with_selected(data: dict, company_id: str | int | None) -> list[str]:
    ids: list[str] = []
    for item in data.get("bitrix_company_ids") or []:
        value = str(item or "").strip()
        if value and value not in ids:
            ids.append(value)
    selected = str(company_id or "").strip()
    if selected and selected not in ids:
        ids.append(selected)
    return ids


def _company_is_linked(data: dict, company_id: str | int | None) -> bool:
    target = str(company_id or "").strip()
    return bool(target and target in {str(item).strip() for item in data.get("bitrix_company_ids", [])})


def _personal_data_message(i18n: I18nService, lang: str, data: dict) -> str:
    return i18n.get_text(lang, "application.personal_data_summary").format(
        last_name=str(data.get("last_name", "")).strip() or "—",
        first_name=str(data.get("first_name", "")).strip() or "—",
        birth_date=str(data.get("birth_date", "")).strip() or "—",
        passport=str(data.get("passport", "")).strip() or "—",
        registration_address=str(data.get("registration_address", "")).strip() or "—",
        email=str(data.get("email", "")).strip() or "—",
        phone=str(data.get("phone", "")).strip() or "—",
    )


def _vehicle_data_message(i18n: I18nService, lang: str, data: dict) -> str:
    return i18n.get_text(lang, "application.vehicle_data_summary").format(
        vehicle_type=str(data.get("vehicle_type", "")).strip() or "—",
        license_plate=str(data.get("license_plate", "")).strip() or "—",
        vehicle_country=str(data.get("vehicle_country", "")).strip() or "—",
        manufacture_year=str(data.get("manufacture_year", "")).strip() or "—",
        vin=str(data.get("vin", "")).strip() or "—",
        fuel_type=str(data.get("fuel_type", "")).strip() or "—",
        engine_capacity=str(data.get("engine_capacity", "")).strip() or "—",
        engine_power=str(data.get("engine_power", "")).strip() or "—",
        power_unit=str(data.get("power_unit", "")).strip() or "—",
    )


def _current_vehicle(data: dict) -> dict:
    return {
        "insurance_period": data.get("insurance_period"),
        "insurance_start_date": data.get("insurance_start_date"),
        "vehicle_country": data.get("vehicle_country"),
        "vehicle_type": data.get("vehicle_type"),
        "license_plate": data.get("license_plate"),
        "vin": data.get("vin"),
        "brand_model": data.get("brand_model"),
        "manufacture_year": data.get("manufacture_year"),
        "fuel_type": data.get("fuel_type"),
        "engine_capacity": data.get("engine_capacity"),
        "engine_power": data.get("engine_power"),
        "power_unit": data.get("power_unit"),
        "comment": data.get("comment"),
        "vehicle_docs": data.get("vehicle_docs", []),
        "reuse_existing_vehicle_docs": bool(data.get("reuse_existing_vehicle_docs")),
    }


class ApplyForm(StatesGroup):
    email_lookup = State()
    passport_verify = State()
    personal_data_confirm = State()
    vehicle_data_confirm = State()
    first_name = State()
    last_name = State()
    phone = State()
    email = State()
    birth_date = State()
    passport = State()
    registration_address = State()
    policyholder_type = State()
    company_confirm = State()
    company_select = State()
    company_title = State()
    company_inn = State()
    company_country = State()
    company_email = State()
    company_phone = State()
    company_ceo_title = State()
    company_ceo_full_name = State()
    insurance_period = State()
    insurance_start_date = State()
    vehicle_country = State()
    vehicle_type = State()
    license_plate = State()
    vin = State()
    brand_model = State()
    manufacture_year = State()
    fuel_type = State()
    engine_capacity = State()
    engine_power = State()
    power_unit = State()
    comment = State()
    vehicle_docs = State()
    techpass_changed = State()
    vehicle_finalize = State()
    consent = State()




def _extract_multifield(value: object) -> str:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return str(first.get("VALUE", "")).strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _birthdate_to_ddmmyyyy(value: str) -> str:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%d.%m.%Y")
        except ValueError:
            continue
    return value





def _parse_common_date(value: str) -> date | None:
    raw = value.strip()
    for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%d.%m.%y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt).date()
            if fmt == "%d.%m.%y":
                # normalize 2-digit year to 1900/2000 by stdlib, keep as parsed
                pass
            return dt
        except ValueError:
            continue
    return None


def _to_ddmmyyyy(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _max_birth_date(today: date | None = None) -> date:
    today = today or date.today()
    try:
        return today.replace(year=today.year - 18)
    except ValueError:
        return today.replace(year=today.year - 18, day=28)


def _datetime_start(value: date) -> datetime:
    return datetime.combine(value, time.min)


def _localized_calendar_text(i18n: I18nService, lang: str, key: str, default: str) -> str:
    text = i18n.get_text(lang, key)
    return default if text == key else text


async def _calendar_locale(from_user, lang: str) -> str | None:
    try:
        return await get_user_locale(from_user)
    except (AttributeError, KeyError):
        return CALENDAR_LOCALES.get(lang)


def _dialog_calendar(locale: str | None, i18n: I18nService, lang: str) -> DialogCalendar:
    kwargs = {
        "cancel_btn": _localized_calendar_text(i18n, lang, "application.calendar.cancel", "Cancel"),
        "show_alerts": True,
    }
    try:
        return DialogCalendar(locale=locale, **kwargs)
    except (KeyError, ValueError, pylocale.Error):
        return DialogCalendar(**kwargs)


def _simple_calendar(locale: str | None, i18n: I18nService, lang: str) -> SimpleCalendar:
    kwargs = {
        "cancel_btn": _localized_calendar_text(i18n, lang, "application.calendar.cancel", "Cancel"),
        "today_btn": _localized_calendar_text(i18n, lang, "application.calendar.today", "Today"),
        "show_alerts": True,
    }
    try:
        return SimpleCalendar(locale=locale, **kwargs)
    except (KeyError, ValueError, pylocale.Error):
        return SimpleCalendar(**kwargs)


def _configure_birth_calendar(calendar: DialogCalendar) -> DialogCalendar:
    calendar.set_dates_range(_datetime_start(date(1900, 1, 1)), _datetime_start(_max_birth_date()))
    return calendar


def _configure_insurance_calendar(calendar: SimpleCalendar) -> SimpleCalendar:
    today = date.today()
    calendar.set_dates_range(
        _datetime_start(today),
        _datetime_start(today + timedelta(days=INSURANCE_START_MAX_DAYS)),
    )
    return calendar


async def _birth_calendar_markup(from_user, i18n: I18nService, lang: str):
    calendar = _configure_birth_calendar(
        _dialog_calendar(await _calendar_locale(from_user, lang), i18n, lang)
    )
    max_date = _max_birth_date()
    return await calendar.start_calendar(year=max_date.year)


async def _insurance_calendar_markup(from_user, i18n: I18nService, lang: str):
    calendar = _configure_insurance_calendar(
        _simple_calendar(await _calendar_locale(from_user, lang), i18n, lang)
    )
    today = date.today()
    return await calendar.start_calendar(year=today.year, month=today.month)


def _is_adult(value: date) -> bool:
    today = date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    return age >= 18


async def _save_birth_date_and_ask_passport(
    message: Message, state: FSMContext, i18n: I18nService, lang: str, value: date
) -> bool:
    if not _is_adult(value):
        await message.answer(i18n.get_text(lang, "application.validation_age_18"))
        return False
    data = await state.get_data()
    await state.update_data(birth_date=_to_ddmmyyyy(value))
    if _is_europolis_data(data):
        await state.set_state(ApplyForm.registration_address)
        address_prefill = str(data.get("registration_address", "")).strip()
        if address_prefill:
            await _send_prefilled_prompt(
                message,
                i18n,
                lang,
                "application.ask_registration_address_prefilled",
                address_prefill,
                "registration_address",
            )
        else:
            await message.answer(i18n.get_text(lang, "application.ask_registration_address"))
        return True

    await state.set_state(ApplyForm.passport)
    passport_prefill = str(data.get("passport", "")).strip()
    if passport_prefill:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_passport_prefilled", passport_prefill, "passport")
    else:
        await message.answer(i18n.get_text(lang, "application.ask_passport"))
    return True


async def _save_insurance_start_date_and_ask_period(
    message: Message, state: FSMContext, i18n: I18nService, lang: str, value: date
) -> bool:
    if value < date.today():
        await message.answer(i18n.get_text(lang, "application.validation_insurance_start_not_past"))
        return False
    data = await state.get_data()
    await state.update_data(insurance_start_date=_to_ddmmyyyy(value))
    if _is_europolis_data(data):
        await _ask_europolis_license_plate(message, state, i18n, lang)
    else:
        await state.set_state(ApplyForm.insurance_period)
        await message.answer(
            i18n.get_text(lang, "application.ask_insurance_period"),
            reply_markup=periods_keyboard(i18n, lang),
        )
    return True


def _vehicle_docs_summary(docs: object) -> str | None:
    if not docs:
        return None
    if isinstance(docs, list):
        names = [str(doc.get("name", "")).strip() for doc in docs if isinstance(doc, dict) and doc.get("name")]
        return ", ".join(names) or None
    return str(docs)


def _safe_doc_name(name: object, index: int, doc_type: str) -> str:
    raw = str(name or "").strip()
    if not raw or raw == "photo":
        raw = f"techpass_{index}.jpg" if doc_type == "photo" else f"techpass_{index}.bin"
    return Path(raw).name or f"techpass_{index}.bin"


async def _download_telegram_docs(bot, docs: object, target_dir: Path, vehicle_index: int) -> list[str]:
    if not isinstance(docs, list):
        return []

    paths: list[str] = []
    for index, doc in enumerate(docs, start=1):
        if not isinstance(doc, dict) or not doc.get("file_id"):
            continue
        telegram_file = await bot.get_file(doc["file_id"])
        filename = _safe_doc_name(doc.get("name"), index, str(doc.get("type", "")))
        local_path = target_dir / f"vehicle_{vehicle_index}_{index}_{filename}"
        with local_path.open("wb") as destination:
            await bot.download_file(telegram_file.file_path, destination=destination)
        paths.append(str(local_path))
    return paths


async def _attach_telegram_docs_to_deals(bot, bitrix_client, vehicles: list[dict], deal_ids: list[int]) -> None:
    with tempfile.TemporaryDirectory(prefix="telegram_vehicle_docs_") as tmpdir:
        tmp_path = Path(tmpdir)
        bitrix_file = BitrixFileService(bitrix_client)
        for vehicle_index, (vehicle, deal_id) in enumerate(zip(vehicles, deal_ids, strict=False), start=1):
            saved_paths = await _download_telegram_docs(bot, vehicle.get("vehicle_docs"), tmp_path, vehicle_index)
            if saved_paths:
                bitrix_file.upload_and_attach_files_to_deal(deal_id, saved_paths)


def _application_from_state(data: dict, lang: str) -> ApplicationCreate:
    vehicles = []
    for vehicle in data.get("vehicles", []):
        vehicles.append(
            {
                "vehicle_country_registration": str(vehicle.get("vehicle_country", "")).strip(),
                "vehicle_type": str(vehicle.get("vehicle_type", "")).strip(),
                "insurance_period_days": int(vehicle.get("insurance_period") or 0),
                "insurance_start_date": _parse_common_date(str(vehicle.get("insurance_start_date", ""))) or date.today(),
                "license_plate": str(vehicle.get("license_plate", "")).strip(),
                "vin": str(vehicle.get("vin", "")).strip() or None,
                "brand_model": str(vehicle.get("brand_model", "")).strip(),
                "manufacture_year": int(vehicle.get("manufacture_year") or 0),
                "engine_type": str(vehicle.get("fuel_type", "")).strip(),
                "engine_capacity_cc": int(vehicle.get("engine_capacity") or 0),
                "engine_power": float(vehicle.get("engine_power") or 0),
                "power_unit": str(vehicle.get("power_unit", "")).strip(),
                "vehicle_docs": _vehicle_docs_summary(vehicle.get("vehicle_docs")),
                "reuse_existing_vehicle_docs": bool(vehicle.get("reuse_existing_vehicle_docs")),
            }
        )

    return ApplicationCreate(
        first_name=str(data.get("first_name", "")).strip(),
        last_name=str(data.get("last_name", "")).strip(),
        phone=str(data.get("phone", "")).strip(),
        email=str(data.get("email", "")).strip(),
        preferred_language=lang,
        policyholder_type="individual",
        birth_date=_parse_common_date(str(data.get("birth_date", ""))) or date.today(),
        registration_address=str(data.get("registration_address", "")).strip(),
        passport_series_number=str(data.get("passport", "")).strip(),
        vehicles=vehicles,
        terms_accepted=True,
        privacy_accepted=True,
        telegram_init_data="telegram_bot_apply_flow",
    )



def _europolis_deal_defaults() -> dict[str, str]:
    return {
        "UF_CRM_1686682902533": "4287",
        "UF_CRM_1693578066803": "4335",
        "UF_CRM_1686683031442": "941",
    }


def _europolis_vehicle_deal_payload(
    data: dict, vehicle: dict, contact_id: int, company_id: int | None, telegram_user_id: int | None
) -> dict:
    lead_service = LeadService(
        None, app_root() / "config" / "bitrix_mapping.yaml"  # type: ignore[arg-type]
    )
    comment_parts = [str(vehicle.get("comment", "")).strip()]
    comment_parts.extend(
        [
            f"Company: {data.get('company_title') or '—'}",
            f"Company tax ID: {data.get('company_inn') or '—'}",
            f"Source bot: europolis_client_bot",
            f"Verification status: {data.get('company_verification_status') or '—'}",
            f"Requires company relation check: {'yes' if data.get('requires_company_relation_check') else 'no'}",
        ]
    )
    payload = {
        "TITLE": f"EuroPolis {data.get('last_name', '')} {data.get('first_name', '')} {vehicle.get('license_plate', '')}".strip(),
        "CONTACT_ID": contact_id,
        "COMPANY_ID": company_id,
        "COMMENTS": "\n".join(part for part in comment_parts if part),
        "UF_CRM_1686152306664": vehicle.get("vehicle_country"),
        "UF_CRM_1686152567597": vehicle.get("vehicle_type"),
        "UF_CRM_1686152209741": int(vehicle.get("insurance_period") or 0),
        "UF_CRM_1686152149204": _parse_common_date(str(vehicle.get("insurance_start_date", ""))) or date.today(),
        "UF_CRM_1686152485641": str(vehicle.get("license_plate", "")).strip(),
        TELEGRAM_CHAT_ID_FIELD: telegram_user_id,
        SHOW_IN_TELEGRAM_FIELD: "1",
        PRODUCT_TYPE_FIELD: "EuroPolis",
        **_europolis_deal_defaults(),
    }
    return {
        key: lead_service._normalize_deal_field(key, value)
        for key, value in payload.items()
        if value not in (None, "")
    }


def _europolis_company_payload(data: dict) -> dict:
    inn = str(data.get("company_inn", "")).strip()
    title = str(data.get("company_title", "")).strip() or (f"Company {inn}" if inn else "Company")
    payload = {
        "TITLE": title,
        "UF_CRM_COMPANY_1692911328252": inn,
        EUROPOLIS_COMPANY_COUNTRY_FIELD: _europolis_company_country_id(data.get("company_country")),
        "UF_CRM_1709019814756": str(data.get("company_ceo_title", "")).strip(),
        "UF_CRM_1709019759168": str(data.get("company_ceo_full_name", "")).strip(),
    }
    company_phone = str(data.get("company_phone", "")).strip()
    company_email = str(data.get("company_email", "")).strip()
    if company_phone:
        payload["PHONE"] = [{"VALUE": company_phone, "VALUE_TYPE": "WORK"}]
    if company_email:
        payload["EMAIL"] = [{"VALUE": company_email, "VALUE_TYPE": "WORK"}]
    return payload


def _create_europolis_bitrix_application(
    data: dict,
    lang: str,
    bitrix_client,
    telegram_username: str | None,
    telegram_user_id: int | None,
) -> dict:
    lead_service = LeadService(bitrix_client, app_root() / "config" / "bitrix_mapping.yaml")

    company_id = data.get("bitrix_company_id")
    company_created_for_contact = False
    if data.get("policyholder_type") == "company" and not company_id:
        company_id = bitrix_client.create_or_update_company(_europolis_company_payload(data))
        company_created_for_contact = True

    contact_payload = {
        "NAME": str(data.get("first_name", "")).strip(),
        "LAST_NAME": str(data.get("last_name", "")).strip(),
        "PHONE_WORK": str(data.get("phone", "")).strip(),
        "EMAIL_WORK": str(data.get("email", "")).strip(),
        "UF_CRM_1753957395750": lead_service._bitrix_language_id(lang),
        TELEGRAM_USERNAME_FIELD: telegram_username,
        TELEGRAM_USER_ID_FIELD: telegram_user_id,
        TELEGRAM_CHAT_ID_FIELD: telegram_user_id,
    }
    if data.get("policyholder_type") == "individual":
        contact_payload.update(
            {
                "BIRTHDATE": _parse_common_date(str(data.get("birth_date", ""))) or date.today(),
                "ADDRESS": str(data.get("registration_address", "")).strip(),
            }
        )
    contact_company_ids = _company_ids_with_selected(data, company_id)
    if company_id and not data.get("requires_company_relation_check"):
        contact_payload["COMPANY_IDS"] = contact_company_ids

    contact_id = bitrix_client.create_or_update_contact(contact_payload)
    if company_created_for_contact and hasattr(bitrix_client, "link_contact_to_companies"):
        bitrix_client.link_contact_to_companies(contact_id, contact_company_ids)

    deals: list[int] = []
    for vehicle in data.get("vehicles", []):
        deals.append(
            bitrix_client.create_deal(
                _europolis_vehicle_deal_payload(
                    data, vehicle, contact_id, company_id, telegram_user_id
                )
            )
        )
    return {"success": True, "contact_id": contact_id, "company_id": company_id, "deals": deals}

def _create_bitrix_application(
    data: dict,
    lang: str,
    bitrix_client,
    telegram_username: str | None,
    telegram_user_id: int | None,

) -> dict:
    if data.get("client_bot") == "europolis":
        return _create_europolis_bitrix_application(
            data, lang, bitrix_client, telegram_username, telegram_user_id
        )

    payload = _application_from_state(data, lang)
    return LeadService(bitrix_client, app_root() / "config" / "bitrix_mapping.yaml").create_application_leads(
        payload, telegram_username, telegram_user_id

    )



@router.message(F.text == "/apply")
async def apply_command(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
    user=None,
) -> None:
    user = user or message.from_user
    if not user:
        return

    lang = lang_store.get(user.id, default_language)
    await state.clear()
    client_bot = getattr(message.bot, "client_bot_code", "default")
    await state.update_data(vehicles=[], current_vehicle={}, client_bot=client_bot)
    from app.services.reminder_service import ReminderService

    try:
        reminder_service = ReminderService()
        reminder_service.mark_calculator_converted(user.id)
        draft = reminder_service.create_application_draft(
            telegram_user_id=user.id,
            telegram_chat_id=message.chat.id,
            product_type="border_insurance",
            source_channel="telegram_bot",
            current_step="started",
            safe_context={"language": lang},
            language=lang,
        )
        await state.update_data(application_draft_id=draft.draft_id)
    except Exception as exc:
        logger.exception(
            "application_draft_reminder_failed user_id=%s error=%s", user.id, exc
        )
    await message.answer(i18n.get_text(lang, "application.form_header"))

    contact = None
    username = (user.username or "").strip()
    try:
        if hasattr(message.bot, "bitrix_client"):
            if _is_europolis_bot(message.bot) and hasattr(
                message.bot.bitrix_client, "find_europolis_contact_by_telegram_identity"
            ):
                contact = (
                    message.bot.bitrix_client.find_europolis_contact_by_telegram_identity(
                        username=username or None, user_id=user.id
                    )
                )
            elif username:
                contact = message.bot.bitrix_client.find_contact_by_telegram_username(username)

        if _is_europolis_bot(message.bot):
            if contact:
                contact_data = _contact_state_data(contact)
                await state.update_data(**contact_data)
                company_id = contact_data.get("bitrix_company_id")
                if company_id and hasattr(
                    message.bot.bitrix_client, "get_europolis_company_prefill"
                ):
                    company = message.bot.bitrix_client.get_europolis_company_prefill(
                        company_id
                    )
                    if company:
                        await state.update_data(**_company_state_data(company))
            await _ask_first_name_for_edit(message, state, i18n, lang)
            return
    except RuntimeError as exc:
        logger.exception(
            "application_bitrix_prefill_failed user_id=%s client_bot=%s error=%s",
            user.id,
            client_bot,
            exc,
        )
        if _is_europolis_bot(message.bot):
            await _ask_first_name_for_edit(message, state, i18n, lang)
            return


    if contact:
        await state.update_data(**_contact_state_data(contact))
        await state.set_state(ApplyForm.personal_data_confirm)
        data = await state.get_data()
        await message.answer(
            _personal_data_message(i18n, lang, data),
            reply_markup=data_actual_keyboard(
                i18n.get_text(lang, "application.data_actual"),
                i18n.get_text(lang, "application.data_edit"),
                "personal",
            ),
        )
        return

    await state.set_state(ApplyForm.email_lookup)
    await message.answer(i18n.get_text(lang, "application.ask_email_lookup"))





async def _send_prefilled_prompt(message: Message, i18n: I18nService, lang: str, text_key: str, value: str, field_key: str) -> None:
    await message.answer(
        i18n.get_text(lang, text_key).format(value=value),
        reply_markup=prefill_next_keyboard(i18n.get_text(lang, "application.prefill_next_button"), field_key),
    )


async def send_apply(message: Message, state: FSMContext, user=None) -> None:
    await apply_command(
        message,
        state,
        message.bot.i18n,
        message.bot.lang_store,
        message.bot.default_language,
        user=user,
    )



@router.message(
    StateFilter(ApplyForm), F.text.regexp(r"^(?:/|🧮|❓|🌍|📝|📄|💳|👨‍💼|🌐)")
)
async def menu_shortcut_during_apply(message: Message, state: FSMContext) -> None:
    lang = message.bot.lang_store.get(
        message.from_user.id, message.bot.default_language
    )
    action = menu_action_for_text(
        message.bot.i18n, message.text, lang, message.bot.default_language
    )
    if not action:
        return
    if action != "apply":
        await state.clear()

    from app.bots.client_bot.handlers.menu import menu_click_router

    await menu_click_router(message, state)




async def _load_europolis_companies(message: Message, state: FSMContext) -> list[dict]:
    data = await state.get_data()
    company_ids = data.get("bitrix_company_ids", [])
    bitrix_client = getattr(message.bot, "bitrix_client", None)
    if not company_ids or bitrix_client is None or not hasattr(bitrix_client, "list_europolis_companies"):
        await state.update_data(linked_companies=[])
        return []
    companies = bitrix_client.list_europolis_companies(company_ids)
    await state.update_data(linked_companies=companies)
    return companies


async def _ensure_europolis_contact_from_state(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("bitrix_contact_id"):
        return
    bitrix_client = getattr(message.bot, "bitrix_client", None)
    if bitrix_client is None or not hasattr(bitrix_client, "find_europolis_contact"):
        return
    contact = bitrix_client.find_europolis_contact(
        username=getattr(message.from_user, "username", None),
        user_id=getattr(message.from_user, "id", None),
        email=data.get("email"),
        phone=data.get("phone"),
    )
    if contact:
        await state.update_data(**_contact_state_data(contact))


async def _ask_or_select_company(
    message: Message, state: FSMContext, i18n: I18nService, lang: str
) -> None:
    companies = await _load_europolis_companies(message, state)
    if len(companies) == 1:
        company = companies[0]
        await state.update_data(candidate_company_id=company.get("ID"))
        await state.set_state(ApplyForm.company_confirm)
        await message.answer(
            _text_or_default(
                i18n,
                lang,
                "application.confirm_company",
                "Оформляем заявку для компании: {company_title}?",
            ).format(company_title=company.get("TITLE") or f"ID {company.get('ID')}"),
            reply_markup=company_confirm_keyboard(
                _text_or_default(i18n, lang, "application.company_confirm_yes", "Да, продолжить"),
                _text_or_default(i18n, lang, "application.company_choose_other", "Выбрать другую компанию"),
            ),
        )
        return
    if len(companies) > 1:
        await state.set_state(ApplyForm.company_select)
        await message.answer(
            _text_or_default(
                i18n, lang, "application.choose_company", "Выберите компанию для оформления заявки"
            ),
            reply_markup=company_select_keyboard(companies),
        )
        return
    await _ask_company_title(message, state, i18n, lang)


async def _select_europolis_company(
    message: Message, state: FSMContext, i18n: I18nService, lang: str, company: dict
) -> None:
    await state.update_data(
        **_company_state_data(company),
        company_verification_status="known_contact_known_company",
        requires_company_relation_check=False,
    )
    await _ask_vehicle_country_start(message, state, i18n, lang)


async def _ask_company_title(message: Message, state: FSMContext, i18n: I18nService, lang: str) -> None:
    await state.set_state(ApplyForm.company_title)
    await message.answer(
        _text_or_default(
            i18n, lang, "application.ask_company_title", "Название компании *"
        )
    )


def _operator_unlinked_company_notice(data: dict, company: dict, telegram_user) -> str:
    username = f"@{telegram_user.username}" if telegram_user and telegram_user.username else "—"
    return (
        "⚠️ Внимание: пользователь оформляет заявку от имени компании, "
        "которая уже есть в Bitrix, но контакт не связан с этой компанией.\n\n"
        f"Пользователь:\n"
        f"Telegram ID: {telegram_user.id if telegram_user else '—'}\n"
        f"Username: {username}\n"
        f"Имя: {data.get('first_name') or '—'} {data.get('last_name') or '—'}\n"
        f"Email: {data.get('email') or '—'}\n"
        f"Телефон: {data.get('phone') or '—'}\n\n"
        f"Компания:\n"
        f"Название: {company.get('TITLE') or data.get('company_title') or '—'}\n"
        f"ИНН: {company.get('UF_CRM_COMPANY_1692911328252') or data.get('company_inn') or '—'}\n"
        f"Bitrix Company ID: {company.get('ID') or '—'}\n\n"
        "Необходимо проверить, является ли пользователь сотрудником / представителем этой компании.\n\n"
        f"Если связь подтверждена, добавьте в карточке контакта Bitrix связь с компанией ID={company.get('ID')} "
        "в поле COMPANY_IDS."
    )

async def _ask_policyholder_type(message: Message, state: FSMContext, i18n: I18nService, lang: str) -> None:
    await state.set_state(ApplyForm.policyholder_type)
    await message.answer(
        _text_or_default(
            i18n,
            lang,
            "application.ask_policyholder_type",
            "Заявку делаем на физическое лицо или юридическое лицо?",
        ),
        reply_markup=policyholder_type_keyboard(
            _text_or_default(i18n, lang, "application.policyholder_individual", "Физическое лицо"),
            _text_or_default(i18n, lang, "application.policyholder_company", "Юридическое лицо"),
        ),
    )


async def _ask_company_inn(message: Message, state: FSMContext, i18n: I18nService, lang: str) -> None:
    await state.set_state(ApplyForm.company_inn)
    await message.answer(
        _text_or_default(
            i18n,
            lang,
            "application.company_data_header",
            "Данные страхователя (юридическое лицо)",
        )
    )
    data = await state.get_data()
    company_inn_prefill = str(data.get("company_inn", "")).strip()
    if company_inn_prefill:
        await _send_prefilled_prompt(
            message,
            i18n,
            lang,
            "application.ask_company_inn_prefilled",
            company_inn_prefill,
            "company_inn",
        )
    else:
        await message.answer(_text_or_default(i18n, lang, "application.ask_company_inn", "ИНН компании *"))


async def _ask_vehicle_country_start(message: Message, state: FSMContext, i18n: I18nService, lang: str) -> None:
    await state.update_data(
        vehicle_country="",
        vehicle_type="",
        insurance_period=None,
        insurance_start_date=None,
        license_plate="",
        comment="",
        vehicle_docs_prefilled=False,
        reuse_existing_vehicle_docs=False,
        vehicle_docs=[],
    )
    await state.set_state(ApplyForm.vehicle_country)
    await message.answer(i18n.get_text(lang, "application.step_2"))
    await message.answer(i18n.get_text(lang, "application.ask_vehicle_country"))
    await message.answer(
        i18n.get_text(lang, "application.choose_from_buttons"),
        reply_markup=countries_keyboard(i18n, lang),
    )


async def _ask_europolis_license_plate(
    message: Message, state: FSMContext, i18n: I18nService, lang: str
) -> None:
    await state.set_state(ApplyForm.license_plate)
    await message.answer(i18n.get_text(lang, "application.ask_license_plate"))

async def _ask_first_name_for_edit(message: Message, state: FSMContext, i18n: I18nService, lang: str) -> None:
    await state.set_state(ApplyForm.first_name)
    await message.answer(i18n.get_text(lang, "application.step_1"))
    data = await state.get_data()
    first_name_prefill = str(data.get("first_name", "")).strip()
    if first_name_prefill:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_first_name_prefilled", first_name_prefill, "first_name")
    else:
        await message.answer(i18n.get_text(lang, "application.ask_first_name"))


async def _ask_license_plate(message: Message, state: FSMContext, i18n: I18nService, lang: str) -> None:
    await state.set_state(ApplyForm.license_plate)
    await message.answer(i18n.get_text(lang, "application.step_2"))
    await message.answer(i18n.get_text(lang, "application.ask_license_plate"))


async def _ask_techpass_or_docs(message: Message, state: FSMContext, i18n: I18nService, lang: str) -> None:
    data = await state.get_data()
    if data.get("vehicle_docs_prefilled"):
        await state.set_state(ApplyForm.techpass_changed)
        await message.answer(
            i18n.get_text(lang, "application.ask_techpass_changed"),
            reply_markup=techpass_changed_keyboard(
                i18n.get_text(lang, "application.techpass_changed_yes"),
                i18n.get_text(lang, "application.techpass_changed_no"),
            ),
        )
    else:
        await state.set_state(ApplyForm.vehicle_docs)
        await message.answer(i18n.get_text(lang, "application.ask_vehicle_docs"))


async def _ask_birth_date(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
    prefill: str = "",
    calendar_user=None,
) -> None:
    await state.set_state(ApplyForm.birth_date)
    if prefill:
        await _send_prefilled_prompt(
            message, i18n, lang, "application.ask_birth_date_prefilled", prefill, "birth_date"
        )
    await message.answer(
        i18n.get_text(lang, "application.ask_birth_date"),
        reply_markup=await _birth_calendar_markup(calendar_user or message.from_user, i18n, lang),
    )


async def _ask_insurance_start_date(
    message: Message, state: FSMContext, i18n: I18nService, lang: str, calendar_user=None
) -> None:
    await state.set_state(ApplyForm.insurance_start_date)
    await message.answer(
        i18n.get_text(lang, "application.ask_insurance_start_date"),
        reply_markup=await _insurance_calendar_markup(calendar_user or message.from_user, i18n, lang),
    )


async def _finish_vehicle_and_ask_next(message: Message, state: FSMContext, i18n: I18nService, lang: str) -> None:
    data = await state.get_data()
    vehicles = data.get("vehicles", [])
    vehicles.append(_current_vehicle(data))
    await state.update_data(vehicles=vehicles)
    await state.set_state(ApplyForm.vehicle_finalize)
    await message.answer(
        i18n.get_text(lang, "application.ask_vehicle_finalize"),
        reply_markup=finalize_vehicle_keyboard(i18n.get_text(lang, "application.add_vehicle"), i18n.get_text(lang, "application.finish_application")),
    )


@router.message(ApplyForm.email_lookup)
async def email_lookup(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    if not EMAIL_RE.match(value):
        await message.answer(i18n.get_text(lang, "application.validation_email"))
        return

    await state.update_data(email=value)
    contact = None
    if hasattr(message.bot, "bitrix_client"):
        contact = message.bot.bitrix_client.find_contact_by_email(value)

    if not contact:
        await message.answer(i18n.get_text(lang, "application.contact_not_found_manual"))
        await _ask_first_name_for_edit(message, state, i18n, lang)
        return

    await state.update_data(pending_contact=_contact_state_data(contact))
    await state.set_state(ApplyForm.passport_verify)
    await message.answer(i18n.get_text(lang, "application.ask_passport_verify"))


@router.message(ApplyForm.passport_verify)
async def passport_verify(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = _normalize_passport(message.text)
    data = await state.get_data()
    pending_contact = data.get("pending_contact") or {}
    if not is_passport_number(value):
        await message.answer(i18n.get_text(lang, "application.validation_passport"))
        return
    if value != _normalize_passport(pending_contact.get("passport")):
        await message.answer(i18n.get_text(lang, "application.passport_verify_failed_manual"))
        await state.update_data(pending_contact=None, passport=value)
        await _ask_first_name_for_edit(message, state, i18n, lang)
        return

    await state.update_data(**pending_contact, pending_contact=None)
    await state.set_state(ApplyForm.personal_data_confirm)
    data = await state.get_data()
    await message.answer(
        _personal_data_message(i18n, lang, data),
        reply_markup=data_actual_keyboard(
            i18n.get_text(lang, "application.data_actual"),
            i18n.get_text(lang, "application.data_edit"),
            "personal",
        ),
    )



@router.callback_query(F.data.startswith("apply:policyholder:"), ApplyForm.policyholder_type)
async def policyholder_type(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    value = callback.data.split(":", 2)[-1]
    if value == "company":
        await state.update_data(policyholder_type="company")
        await _ask_or_select_company(callback.message, state, i18n, lang)
    else:
        await state.update_data(policyholder_type="individual")
        await callback.message.answer(
            _text_or_default(
                i18n,
                lang,
                "application.individual_data_header",
                "Данные страхователя (физическое лицо)",
            )
        )
        data = await state.get_data()
        await _ask_birth_date(
            callback.message,
            state,
            i18n,
            lang,
            str(data.get("birth_date", "")).strip(),
            callback.from_user,
        )
    await callback.answer()



@router.callback_query(F.data == "apply:company:confirm", ApplyForm.company_confirm)
async def company_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    data = await state.get_data()
    company = _company_by_id(data.get("linked_companies", []), data.get("candidate_company_id"))
    if company:
        await _select_europolis_company(callback.message, state, i18n, lang, company)
    else:
        await _ask_company_title(callback.message, state, i18n, lang)
    await callback.answer()


@router.callback_query(F.data == "apply:company:choose_other", StateFilter(ApplyForm.company_confirm, ApplyForm.company_select))
async def company_choose_other(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    await _ask_company_title(callback.message, state, i18n, lang)
    await callback.answer()


@router.callback_query(F.data.startswith("apply:company:select:"), ApplyForm.company_select)
async def company_select(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    company_id = callback.data.rsplit(":", maxsplit=1)[-1]
    data = await state.get_data()
    company = _company_by_id(data.get("linked_companies", []), company_id)
    if company:
        await _select_europolis_company(callback.message, state, i18n, lang, company)
    else:
        await callback.message.answer(
            _text_or_default(i18n, lang, "application.company_not_found", "Компания не найдена.")
        )
        await _ask_company_title(callback.message, state, i18n, lang)
    await callback.answer()


@router.message(ApplyForm.company_title)
async def company_title(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    if len(value) < 2:
        await message.answer(
            _text_or_default(i18n, lang, "application.validation_company_title", "Укажите название компании.")
        )
        return
    await state.update_data(company_title=value)
    await _ask_company_inn(message, state, i18n, lang)

@router.message(ApplyForm.company_inn)
async def company_inn(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    if len(value) < 3:
        await message.answer(
            _text_or_default(i18n, lang, "application.validation_company_inn", "Укажите ИНН компании.")
        )
        return
    data = await state.get_data()
    bitrix_client = getattr(message.bot, "bitrix_client", None)
    company = None
    if bitrix_client is not None and hasattr(bitrix_client, "find_europolis_company_by_tax_id"):
        company = bitrix_client.find_europolis_company_by_tax_id(value)

    update = {"company_inn": value}
    if company:
        update.update(_company_state_data(company))
        if _company_is_linked(data, company.get("ID")):
            update.update(
                company_verification_status="known_contact_known_company",
                requires_company_relation_check=False,
            )
        else:
            update.update(
                company_verification_status=(
                    "known_contact_unlinked_existing_company"
                    if data.get("bitrix_contact_id")
                    else "new_contact_existing_company_unverified"
                ),
                requires_company_relation_check=True,
            )
            OperatorNotifierService().notify_new_ticket(
                _operator_unlinked_company_notice({**data, **update}, company, message.from_user)
            )
    else:
        update.update(
            company_verification_status="new_contact_new_company",
            requires_company_relation_check=False,
        )
    await state.update_data(**update)
    await state.set_state(ApplyForm.company_country)
    await message.answer(
        _text_or_default(i18n, lang, "application.ask_company_country", "Страна регистрации компании *")
    )



@router.message(ApplyForm.company_country)
async def company_country(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    if len(value) < 2:
        await message.answer(
            _text_or_default(i18n, lang, "application.validation_company_country", "Укажите страну регистрации компании.")
        )
        return
    await state.update_data(company_country=value)
    await state.set_state(ApplyForm.company_email)
    await message.answer(_text_or_default(i18n, lang, "application.ask_company_email", "E-mail компании *"))


@router.message(ApplyForm.company_email)
async def company_email(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    if not EMAIL_RE.match(value):
        await message.answer(i18n.get_text(lang, "application.validation_email"))
        return
    await state.update_data(company_email=value)
    await state.set_state(ApplyForm.company_phone)
    await message.answer(
        _text_or_default(i18n, lang, "application.ask_company_phone", "Телефон компании (с кодом страны) *")
    )


@router.message(ApplyForm.company_phone)
async def company_phone(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    if not PHONE_RE.match(value):
        await message.answer(i18n.get_text(lang, "application.validation_phone"))
        return
    await state.update_data(company_phone=value)
    await state.set_state(ApplyForm.company_ceo_title)
    await message.answer(
        _text_or_default(i18n, lang, "application.ask_company_ceo_title", "Должность руководителя *")
    )

@router.message(ApplyForm.company_ceo_title)
async def company_ceo_title(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    if len(value) < 2:
        await message.answer(
            _text_or_default(
                i18n, lang, "application.validation_company_ceo_title", "Укажите должность руководителя."
            )
        )
        return
    await state.update_data(company_ceo_title=value)
    await state.set_state(ApplyForm.company_ceo_full_name)
    await message.answer(
        _text_or_default(i18n, lang, "application.ask_company_ceo_full_name", "ФИО руководителя *")
    )


@router.message(ApplyForm.company_ceo_full_name)
async def company_ceo_full_name(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    if len(value) < 3:
        await message.answer(
            _text_or_default(
                i18n, lang, "application.validation_company_ceo_full_name", "Укажите ФИО руководителя."
            )
        )
        return
    await state.update_data(company_ceo_full_name=value)
    await _ask_vehicle_country_start(message, state, i18n, lang)

@router.callback_query(F.data == "apply:personal:actual", ApplyForm.personal_data_confirm)
async def personal_data_actual(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    data = await state.get_data()
    if _is_europolis_data(data):
        await _ask_vehicle_country_start(callback.message, state, i18n, lang)
    else:
        await _ask_license_plate(callback.message, state, i18n, lang)
    await callback.answer()


@router.callback_query(F.data == "apply:personal:edit", ApplyForm.personal_data_confirm)
async def personal_data_edit(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    await _ask_first_name_for_edit(callback.message, state, i18n, lang)
    await callback.answer()


@router.callback_query(F.data == "apply:vehicle:actual", ApplyForm.vehicle_data_confirm)
async def vehicle_data_actual(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    await _ask_techpass_or_docs(callback.message, state, i18n, lang)
    await callback.answer()


@router.callback_query(F.data == "apply:vehicle:edit", ApplyForm.vehicle_data_confirm)
async def vehicle_data_edit(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    await state.set_state(ApplyForm.vehicle_country)
    data = await state.get_data()
    country_prefill = str(data.get("vehicle_country", "")).strip()
    if country_prefill:
        await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_vehicle_country_prefilled", country_prefill, "vehicle_country")
    await callback.message.answer(i18n.get_text(lang, "application.choose_from_buttons"), reply_markup=countries_keyboard(i18n, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("apply:prefill-next:"))
async def prefill_next(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    field = callback.data.split(":", 2)[-1]
    data = await state.get_data()

    if field == "first_name":
        await state.update_data(first_name=str(data.get("first_name", "")).strip())
        await state.set_state(ApplyForm.last_name)
        value = str(data.get("last_name", "")).strip()
        if value:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_last_name_prefilled", value, "last_name")
        else:
            await callback.message.answer(i18n.get_text(lang, "application.ask_last_name"))
    elif field == "last_name":
        await state.update_data(last_name=str(data.get("last_name", "")).strip())
        await state.set_state(ApplyForm.phone)
        value = str(data.get("phone", "")).strip()
        if value:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_phone_prefilled", value, "phone")
        else:
            await callback.message.answer(i18n.get_text(lang, "application.ask_phone"))
    elif field == "phone":
        await state.update_data(phone=str(data.get("phone", "")).strip())
        await state.set_state(ApplyForm.email)
        value = str(data.get("email", "")).strip()
        if value:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_email_prefilled", value, "email")
        else:
            await callback.message.answer(i18n.get_text(lang, "application.ask_email"))
    elif field == "email":
        await state.update_data(email=str(data.get("email", "")).strip())
        if _is_europolis_data(data):
            await _ask_policyholder_type(callback.message, state, i18n, lang)
        else:
            value = str(data.get("birth_date", "")).strip()
            await _ask_birth_date(callback.message, state, i18n, lang, value, callback.from_user)
    elif field == "birth_date":
        await state.update_data(birth_date=str(data.get("birth_date", "")).strip())
        if _is_europolis_data(data):
            await state.set_state(ApplyForm.registration_address)
            value = str(data.get("registration_address", "")).strip()
            if value:
                await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_registration_address_prefilled", value, "registration_address")
            else:
                await callback.message.answer(i18n.get_text(lang, "application.ask_registration_address"))
        else:
            await state.set_state(ApplyForm.passport)
            value = str(data.get("passport", "")).strip()
            if value:
                await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_passport_prefilled", value, "passport")
            else:
                await callback.message.answer(i18n.get_text(lang, "application.ask_passport"))
    elif field == "passport":
        await state.update_data(passport=str(data.get("passport", "")).strip())
        await state.set_state(ApplyForm.registration_address)
        value = str(data.get("registration_address", "")).strip()
        if value:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_registration_address_prefilled", value, "registration_address")
        else:
            await callback.message.answer(i18n.get_text(lang, "application.ask_registration_address"))
    elif field == "registration_address":
        await state.update_data(registration_address=str(data.get("registration_address", "")).strip())
        if _is_europolis_data(data):
            await _ask_vehicle_country_start(callback.message, state, i18n, lang)
        else:
            await _ask_license_plate(callback.message, state, i18n, lang)
    elif field == "company_inn":
        await state.update_data(company_inn=str(data.get("company_inn", "")).strip())
        await state.set_state(ApplyForm.company_ceo_title)
        value = str(data.get("company_ceo_title", "")).strip()
        if value:
            await _send_prefilled_prompt(
                callback.message,
                i18n,
                lang,
                "application.ask_company_ceo_title_prefilled",
                value,
                "company_ceo_title",
            )
        else:
            await callback.message.answer(
                _text_or_default(i18n, lang, "application.ask_company_ceo_title", "Должность руководителя *")
            )
    elif field == "company_ceo_title":
        await state.update_data(company_ceo_title=str(data.get("company_ceo_title", "")).strip())
        await state.set_state(ApplyForm.company_ceo_full_name)
        value = str(data.get("company_ceo_full_name", "")).strip()
        if value:
            await _send_prefilled_prompt(
                callback.message,
                i18n,
                lang,
                "application.ask_company_ceo_full_name_prefilled",
                value,
                "company_ceo_full_name",
            )
        else:
            await callback.message.answer(
                _text_or_default(i18n, lang, "application.ask_company_ceo_full_name", "ФИО руководителя *")
            )
    elif field == "company_ceo_full_name":
        await state.update_data(company_ceo_full_name=str(data.get("company_ceo_full_name", "")).strip())
        await _ask_vehicle_country_start(callback.message, state, i18n, lang)
    elif field == "vehicle_country":
        await state.update_data(vehicle_country=str(data.get("vehicle_country", "")).strip())
        await state.set_state(ApplyForm.vehicle_type)
        value = str(data.get("vehicle_type", "")).strip()
        if value:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_vehicle_type_prefilled", value, "vehicle_type")
        await callback.message.answer(i18n.get_text(lang, "application.choose_from_buttons"), reply_markup=vehicle_types_keyboard(i18n, lang))
    elif field == "vehicle_type":
        await state.update_data(vehicle_type=str(data.get("vehicle_type", "")).strip())
        if _is_europolis_data(data):
            await state.set_state(ApplyForm.insurance_period)
            await callback.message.answer(
                i18n.get_text(lang, "application.ask_insurance_period"),
                reply_markup=periods_keyboard(i18n, lang),
            )
        else:
            await state.set_state(ApplyForm.vin)
            value = str(data.get("vin", "")).strip().upper()
            if value:
                await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_vin_prefilled", value, "vin")
            else:
                await callback.message.answer(i18n.get_text(lang, "application.ask_vin"))
    elif field == "vin":
        await state.update_data(vin=str(data.get("vin", "")).strip().upper())
        await state.set_state(ApplyForm.brand_model)
        value = str(data.get("brand_model", "")).strip()
        if value:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_brand_model_prefilled", value, "brand_model")
        else:
            await callback.message.answer(i18n.get_text(lang, "application.ask_brand_model"))
    elif field == "brand_model":
        await state.update_data(brand_model=str(data.get("brand_model", "")).strip())
        await state.set_state(ApplyForm.manufacture_year)
        value = str(data.get("manufacture_year", "")).strip()
        if value:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_manufacture_year_prefilled", value, "manufacture_year")
        else:
            await callback.message.answer(i18n.get_text(lang, "application.ask_manufacture_year"))
    elif field == "manufacture_year":
        await state.update_data(manufacture_year=str(data.get("manufacture_year", "")).strip())
        await state.set_state(ApplyForm.fuel_type)
        value = str(data.get("fuel_type", "")).strip()
        if value in FUEL_TYPES:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_fuel_type_prefilled", value, "fuel_type")
        await callback.message.answer(i18n.get_text(lang, "application.ask_fuel_type"), reply_markup=fuel_types_keyboard(i18n, lang))
    elif field == "fuel_type":
        value = str(data.get("fuel_type", "")).strip()
        await state.update_data(fuel_type=value)
        if value.lower() == "электро":
            await state.update_data(engine_capacity=0)
            await state.set_state(ApplyForm.engine_power)
            power = str(data.get("engine_power", "")).strip()
            if power:
                await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_engine_power_prefilled", power, "engine_power")
            else:
                await callback.message.answer(i18n.get_text(lang, "application.ask_engine_power"))
        else:
            await state.set_state(ApplyForm.engine_capacity)
            capacity = str(data.get("engine_capacity", "")).strip()
            if capacity:
                await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_engine_capacity_prefilled", capacity, "engine_capacity")
            else:
                await callback.message.answer(i18n.get_text(lang, "application.ask_engine_capacity"))
    elif field == "engine_capacity":
        await state.update_data(engine_capacity=str(data.get("engine_capacity", "")).strip())
        await state.set_state(ApplyForm.engine_power)
        value = str(data.get("engine_power", "")).strip()
        if value:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_engine_power_prefilled", value, "engine_power")
        else:
            await callback.message.answer(i18n.get_text(lang, "application.ask_engine_power"))
    elif field == "engine_power":
        await state.update_data(engine_power=str(data.get("engine_power", "")).strip())
        await state.set_state(ApplyForm.power_unit)
        value = str(data.get("power_unit", "")).strip()
        if value in POWER_UNITS:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_power_unit_prefilled", value, "power_unit")
        await callback.message.answer(i18n.get_text(lang, "application.ask_power_unit"), reply_markup=power_units_keyboard(i18n, lang))
    elif field == "power_unit":
        await state.update_data(power_unit=str(data.get("power_unit", "")).strip())
        await state.set_state(ApplyForm.comment)
        await callback.message.answer(i18n.get_text(lang, "application.ask_comment"), reply_markup=skip_comment_keyboard(i18n.get_text(lang, "application.skip_comment_button")))

    await callback.answer()

@router.message(ApplyForm.first_name)
async def first_name(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:

    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    data = await state.get_data()
    if not value:
        value = str(data.get("first_name", "")).strip()
    if len(value) < 2 or not is_latin_name(value):
        await message.answer(i18n.get_text(lang, "application.validation_name"))
        return
    await state.update_data(first_name=value)
    await state.set_state(ApplyForm.last_name)
    last_name_prefill = str(data.get("last_name", "")).strip()
    if last_name_prefill:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_last_name_prefilled", last_name_prefill, "last_name")
    else:
        await message.answer(i18n.get_text(lang, "application.ask_last_name"))


@router.message(ApplyForm.last_name)
async def last_name(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    data = await state.get_data()
    if not value:
        value = str(data.get("last_name", "")).strip()
    if len(value) < 2 or not is_latin_name(value):
        await message.answer(i18n.get_text(lang, "application.validation_name"))
        return
    await state.update_data(last_name=value)
    await state.set_state(ApplyForm.phone)
    phone_prefill = str(data.get("phone", "")).strip()
    if phone_prefill:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_phone_prefilled", phone_prefill, "phone")
    else:
        await message.answer(i18n.get_text(lang, "application.ask_phone"))


@router.message(ApplyForm.phone)
async def phone(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:

    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    data = await state.get_data()
    if not value:

        value = str(data.get("phone", "")).strip()
    if not PHONE_RE.match(value):
        await message.answer(i18n.get_text(lang, "application.validation_phone"))
        return
    await state.update_data(phone=value)
    data = await state.get_data()
    if _is_europolis_data(data):
        await _ensure_europolis_contact_from_state(message, state)
        data = await state.get_data()
    await state.set_state(ApplyForm.email)
    email_prefill = str(data.get("email", "")).strip()
    if email_prefill:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_email_prefilled", email_prefill, "email")
    else:
        await message.answer(i18n.get_text(lang, "application.ask_email"))


@router.message(ApplyForm.email)
async def email(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    data = await state.get_data()
    if not value:
        value = str(data.get("email", "")).strip()
    if not EMAIL_RE.match(value):
        await message.answer(i18n.get_text(lang, "application.validation_email"))
        return
    await state.update_data(email=value)
    if _is_europolis_data(data):
        await _ensure_europolis_contact_from_state(message, state)
        await _ask_policyholder_type(message, state, i18n, lang)
    else:
        birth_prefill = str(data.get("birth_date", "")).strip()
        await _ask_birth_date(message, state, i18n, lang, birth_prefill)


@router.callback_query(DialogCalendarCallback.filter(), ApplyForm.birth_date)
async def birth_date_calendar(
    callback: CallbackQuery,
    callback_data: DialogCalendarCallback,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    calendar = _configure_birth_calendar(
        _dialog_calendar(await _calendar_locale(callback.from_user, lang), i18n, lang)
    )
    selected, selected_date = await calendar.process_selection(callback, callback_data)
    if selected:
        await _save_birth_date_and_ask_passport(
            callback.message, state, i18n, lang, selected_date.date()
        )
        await callback.answer()


@router.message(ApplyForm.birth_date)
async def birth_date(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    data = await state.get_data()
    if not value:
        value = str(data.get("birth_date", "")).strip()
    parsed = _parse_common_date(value)
    if not parsed:
        await message.answer(i18n.get_text(lang, "application.validation_date"))
        return
    await _save_birth_date_and_ask_passport(message, state, i18n, lang, parsed)


@router.message(ApplyForm.passport)
async def passport(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = normalize_passport(message.text)
    data = await state.get_data()
    if not value:
        value = normalize_passport(data.get("passport", ""))
    if not is_passport_number(value):
        await message.answer(i18n.get_text(lang, "application.validation_passport"))
        return
    await state.update_data(passport=value)
    await state.set_state(ApplyForm.registration_address)
    address_prefill = str(data.get("registration_address", "")).strip()
    if address_prefill:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_registration_address_prefilled", address_prefill, "registration_address")
    else:
        await message.answer(i18n.get_text(lang, "application.ask_registration_address"))


@router.message(ApplyForm.registration_address)
async def registration_address(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    data = await state.get_data()
    if not value:
        value = str(data.get("registration_address", "")).strip()
    if len(value) < 8:
        await message.answer(i18n.get_text(lang, "application.validation_address"))
        return
    await state.update_data(registration_address=value)
    if _is_europolis_data(data):
        await _ask_vehicle_country_start(message, state, i18n, lang)
    else:
        await _ask_license_plate(message, state, i18n, lang)


@router.callback_query(F.data.startswith("apply:period:"), ApplyForm.insurance_period)
async def insurance_period(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    days = int(callback.data.split(":")[-1])
    await state.update_data(insurance_period=days)
    data = await state.get_data()
    if _is_europolis_data(data):
        await _ask_insurance_start_date(callback.message, state, i18n, lang, callback.from_user)
    else:
        await _finish_vehicle_and_ask_next(callback.message, state, i18n, lang)
    await callback.answer()


@router.callback_query(SimpleCalendarCallback.filter(), ApplyForm.insurance_start_date)
async def insurance_start_date_calendar(
    callback: CallbackQuery,
    callback_data: SimpleCalendarCallback,
    state: FSMContext,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    calendar = _configure_insurance_calendar(
        _simple_calendar(await _calendar_locale(callback.from_user, lang), i18n, lang)
    )
    selected, selected_date = await calendar.process_selection(callback, callback_data)
    if selected:
        await _save_insurance_start_date_and_ask_period(
            callback.message, state, i18n, lang, selected_date.date()
        )
        await callback.answer()


@router.message(ApplyForm.insurance_start_date)
async def insurance_start_date(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    parsed = _parse_common_date(value)
    if not parsed:
        await message.answer(i18n.get_text(lang, "application.validation_date"))
        return

    await _save_insurance_start_date_and_ask_period(message, state, i18n, lang, parsed)



@router.message(ApplyForm.vehicle_country)
async def vehicle_country_text(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    data = await state.get_data()
    if not value:
        value = str(data.get("vehicle_country", "")).strip()
    if len(value) < 2:
        await message.answer(i18n.get_text(lang, "application.validation_vehicle_country"))
        return
    await state.update_data(vehicle_country=value)
    await state.set_state(ApplyForm.vehicle_type)
    type_prefill = str(data.get("vehicle_type", "")).strip()
    if type_prefill:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_vehicle_type_prefilled", type_prefill, "vehicle_type")
    await message.answer(i18n.get_text(lang, "application.choose_from_buttons"), reply_markup=vehicle_types_keyboard(i18n, lang))


@router.callback_query(F.data.startswith("apply:country:"), ApplyForm.vehicle_country)
async def vehicle_country(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    value = callback.data.split(":", 2)[-1]
    await state.update_data(vehicle_country=value)
    await state.set_state(ApplyForm.vehicle_type)
    data = await state.get_data()
    type_prefill = str(data.get("vehicle_type", "")).strip()
    if type_prefill:
        await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_vehicle_type_prefilled", type_prefill, "vehicle_type")
    await callback.message.answer(i18n.get_text(lang, "application.choose_from_buttons"), reply_markup=vehicle_types_keyboard(i18n, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("apply:vtype:"), ApplyForm.vehicle_type)
async def vehicle_type(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    value = callback.data.split(":", 2)[-1]
    await state.update_data(vehicle_type=value)
    data = await state.get_data()
    if _is_europolis_data(data):
        await state.set_state(ApplyForm.insurance_period)
        await callback.message.answer(
            i18n.get_text(lang, "application.ask_insurance_period"),
            reply_markup=periods_keyboard(i18n, lang),
        )
    else:
        await state.set_state(ApplyForm.vin)
        vin_prefill = str(data.get("vin", "")).strip().upper()
        if vin_prefill:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_vin_prefilled", vin_prefill, "vin")
        else:
            await callback.message.answer(i18n.get_text(lang, "application.ask_vin"))
    await callback.answer()



@router.message(ApplyForm.license_plate)
async def license_plate(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    raw = normalize_license_plate(message.text)
    data = await state.get_data()
    is_europolis = _is_europolis_data(data)
    if is_europolis:
        if not is_license_plate_long(raw):
            await message.answer(
                _text_or_default(
                    i18n,
                    lang,
                    "application.validation_license_plate_long",
                    "Госномер: только латинские буквы и цифры, без пробелов/тире, максимум 20 символов.",
                )
            )
            return
        vehicle_docs_prefilled = False
        if hasattr(message.bot, "bitrix_client") and hasattr(
            message.bot.bitrix_client, "find_europolis_vehicle_docs_by_company_and_plate"
        ):
            found_deal = message.bot.bitrix_client.find_europolis_vehicle_docs_by_company_and_plate(
                data.get("bitrix_company_id"), raw
            )
            if found_deal:
                contact_matches = _bitrix_ids_match(
                    found_deal.get("CONTACT_ID"), data.get("bitrix_contact_id")
                )
                company_matches = _bitrix_ids_match(
                    found_deal.get("COMPANY_ID"), data.get("bitrix_company_id")
                )
                if contact_matches or company_matches:
                    vehicle_docs_prefilled = bool(found_deal.get("UF_CRM_1686154280439"))
        await state.update_data(
            license_plate=raw,
            vehicle_docs_prefilled=vehicle_docs_prefilled,
            reuse_existing_vehicle_docs=False,
            vehicle_docs=[],
        )
        await state.set_state(ApplyForm.comment)
        await message.answer(
            i18n.get_text(lang, "application.ask_comment"),
            reply_markup=skip_comment_keyboard(
                i18n.get_text(lang, "application.skip_comment_button")
            ),
        )
        return

    if not is_license_plate(raw):
        await message.answer(i18n.get_text(lang, "application.validation_license_plate_strict"))
        return

    await state.update_data(
        license_plate=raw,
        vehicle_country="",
        brand_model="",
        manufacture_year="",
        vin="",
        vehicle_type="",
        fuel_type="",
        engine_capacity="",
        engine_power="",
        power_unit="",
        comment="",
        vehicle_docs_prefilled=False,
        reuse_existing_vehicle_docs=False,
        vehicle_docs=[],
        insurance_period=None,
        insurance_start_date=None,
    )
    data = await state.get_data()
    bitrix_contact_id = data.get("bitrix_contact_id")
    deal = None
    if hasattr(message.bot, "bitrix_client"):
        found_deal = message.bot.bitrix_client.find_deal_by_license_plate(raw)
        if found_deal and _bitrix_ids_match(found_deal.get("CONTACT_ID"), bitrix_contact_id):
            deal = found_deal

    if deal:
        await state.update_data(
            vehicle_country=_map_bitrix_enum(deal.get("UF_CRM_1686152306664", ""), BITRIX_COUNTRY_MAP),
            brand_model=str(deal.get("UF_CRM_1686152515152", "")).strip(),
            manufacture_year=str(deal.get("UF_CRM_1686152614718", "")).strip(),
            vin=str(deal.get("UF_CRM_1686152659867", "")).strip().upper(),
            vehicle_type=_map_bitrix_enum(deal.get("UF_CRM_1686152567597", ""), BITRIX_VTYPE_MAP),
            fuel_type=_map_bitrix_enum(deal.get("UF_CRM_1686152745455", ""), BITRIX_FUEL_MAP),
            engine_capacity=str(deal.get("UF_CRM_1686152831791", "")).strip(),
            engine_power=str(deal.get("UF_CRM_1686152861297", "")).strip(),
            power_unit=_map_bitrix_enum(deal.get("UF_CRM_1686152902186", ""), BITRIX_POWER_UNIT_MAP),
            vehicle_docs_prefilled=bool(deal.get("UF_CRM_1686154280439")),
            reuse_existing_vehicle_docs=False,
        )
        await state.set_state(ApplyForm.vehicle_data_confirm)
        data = await state.get_data()
        await message.answer(
            _vehicle_data_message(i18n, lang, data),
            reply_markup=data_actual_keyboard(
                i18n.get_text(lang, "application.data_actual"),
                i18n.get_text(lang, "application.data_edit"),
                "vehicle",
            ),
        )
        return

    await message.answer(i18n.get_text(lang, "application.vehicle_not_found_manual"))
    await state.set_state(ApplyForm.vehicle_country)
    await message.answer(i18n.get_text(lang, "application.choose_from_buttons"), reply_markup=countries_keyboard(i18n, lang))


@router.message(ApplyForm.vin)
async def vin(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = normalize_vin(message.text)
    if not is_vin(value):
        await message.answer(i18n.get_text(lang, "application.validation_vin"))
        return
    await state.update_data(vin=value)
    await state.set_state(ApplyForm.brand_model)
    await message.answer(i18n.get_text(lang, "application.ask_brand_model"))


@router.message(ApplyForm.brand_model)
async def brand_model(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    if len(value) < 2:
        await message.answer(i18n.get_text(lang, "application.validation_brand_model"))
        return
    await state.update_data(brand_model=value)
    await state.set_state(ApplyForm.manufacture_year)
    await message.answer(i18n.get_text(lang, "application.ask_manufacture_year"))


@router.message(ApplyForm.manufacture_year)
async def manufacture_year(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    if not value.isdigit() or not 1900 <= int(value) <= datetime.utcnow().year + 1:
        await message.answer(i18n.get_text(lang, "application.validation_year"))
        return
    await state.update_data(manufacture_year=int(value))
    await state.set_state(ApplyForm.fuel_type)
    current = str((await state.get_data()).get("fuel_type", "")).strip()
    if current in FUEL_TYPES:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_fuel_type_prefilled", current, "fuel_type")
    await message.answer(i18n.get_text(lang, "application.ask_fuel_type"), reply_markup=fuel_types_keyboard(i18n, lang))


@router.callback_query(F.data.startswith("apply:fuel:"), ApplyForm.fuel_type)
async def fuel_type(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    value = callback.data.split(":", 2)[-1]
    await state.update_data(fuel_type=value)
    data = await state.get_data()
    if value.lower() == "электро":
        await state.update_data(engine_capacity=0)
        await state.set_state(ApplyForm.engine_power)
        await callback.message.answer(i18n.get_text(lang, "application.skip_engine_capacity_electric"))
        power = str(data.get("engine_power", "")).strip()
        if power:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_engine_power_prefilled", power, "engine_power")
        else:
            await callback.message.answer(i18n.get_text(lang, "application.ask_engine_power"))
    else:
        await state.set_state(ApplyForm.engine_capacity)
        capacity = str(data.get("engine_capacity", "")).strip()
        if capacity:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_engine_capacity_prefilled", capacity, "engine_capacity")
        else:
            await callback.message.answer(i18n.get_text(lang, "application.ask_engine_capacity"))
    await callback.answer()


@router.message(ApplyForm.engine_capacity)
async def engine_capacity(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    if not value.isdigit() or int(value) <= 0:
        await message.answer(i18n.get_text(lang, "application.validation_positive_integer"))
        return
    await state.update_data(engine_capacity=int(value))
    await state.set_state(ApplyForm.engine_power)
    current = str((await state.get_data()).get("engine_power", "")).strip()
    if current:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_engine_power_prefilled", current, "engine_power")
    else:
        await message.answer(i18n.get_text(lang, "application.ask_engine_power"))


@router.message(ApplyForm.engine_power)
async def engine_power(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip().replace(",", ".")
    try:
        parsed = float(value)
        if parsed <= 0:
            raise ValueError
    except ValueError:
        await message.answer(i18n.get_text(lang, "application.validation_positive_number"))
        return
    await state.update_data(engine_power=parsed)
    await state.set_state(ApplyForm.power_unit)
    current = str((await state.get_data()).get("power_unit", "")).strip()
    if current in POWER_UNITS:
        await message.answer(i18n.get_text(lang, "application.ask_power_unit_prefilled").format(value=current))
    await message.answer(i18n.get_text(lang, "application.ask_power_unit"), reply_markup=power_units_keyboard(i18n, lang))


@router.callback_query(F.data.startswith("apply:power:"), ApplyForm.power_unit)
async def power_unit(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    value = callback.data.split(":", 2)[-1]
    await state.update_data(power_unit=value)
    await state.set_state(ApplyForm.comment)

    await callback.message.answer(i18n.get_text(lang, "application.ask_comment"), reply_markup=skip_comment_keyboard(i18n.get_text(lang, "application.skip_comment_button")))
    await callback.answer()


@router.callback_query(F.data == "apply:comment:skip", ApplyForm.comment)
async def comment_skip(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    await state.update_data(comment="")
    data = await state.get_data()
    if data.get("vehicle_docs_prefilled"):
        await state.set_state(ApplyForm.techpass_changed)
        await callback.message.answer(
            i18n.get_text(lang, "application.ask_techpass_changed"),
            reply_markup=techpass_changed_keyboard(
                i18n.get_text(lang, "application.techpass_changed_yes"),
                i18n.get_text(lang, "application.techpass_changed_no"),
            ),
        )
    else:
        await state.set_state(ApplyForm.vehicle_docs)
        await callback.message.answer(i18n.get_text(lang, "application.ask_vehicle_docs"))

    await callback.answer()


@router.message(ApplyForm.comment)
async def comment(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    await state.update_data(comment=(message.text or "").strip())
    data = await state.get_data()
    if data.get("vehicle_docs_prefilled"):
        await state.set_state(ApplyForm.techpass_changed)
        await message.answer(
            i18n.get_text(lang, "application.ask_techpass_changed"),
            reply_markup=techpass_changed_keyboard(
                i18n.get_text(lang, "application.techpass_changed_yes"),
                i18n.get_text(lang, "application.techpass_changed_no"),
            ),
        )
    else:
        await state.set_state(ApplyForm.vehicle_docs)
        await message.answer(i18n.get_text(lang, "application.ask_vehicle_docs"))


@router.callback_query(F.data == "apply:techpass:unchanged", ApplyForm.techpass_changed)
async def techpass_unchanged(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    await state.update_data(reuse_existing_vehicle_docs=True, vehicle_docs=[])
    data = await state.get_data()
    if _is_europolis_data(data):
        await _finish_vehicle_and_ask_next(callback.message, state, i18n, lang)
    else:
        await _ask_insurance_start_date(callback.message, state, i18n, lang, callback.from_user)
    await callback.answer()


@router.callback_query(F.data == "apply:techpass:changed", ApplyForm.techpass_changed)
async def techpass_changed(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    await state.update_data(reuse_existing_vehicle_docs=False)
    await state.set_state(ApplyForm.vehicle_docs)
    await callback.message.answer(i18n.get_text(lang, "application.ask_vehicle_docs"))
    await callback.answer()
@router.message(ApplyForm.vehicle_docs, F.document | F.photo)
async def vehicle_docs(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    data = await state.get_data()
    docs = data.get("vehicle_docs", [])
    if message.document:
        docs.append({"type": "document", "file_id": message.document.file_id, "name": message.document.file_name})
    elif message.photo:
        docs.append({"type": "photo", "file_id": message.photo[-1].file_id, "name": "photo"})
    await state.update_data(vehicle_docs=docs, reuse_existing_vehicle_docs=False)
    await message.answer(
        i18n.get_text(lang, "application.ask_vehicle_docs_complete"),
        reply_markup=vehicle_docs_complete_keyboard(
            i18n.get_text(lang, "application.add_more_docs"),
            i18n.get_text(lang, "application.all_docs_uploaded"),
        ),
    )


@router.callback_query(F.data == "apply:docs:add_more", ApplyForm.vehicle_docs)
async def vehicle_docs_add_more(callback: CallbackQuery, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    await callback.message.answer(i18n.get_text(lang, "application.ask_vehicle_docs"))
    await callback.answer()


@router.callback_query(F.data == "apply:docs:complete", ApplyForm.vehicle_docs)
async def vehicle_docs_complete(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    data = await state.get_data()
    if not data.get("vehicle_docs"):
        await callback.message.answer(i18n.get_text(lang, "application.validation_docs"))
        await callback.answer()
        return
    if _is_europolis_data(data):
        await _finish_vehicle_and_ask_next(callback.message, state, i18n, lang)
    else:
        await _ask_insurance_start_date(callback.message, state, i18n, lang, callback.from_user)
    await callback.answer()


@router.message(ApplyForm.vehicle_docs)
async def vehicle_docs_invalid(message: Message, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    await message.answer(i18n.get_text(lang, "application.validation_docs"))




@router.callback_query(F.data == "apply:vehicle:add", ApplyForm.vehicle_finalize)
async def vehicle_add(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    data = await state.get_data()
    if _is_europolis_data(data):
        await _ask_vehicle_country_start(callback.message, state, i18n, lang)
    else:
        await _ask_license_plate(callback.message, state, i18n, lang)
    await callback.answer()


@router.callback_query(F.data == "apply:vehicle:finish", ApplyForm.vehicle_finalize)
async def vehicle_finish(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    await state.set_state(ApplyForm.consent)
    await callback.message.answer(
        i18n.get_text(lang, "application.ask_consent"),
        reply_markup=consent_keyboard(i18n.get_text(lang, "application.consent_agree"), i18n.get_text(lang, "application.consent_decline")),
    )
    await callback.answer()
@router.callback_query(F.data == "apply:consent:agree", ApplyForm.consent)
async def consent_agree(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    data = await state.get_data()
    try:
        bitrix = _create_bitrix_application(
            data,
            lang,
            callback.bot.bitrix_client,
            callback.from_user.username,
            callback.from_user.id,

        )
        await _attach_telegram_docs_to_deals(callback.bot, callback.bot.bitrix_client, data.get("vehicles", []), bitrix.get("deals", []))
    except Exception as exc:
        logger.exception("telegram_application_bitrix_error user_id=%s error=%s", callback.from_user.id, exc)
        await callback.message.answer(i18n.get_text(lang, "application.bitrix_error"))
        await callback.answer()
        return

    from app.services.reminder_service import ReminderService

    try:
        reminder_service = ReminderService()
        reminder_service.complete_active_drafts(callback.from_user.id)
        reminder_service.mark_calculator_converted(callback.from_user.id)
    except Exception as exc:
        logger.exception("application_reminder_completion_failed user_id=%s error=%s", callback.from_user.id, exc)
    await state.clear()
    await callback.message.answer(i18n.get_text(lang, "application.submitted"))
    await callback.answer()


@router.callback_query(F.data == "apply:consent:decline", ApplyForm.consent)
async def consent_decline(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    from app.services.reminder_service import ReminderService

    try:
        ReminderService().cancel_active_drafts(callback.from_user.id)
    except Exception as exc:
        logger.exception("application_draft_cancel_failed user_id=%s error=%s", callback.from_user.id, exc)
    await state.clear()
    await callback.message.answer(i18n.get_text(lang, "application.declined"))
    await callback.answer()
