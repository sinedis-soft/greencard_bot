from aiogram import F, Router
from aiogram.types import Message

from app.services.operator_notifier_service import ClientNotifierService
from app.services.operator_ticket_service import OperatorTicketService

router = Router()


@router.message(F.text.startswith("/reply "))
async def reply(message: Message) -> None:
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return
    request_id, text = parts[1], parts[2]
    svc = OperatorTicketService()
    ticket = svc.get_ticket(request_id)
    if not ticket or not ticket.telegram_user_id:
        return
    ClientNotifierService().send_to_client(ticket.telegram_user_id, text)
    svc.set_status(request_id, "waiting_client")
    svc.log_action(request_id, message.from_user.id, "reply", text)
    await message.answer(message.bot["i18n"].get_text("en", "operator.reply_sent"))
