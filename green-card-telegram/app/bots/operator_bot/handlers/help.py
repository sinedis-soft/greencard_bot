from aiogram import F, Router
from aiogram.types import Message

from app.bots.operator_bot.command_menu import operator_help_text
from app.bots.operator_bot.handlers.start import _allowed
from app.bots.operator_bot.keyboards.operator_menu import operator_main_keyboard
from app.services.i18n_service import I18nService

router = Router()


@router.message(F.text == "/help")
async def help_command(message: Message, i18n: I18nService) -> None:
    if not _allowed(message):
        await message.answer(i18n.get_text("en", "operator.access_denied"))
        return
    await message.answer(operator_help_text(), reply_markup=operator_main_keyboard())
