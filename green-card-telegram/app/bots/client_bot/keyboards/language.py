from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

LANGUAGES = [
    ("be", "Беларуская"),
    ("ru", "Русская"),
    ("uk", "Українська"),
    ("mn", "Монгол"),
    ("en", "English"),
    ("ro", "Română"),
    ("tr", "Türkçe"),
    ("kk", "Қазақша"),
    ("uz", "O‘zbekcha"),
    ("ka", "ქართული"),
    ("hy", "Հայերեն"),
    ("fa", "فارسی"),
]


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lang, label in LANGUAGES:
        builder.button(text=label, callback_data=f"lang:{lang}")
    builder.adjust(3, 2)
    return builder.as_markup()
