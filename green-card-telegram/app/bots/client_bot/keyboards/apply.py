from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.i18n_service import I18nService


INSURANCE_PERIODS = [30, 60, 90, 120, 180, 364]
COUNTRIES = [
    ("belarus", "application.options.countries.belarus"),
    ("russia", "application.options.countries.russia"),
    ("kazakhstan", "application.options.countries.kazakhstan"),
    ("uzbekistan", "application.options.countries.uzbekistan"),
    ("turkey", "application.options.countries.turkey"),
    ("usa", "application.options.countries.usa"),
    ("united kingdom", "application.options.countries.united_kingdom"),
    ("azerbaijan", "application.options.countries.azerbaijan"),
    ("georgia", "application.options.countries.georgia"),
    ("moldova", "application.options.countries.moldova"),
    ("ukraine", "application.options.countries.ukraine"),
    ("armenia", "application.options.countries.armenia"),
    ("other country", "application.options.countries.other_country"),
]
VEHICLE_TYPES = [
    ("car", "application.options.vehicle_types.car"),
    ("truck", "application.options.vehicle_types.truck"),
    ("moto", "application.options.vehicle_types.moto"),
    ("bus", "application.options.vehicle_types.bus"),
    ("trailer", "application.options.vehicle_types.trailer"),
]
FUEL_TYPES = [
    ("petrol", "application.options.fuel_types.petrol"),
    ("diesel", "application.options.fuel_types.diesel"),
    ("gas", "application.options.fuel_types.gas"),
    ("electric", "application.options.fuel_types.electric"),
    ("hybrid", "application.options.fuel_types.hybrid"),
]
POWER_UNITS = [
    ("hp", "application.options.power_units.hp"),
    ("kw", "application.options.power_units.kw"),
]


def _options_keyboard(options: list[tuple[str, str]], prefix: str, i18n: I18nService, lang: str, row_size: int = 2) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for value, text_key in options:
        builder.button(text=i18n.get_text(lang, text_key), callback_data=f"{prefix}:{value}")
    builder.adjust(*([row_size] * ((len(options) + row_size - 1) // row_size)))
    return builder.as_markup()


def periods_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for days in INSURANCE_PERIODS:
        builder.button(text=f"{days} дней", callback_data=f"apply:period:{days}")
    builder.adjust(3)
    return builder.as_markup()


def countries_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return _options_keyboard(COUNTRIES, "apply:country", i18n, lang)


def vehicle_types_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return _options_keyboard(VEHICLE_TYPES, "apply:vtype", i18n, lang)


def fuel_types_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return _options_keyboard(FUEL_TYPES, "apply:fuel", i18n, lang)


def power_units_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return _options_keyboard(POWER_UNITS, "apply:power", i18n, lang)


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
