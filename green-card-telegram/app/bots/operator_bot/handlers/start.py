from aiogram import F, Router
from aiogram.types import Message

from app.services.i18n_service import I18nService

router = Router()


def _allowed(message: Message) -> bool:
    ids = getattr(message.bot, "operator_ids", set())
    return message.from_user and message.from_user.id in ids


@router.message(F.text == "/start")
async def start(message: Message, i18n: I18nService) -> None:
    if not _allowed(message):
        await message.answer(i18n.get_text("en", "operator.access_denied"))
        return
    await message.answer(i18n.get_text("en", "operator.operator_connected"))
