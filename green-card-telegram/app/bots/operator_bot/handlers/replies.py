import re

from aiogram import F, Router
from aiogram.types import Message

from app.bots.operator_bot.handlers.start import _operator_ids
from app.services.operator_notifier_service import ClientNotifierService
from app.services.operator_ticket_service import OperatorTicketService

router = Router()

_TICKET_ID_PATTERN = re.compile(r"(?:^|\n)ID:\s*(\S+)")


def _allowed(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in _operator_ids())


def _extract_request_id(text: str | None) -> str | None:
    if not text:
        return None
    match = _TICKET_ID_PATTERN.search(text)
    if match:
        return match.group(1)
    first_line = text.splitlines()[0].strip()
    if " | " in first_line:
        return first_line.split(" | ", maxsplit=1)[0]
    return None


async def _send_operator_reply(message: Message, request_id: str, text: str) -> None:
    if not _allowed(message):
        await message.answer(message.bot["i18n"].get_text("en", "operator.access_denied"))
        return
    svc = OperatorTicketService()
    ticket = svc.get_ticket(request_id)
    if not ticket or not ticket.telegram_user_id:
        await message.answer("Ticket not found or has no client Telegram ID")
        return
    ClientNotifierService().send_to_client(ticket.telegram_user_id, text)
    svc.set_status(request_id, "waiting_client")
    svc.log_action(request_id, message.from_user.id, "reply", text)
    await message.answer(message.bot["i18n"].get_text("en", "operator.reply_sent"))


@router.message(F.text.startswith("/reply "))
async def reply(message: Message) -> None:
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Usage: /reply <request_id> <message>")
        return
    request_id, text = parts[1], parts[2]
    await _send_operator_reply(message, request_id, text)


@router.message(F.reply_to_message & F.text)
async def reply_to_ticket_message(message: Message) -> None:
    original_text = message.reply_to_message.text or message.reply_to_message.caption
    request_id = _extract_request_id(original_text)
    if not request_id:
        return
    await _send_operator_reply(message, request_id, message.text)
