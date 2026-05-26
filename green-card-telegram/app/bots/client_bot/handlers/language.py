from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bots.client_bot.keyboards.language import language_keyboard
from app.bots.client_bot.keyboards.main_menu import main_menu_keyboard
from app.services.i18n_service import I18nService

router = Router()


@router.message(F.text == "/start")
async def start_command(message: Message, i18n: I18nService) -> None:
    await message.answer(i18n.get_text("en", "language.select"), reply_markup=language_keyboard())


@router.message(F.text == "/menu")
async def menu_command(message: Message, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    await message.answer(i18n.get_text(lang, "menu.title"), reply_markup=main_menu_keyboard(i18n, lang))


@router.callback_query(F.data.startswith("lang:"))
async def choose_language(
    callback: CallbackQuery,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = callback.data.split(":", maxsplit=1)[1]
    lang_store[callback.from_user.id] = lang
    await callback.message.answer(
        i18n.get_text(lang, "language.changed"),
        reply_markup=main_menu_keyboard(i18n, lang),
    )
    await callback.answer()
