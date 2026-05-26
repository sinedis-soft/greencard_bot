from aiogram import F, Router
from aiogram.types import Message

from app.services.i18n_service import I18nService

router = Router()


@router.message(F.text == "/coverage")
async def coverage_command(message: Message, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    await message.answer(i18n.get_text(lang, "coverage.text"))
    await message.answer(i18n.get_text(lang, "coverage.map_todo"))


async def send_coverage(message: Message) -> None:
    await coverage_command(
    message,
    message.bot.i18n,
    message.bot.lang_store,
    message.bot.default_language,
)
