import os

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.bots.operator_bot.handlers.start import _operator_ids
from app.services.client_broadcast_service import ClientBroadcastService

router = Router()


class RestartBroadcastForm(StatesGroup):
    waiting_admin_token = State()


def _allowed(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in _operator_ids())


@router.message(F.text == "/restart_bot")
async def restart_bot_command(message: Message, state: FSMContext) -> None:
    if not _allowed(message):
        await message.answer(
            message.bot["i18n"].get_text("en", "operator.access_denied")
        )
        return
    if not os.getenv("ADMIN_API_TOKEN", ""):
        await message.answer("ADMIN_API_TOKEN is not configured.")
        return
    await state.set_state(RestartBroadcastForm.waiting_admin_token)
    await message.answer(
        "Введите ADMIN_API_TOKEN, чтобы отправить всем пользователям сообщение "
        "о перезапуске бота."
    )


@router.message(RestartBroadcastForm.waiting_admin_token)
async def restart_bot_confirm(message: Message, state: FSMContext) -> None:
    if not _allowed(message):
        await state.clear()
        await message.answer(
            message.bot["i18n"].get_text("en", "operator.access_denied")
        )
        return
    expected_token = os.getenv("ADMIN_API_TOKEN", "")
    provided_token = (message.text or "").strip()
    if not expected_token or provided_token != expected_token:
        await state.clear()
        await message.answer("Неверный ADMIN_API_TOKEN. Рассылка отменена.")
        return

    result = ClientBroadcastService().send_restart_notice()
    await state.clear()
    await message.answer(
        "Рассылка перезапуска завершена. "
        f"Отправлено: {result['sent']}. Ошибок: {result['failed']}."
    )
