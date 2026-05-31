from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

LANGUAGES = [
    ("ru", "Русская"),
    ("en", "English"),
    ("pl", "Polski"),
    ("ka", "ქართული"),
    ("kk", "Қазақша"),
]


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, label in LANGUAGES:
        builder.button(text=label, callback_data=f"lang:{code}")
    builder.adjust(2)
    return builder.as_markup()
