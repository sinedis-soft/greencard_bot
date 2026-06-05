from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.i18n_service import I18nService

VEHICLE_TYPES = ["car", "truck", "bus", "moto", "trailer", "special"]
PERIODS = [30, 60, 90, 180, 365]


def vehicle_types_keyboard(
    i18n: I18nService, lang: str, vehicle_types: tuple[str, ...] | None = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    selected_vehicle_types = vehicle_types or tuple(VEHICLE_TYPES)
    for vtype in selected_vehicle_types:
        builder.button(
            text=i18n.get_text(lang, f"calculator.vehicle.{vtype}"),
            callback_data=f"calc:vehicle:{vtype}",
        )
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def periods_keyboard(
    i18n: I18nService | None = None, lang: str = ""
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for days in PERIODS:
        text = str(days)
        if i18n is not None and lang:
            key = f"calculator.period.{days}"
            localized = i18n.get_text(lang, key)
            if localized != key:
                text = localized
        builder.button(text=text, callback_data=f"calc:period:{days}")
    builder.adjust(3, 2)
    return builder.as_markup()


def apply_cta_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.get_text(lang, "calculator.apply_cta"), callback_data="calc:apply"
    )
    builder.adjust(1)
    return builder.as_markup()
