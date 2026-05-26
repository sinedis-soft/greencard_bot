from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder


def apply_webapp_keyboard(button_text: str, mini_app_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=button_text, web_app=WebAppInfo(url=mini_app_url))
    return builder.as_markup()
