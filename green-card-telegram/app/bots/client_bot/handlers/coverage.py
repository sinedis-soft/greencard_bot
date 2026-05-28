from pathlib import Path

from aiogram import F, Router
from aiogram.types import FSInputFile, Message

from app.services.i18n_service import I18nService

router = Router()
COVERAGE_MAP_PATH = Path(__file__).resolve().parents[1] / "img" / "coverage-map.png"


@router.message(F.text == "/coverage")
async def coverage_command(message: Message, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    coverage_text = i18n.get_text(lang, "coverage.text")
    if COVERAGE_MAP_PATH.exists():
        await message.answer_photo(FSInputFile(COVERAGE_MAP_PATH), caption=coverage_text)
        return
    await message.answer(coverage_text)


async def send_coverage(message: Message) -> None:
    await coverage_command(
        message,
        message.bot.i18n,
        message.bot.lang_store,
        message.bot.default_language,
    )
