from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.services.i18n_service import I18nService


def main_menu_keyboard(i18n: I18nService, lang: str) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=i18n.get_text(lang, "main_menu.calculator"))
    builder.button(text=i18n.get_text(lang, "main_menu.faq"))
    builder.button(text=i18n.get_text(lang, "main_menu.coverage"))
    builder.button(text=i18n.get_text(lang, "main_menu.apply"))
    builder.button(text=i18n.get_text(lang, "main_menu.operator"))
    builder.button(text=i18n.get_text(lang, "main_menu.language"))
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)
