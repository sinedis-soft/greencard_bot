from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.i18n_service import I18nService


INSURANCE_PERIODS = [30, 60, 90, 120, 180, 364]
COUNTRIES = [
    ("Беларусь", "belarus"),
    ("Россия", "russia"),
    ("Казахстан", "kazakhstan"),
    ("Узбекистан", "uzbekistan"),
    ("Турция", "turkey"),
    ("США", "usa"),
    ("Великобритания", "united_kingdom"),
    ("Азербайджан", "azerbaijan"),
    ("Грузия", "georgia"),
    ("Молдова", "moldova"),
    ("Украина", "ukraine"),
    ("Армения", "armenia"),
    ("Другая страна", "other"),
]
VEHICLE_TYPES = [
    ("Легковой", "car"),
    ("Грузовой", "truck"),
    ("Мотоцикл", "moto"),
    ("Автобус", "bus"),
    ("Прицеп", "trailer"),
]
FUEL_TYPES = [
    ("Бензин", "petrol"),
    ("Дизель", "diesel"),
    ("Газ / бензин", "gas_petrol"),
    ("Электро", "electric"),
    ("Гибрид", "hybrid"),
]
POWER_UNITS = [("Лошадиные силы", "hp"), ("Киловат", "kw")]


def _option_text(i18n: I18nService, lang: str, key: str, default_text: str) -> str:
    text = i18n.get_text(lang, key)
    return default_text if text == key else text


def _options_keyboard(
    i18n: I18nService,
    lang: str,
    options: list[tuple[str, str]],
    prefix: str,
    translation_prefix: str,
    row_size: int = 2,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for value, key in options:
        builder.button(
            text=_option_text(i18n, lang, f"{translation_prefix}.{key}", value),
            callback_data=f"{prefix}:{value}",
        )
    builder.adjust(*([row_size] * ((len(options) + row_size - 1) // row_size)))
    return builder.as_markup()


def periods_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for days in INSURANCE_PERIODS:
        builder.button(
            text=i18n.get_text(lang, "application.options.period_days").format(days=days),
            callback_data=f"apply:period:{days}",
        )
    builder.adjust(3)
    return builder.as_markup()


def countries_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return _options_keyboard(i18n, lang, COUNTRIES, "apply:country", "application.options.countries")


def vehicle_types_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return _options_keyboard(i18n, lang, VEHICLE_TYPES, "apply:vtype", "application.options.vehicle_types")


def fuel_types_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return _options_keyboard(i18n, lang, FUEL_TYPES, "apply:fuel", "application.options.fuel_types")


def power_units_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return _options_keyboard(i18n, lang, POWER_UNITS, "apply:power", "application.options.power_units")


def finalize_vehicle_keyboard(add_text: str, finish_text: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=add_text, callback_data="apply:vehicle:add")
    builder.button(text=finish_text, callback_data="apply:vehicle:finish")
    builder.adjust(1)
    return builder.as_markup()


def consent_keyboard(agree_text: str, decline_text: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=agree_text, callback_data="apply:consent:agree")
    builder.button(text=decline_text, callback_data="apply:consent:decline")
    builder.adjust(1)
    return builder.as_markup()


def techpass_changed_keyboard(yes_text: str, no_text: str) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    builder.button(text=yes_text, callback_data="apply:techpass:changed")
    builder.button(text=no_text, callback_data="apply:techpass:unchanged")
    builder.adjust(1)
    return builder.as_markup()


def prefill_next_keyboard(button_text: str, field_key: str) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    builder.button(text=button_text, callback_data=f"apply:prefill-next:{field_key}")
    return builder.as_markup()


def data_actual_keyboard(actual_text: str, edit_text: str, prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=actual_text, callback_data=f"apply:{prefix}:actual")
    builder.button(text=edit_text, callback_data=f"apply:{prefix}:edit")
    builder.adjust(1)
    return builder.as_markup()


def skip_comment_keyboard(button_text: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=button_text, callback_data="apply:comment:skip")

    return builder.as_markup()


def vehicle_docs_complete_keyboard(add_more_text: str, all_uploaded_text: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=add_more_text, callback_data="apply:docs:add_more")
    builder.button(text=all_uploaded_text, callback_data="apply:docs:complete")
    builder.adjust(1)
    return builder.as_markup()
