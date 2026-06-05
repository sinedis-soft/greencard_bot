from aiogram import F, Router
from aiogram.types import Message

from app.bots.operator_bot.keyboards.operator_menu import operator_main_keyboard
from app.services.i18n_service import I18nService
from app.services.operator_service import OperatorService

router = Router()


def _operator_ids() -> set[int]:
    return OperatorService().active_operator_ids()


def _allowed(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in _operator_ids())


@router.message(F.text == "/start")
async def start(message: Message, i18n: I18nService) -> None:
    if not _allowed(message):
        await message.answer(i18n.get_text("en", "operator.access_denied"))
        return
    await message.answer(
        i18n.get_text("en", "operator.operator_connected"),
        reply_markup=operator_main_keyboard(),
    )
