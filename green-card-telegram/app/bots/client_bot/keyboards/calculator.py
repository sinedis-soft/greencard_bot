from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.i18n_service import I18nService

VEHICLE_TYPES = ["car", "truck", "bus", "moto", "trailer", "special"]
PERIODS = [30, 60, 90, 180, 365]


def vehicle_types_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for vtype in VEHICLE_TYPES:
        builder.button(text=i18n.get_text(lang, f"calculator.vehicle.{vtype}"), callback_data=f"calc:vehicle:{vtype}")
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def periods_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for days in PERIODS:
        builder.button(text=str(days), callback_data=f"calc:period:{days}")
    builder.adjust(3, 2)
    return builder.as_markup()
