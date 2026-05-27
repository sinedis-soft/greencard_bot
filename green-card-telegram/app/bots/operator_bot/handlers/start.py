from aiogram import F, Router
from aiogram.types import Message
import os

from app.services.i18n_service import I18nService

router = Router()


def _operator_ids() -> set[int]:
    return {int(x.strip()) for x in os.getenv("OPERATOR_IDS", "").split(",") if x.strip()}


def _allowed(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in _operator_ids())


@router.message(F.text == "/start")
async def start(message: Message, i18n: I18nService) -> None:
    if not _allowed(message):
        await message.answer(i18n.get_text("en", "operator.access_denied"))
        return
    await message.answer(i18n.get_text("en", "operator.operator_connected"))
