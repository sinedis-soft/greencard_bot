from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

LANGUAGES = ["ru", "en", "pl", "ka", "kk"]


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lang in LANGUAGES:
        builder.button(text=lang.upper(), callback_data=f"lang:{lang}")
    builder.adjust(3, 2)
    return builder.as_markup()
