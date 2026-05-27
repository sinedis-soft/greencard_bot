from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


INSURANCE_PERIODS = [30, 60, 90, 120, 180, 364]
COUNTRIES = [
    "Беларусь",
    "Россия",
    "Казахстан",
    "Узбекистан",
    "Турция",
    "США",
    "Великобритания",
    "Азербайджан",
    "Грузия",
    "Молдова",
    "Украина",
    "Армения",
    "Другая страна",
]
VEHICLE_TYPES = ["Легковой", "Грузовой", "Мотоцикл", "Автобус", "Прицеп"]
FUEL_TYPES = ["Бензин", "Дизель", "Газ / бензин", "Электро", "Гибрид"]
POWER_UNITS = ["Лошадиные силы", "Киловат"]


def _options_keyboard(options: list[str], prefix: str, row_size: int = 2) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in options:
        builder.button(text=item, callback_data=f"{prefix}:{item}")
    builder.adjust(*([row_size] * ((len(options) + row_size - 1) // row_size)))
    return builder.as_markup()


def periods_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for days in INSURANCE_PERIODS:
        builder.button(text=f"{days} дней", callback_data=f"apply:period:{days}")
    builder.adjust(3)
    return builder.as_markup()


def countries_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(COUNTRIES, "apply:country")


def vehicle_types_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(VEHICLE_TYPES, "apply:vtype")


def fuel_types_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(FUEL_TYPES, "apply:fuel")


def power_units_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(POWER_UNITS, "apply:power")


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


def skip_comment_keyboard(button_text: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=button_text, callback_data="apply:comment:skip")

    return builder.as_markup()
