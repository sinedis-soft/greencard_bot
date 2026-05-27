import re

from datetime import datetime, date


from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message


from app.bots.client_bot.keyboards.apply import (
    consent_keyboard,
    countries_keyboard,
    fuel_types_keyboard,
    finalize_vehicle_keyboard,
    periods_keyboard,
    power_units_keyboard,
    prefill_next_keyboard,
    skip_comment_keyboard,

    techpass_changed_keyboard,
    vehicle_types_keyboard,
)
from app.services.i18n_service import I18nService

router = Router()

PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSPORT_RE = re.compile(r"^[A-Za-zА-Яа-я0-9]{6,20}$")
PLATE_RE = re.compile(r"^[A-Z0-9]{1,8}$")

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


def _map_bitrix_enum(value: object, mapping: dict[str, str]) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    return mapping.get(raw, raw)



class ApplyForm(StatesGroup):
    first_name = State()
    last_name = State()
    phone = State()
    email = State()
    birth_date = State()
    passport = State()
    registration_address = State()
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



@router.message(F.text == "/apply")
async def apply_command(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:

    lang = lang_store.get(message.from_user.id, default_language)
    await state.clear()
    await state.update_data(vehicles=[], current_vehicle={})
    await message.answer(i18n.get_text(lang, "application.form_header"))

    contact = None
    username = (message.from_user.username or "").strip()
    if username and hasattr(message.bot, "bitrix_client"):
        contact = message.bot.bitrix_client.find_contact_by_telegram_username(username)

    if contact:
        first_name = str(contact.get("NAME", "")).strip()
        last_name = str(contact.get("LAST_NAME", "")).strip()
        birth_date = _birthdate_to_ddmmyyyy(str(contact.get("BIRTHDATE", "")).strip())
        address = str(contact.get("ADDRESS", "")).strip()
        phone = _extract_multifield(contact.get("PHONE"))
        email = _extract_multifield(contact.get("EMAIL"))
        passport = str(contact.get("UF_CRM_CONTACT_1686145698592", "")).replace(" ", "")

        await state.update_data(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            birth_date=birth_date,
            passport=passport,
            registration_address=address,
        )
        await message.answer(i18n.get_text(lang, "application.prefilled_from_bitrix_editable"))

    await state.set_state(ApplyForm.first_name)
    await message.answer(i18n.get_text(lang, "application.step_1"))
    data = await state.get_data()
    first_name_prefill = str(data.get("first_name", "")).strip()
    if first_name_prefill:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_first_name_prefilled", first_name_prefill, "first_name")
    else:
        await message.answer(i18n.get_text(lang, "application.ask_first_name"))




async def _send_prefilled_prompt(message: Message, i18n: I18nService, lang: str, text_key: str, value: str, field_key: str) -> None:
    await message.answer(
        i18n.get_text(lang, text_key).format(value=value),
        reply_markup=prefill_next_keyboard(i18n.get_text(lang, "application.prefill_next_button"), field_key),
    )


async def send_apply(message: Message, state: FSMContext) -> None:
    await apply_command(message, state, message.bot.i18n, message.bot.lang_store, message.bot.default_language)




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
        await state.set_state(ApplyForm.birth_date)
        value = str(data.get("birth_date", "")).strip()
        if value:
            await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_birth_date_prefilled", value, "birth_date")
        else:
            await callback.message.answer(i18n.get_text(lang, "application.ask_birth_date"))
    elif field == "birth_date":
        await state.update_data(birth_date=str(data.get("birth_date", "")).strip())
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
        await state.set_state(ApplyForm.insurance_period)
        await callback.message.answer(i18n.get_text(lang, "application.step_2"))
        await callback.message.answer(i18n.get_text(lang, "application.ask_insurance_period"), reply_markup=periods_keyboard())
    elif field == "vehicle_country":
        await state.update_data(vehicle_country=str(data.get("vehicle_country", "")).strip())
        await state.set_state(ApplyForm.vehicle_type)
        value = str(data.get("vehicle_type", "")).strip()
        if value:
            await callback.message.answer(i18n.get_text(lang, "application.ask_vehicle_type_prefilled").format(value=value))
        await callback.message.answer(i18n.get_text(lang, "application.choose_from_buttons"), reply_markup=vehicle_types_keyboard())
    elif field == "vehicle_type":
        await state.update_data(vehicle_type=str(data.get("vehicle_type", "")).strip())
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
        await callback.message.answer(i18n.get_text(lang, "application.ask_fuel_type"), reply_markup=fuel_types_keyboard())

    await callback.answer()

@router.message(ApplyForm.first_name)
async def first_name(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:

    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    data = await state.get_data()
    if not value:
        value = str(data.get("first_name", "")).strip()
    if len(value) < 2:
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
    if len(value) < 2:
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
    await state.set_state(ApplyForm.birth_date)
    birth_prefill = str(data.get("birth_date", "")).strip()
    if birth_prefill:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_birth_date_prefilled", birth_prefill, "birth_date")
    else:
        await message.answer(i18n.get_text(lang, "application.ask_birth_date"))


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
    today = date.today()
    age = today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))
    if age < 18:
        await message.answer(i18n.get_text(lang, "application.validation_age_18"))
        return
    await state.update_data(birth_date=_to_ddmmyyyy(parsed))
    await state.set_state(ApplyForm.passport)
    passport_prefill = str(data.get("passport", "")).strip()
    if passport_prefill:
        await _send_prefilled_prompt(message, i18n, lang, "application.ask_passport_prefilled", passport_prefill, "passport")
    else:
        await message.answer(i18n.get_text(lang, "application.ask_passport"))


@router.message(ApplyForm.passport)
async def passport(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    data = await state.get_data()
    if not value:
        value = str(data.get("passport", "")).strip()
    if not PASSPORT_RE.match(value):
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
    await state.set_state(ApplyForm.insurance_period)
    await message.answer(i18n.get_text(lang, "application.step_2"))
    await message.answer(i18n.get_text(lang, "application.ask_insurance_period"), reply_markup=periods_keyboard())


@router.callback_query(F.data.startswith("apply:period:"), ApplyForm.insurance_period)
async def insurance_period(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    days = int(callback.data.split(":")[-1])
    await state.update_data(insurance_period=days)
    await state.set_state(ApplyForm.insurance_start_date)
    await callback.message.answer(i18n.get_text(lang, "application.ask_insurance_start_date"))
    await callback.answer()


@router.message(ApplyForm.insurance_start_date)
async def insurance_start_date(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip()
    parsed = _parse_common_date(value)
    if not parsed:
        await message.answer(i18n.get_text(lang, "application.validation_date"))
        return
    if parsed < date.today():
        await message.answer(i18n.get_text(lang, "application.validation_insurance_start_not_past"))
        return
    await state.update_data(insurance_start_date=_to_ddmmyyyy(parsed))
    await state.set_state(ApplyForm.license_plate)
    await message.answer(i18n.get_text(lang, "application.ask_license_plate_after_start"))


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
        await message.answer(i18n.get_text(lang, "application.ask_vehicle_type_prefilled").format(value=type_prefill))
    await message.answer(i18n.get_text(lang, "application.choose_from_buttons"), reply_markup=vehicle_types_keyboard())


@router.callback_query(F.data.startswith("apply:country:"), ApplyForm.vehicle_country)
async def vehicle_country(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    value = callback.data.split(":", 2)[-1]
    await state.update_data(vehicle_country=value)
    await state.set_state(ApplyForm.vehicle_type)
    data = await state.get_data()
    type_prefill = str(data.get("vehicle_type", "")).strip()
    if type_prefill:
        await callback.message.answer(i18n.get_text(lang, "application.ask_vehicle_type_prefilled").format(value=type_prefill))
    await callback.message.answer(i18n.get_text(lang, "application.choose_from_buttons"), reply_markup=vehicle_types_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("apply:vtype:"), ApplyForm.vehicle_type)
async def vehicle_type(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    value = callback.data.split(":", 2)[-1]
    await state.update_data(vehicle_type=value)
    await state.set_state(ApplyForm.vin)
    data = await state.get_data()
    vin_prefill = str(data.get("vin", "")).strip().upper()
    if vin_prefill:
        await _send_prefilled_prompt(callback.message, i18n, lang, "application.ask_vin_prefilled", vin_prefill, "vin")
    else:
        await callback.message.answer(i18n.get_text(lang, "application.ask_vin"))
    await callback.answer()



@router.message(ApplyForm.license_plate)
async def license_plate(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    raw = (message.text or "").strip().upper()
    if not PLATE_RE.match(raw):
        await message.answer(i18n.get_text(lang, "application.validation_license_plate_strict"))
        return

    await state.update_data(license_plate=raw)
    deal = None
    if hasattr(message.bot, "bitrix_client"):
        deal = message.bot.bitrix_client.find_deal_by_license_plate(raw)

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
        await message.answer(i18n.get_text(lang, "application.prefilled_vehicle_from_bitrix_editable"))

    await state.set_state(ApplyForm.vehicle_country)
    data = await state.get_data()
    country_prefill = str(data.get("vehicle_country", "")).strip()
    if country_prefill:
        await message.answer(i18n.get_text(lang, "application.ask_vehicle_country_prefilled").format(value=country_prefill))
    await message.answer(i18n.get_text(lang, "application.choose_from_buttons"), reply_markup=countries_keyboard())

@router.message(ApplyForm.vin)
async def vin(message: Message, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    value = (message.text or "").strip().upper()
    if len(value) != 17:
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
    await message.answer(i18n.get_text(lang, "application.ask_fuel_type"), reply_markup=fuel_types_keyboard())


@router.callback_query(F.data.startswith("apply:fuel:"), ApplyForm.fuel_type)
async def fuel_type(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    value = callback.data.split(":", 2)[-1]
    await state.update_data(fuel_type=value)
    if value.lower() == "электро":
        await state.update_data(engine_capacity=0)
        await state.set_state(ApplyForm.engine_power)
        await callback.message.answer(i18n.get_text(lang, "application.skip_engine_capacity_electric"))
        await callback.message.answer(i18n.get_text(lang, "application.ask_engine_power"))
    else:
        await state.set_state(ApplyForm.engine_capacity)
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
    await message.answer(i18n.get_text(lang, "application.ask_power_unit"), reply_markup=power_units_keyboard())


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
    vehicle = {
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
        "vehicle_docs": [],
        "reuse_existing_vehicle_docs": True,
    }
    vehicles = data.get("vehicles", [])
    vehicles.append(vehicle)
    await state.update_data(vehicles=vehicles)
    await state.set_state(ApplyForm.vehicle_finalize)
    await callback.message.answer(
        i18n.get_text(lang, "application.ask_vehicle_finalize"),
        reply_markup=finalize_vehicle_keyboard(i18n.get_text(lang, "application.add_vehicle"), i18n.get_text(lang, "application.finish_application")),
    )
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
    await state.update_data(vehicle_docs=docs)
    data = await state.get_data()
    vehicle = {
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
        "vehicle_docs": docs,
        "reuse_existing_vehicle_docs": False,
    }
    vehicles = data.get("vehicles", [])
    vehicles.append(vehicle)
    await state.update_data(vehicles=vehicles)
    await state.set_state(ApplyForm.vehicle_finalize)
    await message.answer(
        i18n.get_text(lang, "application.ask_vehicle_finalize"),
        reply_markup=finalize_vehicle_keyboard(i18n.get_text(lang, "application.add_vehicle"), i18n.get_text(lang, "application.finish_application")),
    )


@router.message(ApplyForm.vehicle_docs)
async def vehicle_docs_invalid(message: Message, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    await message.answer(i18n.get_text(lang, "application.validation_docs"))




@router.callback_query(F.data == "apply:vehicle:add", ApplyForm.vehicle_finalize)
async def vehicle_add(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    await state.set_state(ApplyForm.insurance_period)
    await callback.message.answer(i18n.get_text(lang, "application.ask_insurance_period"), reply_markup=periods_keyboard())
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
    await state.clear()
    await callback.message.answer(i18n.get_text(lang, "application.submitted"))
    await callback.answer()


@router.callback_query(F.data == "apply:consent:decline", ApplyForm.consent)
async def consent_decline(callback: CallbackQuery, state: FSMContext, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    await state.clear()
    await callback.message.answer(i18n.get_text(lang, "application.declined"))
    await callback.answer()
