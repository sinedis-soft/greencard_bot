from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.services.client_bot_notifier import notify_client_operator_connected
from app.services.operator_ticket_service import OperatorTicketService

router = Router()


@router.callback_query(F.data.startswith("take:"))
async def take_callback(callback: CallbackQuery) -> None:
    request_id = callback.data.split(":", 1)[1]
    svc = OperatorTicketService()
    svc.set_status(request_id, "in_progress")
    svc.log_action(request_id, callback.from_user.id, "take")
    notify_client_operator_connected(request_id)
    await callback.message.answer(callback.bot["i18n"].get_text("en", "operator.taken"))
    await callback.answer()


@router.callback_query(F.data.startswith("close:"))
async def close_callback(callback: CallbackQuery) -> None:
    request_id = callback.data.split(":", 1)[1]
    svc = OperatorTicketService()
    svc.set_status(request_id, "closed")
    svc.log_action(request_id, callback.from_user.id, "close")
    await callback.message.answer(callback.bot["i18n"].get_text("en", "operator.closed"))
    await callback.answer()


@router.message(F.text.startswith("/take "))
async def take_cmd(message: Message) -> None:
    request_id = message.text.split(maxsplit=1)[1]
    svc = OperatorTicketService()
    if svc.set_status(request_id, "in_progress"):
        svc.log_action(request_id, message.from_user.id, "take")
        notify_client_operator_connected(request_id)
        await message.answer(message.bot["i18n"].get_text("en", "operator.taken"))


@router.message(F.text.startswith("/close "))
async def close_cmd(message: Message) -> None:
    request_id = message.text.split(maxsplit=1)[1]
    svc = OperatorTicketService()
    if svc.set_status(request_id, "closed"):
        svc.log_action(request_id, message.from_user.id, "close")
        await message.answer(message.bot["i18n"].get_text("en", "operator.closed"))
