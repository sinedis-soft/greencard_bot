from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bots.operator_bot.handlers.start import _operator_ids
from app.bots.operator_bot.keyboards.ticket_actions import reply_command, reply_instruction
from app.services.client_bot_notifier import notify_client_operator_connected
from app.services.operator_ticket_service import OperatorTicketService

router = Router()


def _callback_allowed(callback: CallbackQuery) -> bool:
    return bool(callback.from_user and callback.from_user.id in _operator_ids())


@router.callback_query(F.data.startswith("take:"))
async def take_callback(callback: CallbackQuery) -> None:
    if not _callback_allowed(callback):
        await callback.answer(callback.bot["i18n"].get_text("en", "operator.access_denied"), show_alert=True)
        return
    request_id = callback.data.split(":", 1)[1]
    svc = OperatorTicketService()
    svc.set_status(request_id, "in_progress")
    svc.log_action(request_id, callback.from_user.id, "take")
    notify_client_operator_connected(request_id)
    await callback.message.answer(
        f"{callback.bot['i18n'].get_text('en', 'operator.taken')}\n{reply_instruction(request_id)}"
    )
    await callback.message.answer(reply_command(request_id))
    await callback.answer()


@router.callback_query(F.data.startswith("reply_help:"))
async def reply_help_callback(callback: CallbackQuery) -> None:
    if not _callback_allowed(callback):
        await callback.answer(callback.bot["i18n"].get_text("en", "operator.access_denied"), show_alert=True)
        return
    request_id = callback.data.split(":", 1)[1]
    await callback.message.answer(reply_instruction(request_id))
    await callback.message.answer(reply_command(request_id))
    await callback.answer()


@router.callback_query(F.data.startswith("close:"))
async def close_callback(callback: CallbackQuery) -> None:
    if not _callback_allowed(callback):
        await callback.answer(callback.bot["i18n"].get_text("en", "operator.access_denied"), show_alert=True)
        return
    request_id = callback.data.split(":", 1)[1]
    svc = OperatorTicketService()
    svc.set_status(request_id, "closed")
    svc.log_action(request_id, callback.from_user.id, "close")
    await callback.message.answer(callback.bot["i18n"].get_text("en", "operator.closed"))
    await callback.answer()


@router.message(F.text.startswith("/take "))
async def take_cmd(message: Message) -> None:
    if message.from_user.id not in _operator_ids():
        await message.answer(message.bot["i18n"].get_text("en", "operator.access_denied"))
        return
    request_id = message.text.split(maxsplit=1)[1]
    svc = OperatorTicketService()
    if svc.set_status(request_id, "in_progress"):
        svc.log_action(request_id, message.from_user.id, "take")
        notify_client_operator_connected(request_id)
        await message.answer(f"{message.bot['i18n'].get_text('en', 'operator.taken')}\n{reply_instruction(request_id)}")
        await message.answer(reply_command(request_id))


@router.message(F.text.startswith("/close "))
async def close_cmd(message: Message) -> None:
    if message.from_user.id not in _operator_ids():
        await message.answer(message.bot["i18n"].get_text("en", "operator.access_denied"))
        return
    request_id = message.text.split(maxsplit=1)[1]
    svc = OperatorTicketService()
    if svc.set_status(request_id, "closed"):
        svc.log_action(request_id, message.from_user.id, "close")
        await message.answer(message.bot["i18n"].get_text("en", "operator.closed"))
