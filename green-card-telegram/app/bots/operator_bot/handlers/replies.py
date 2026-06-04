import re
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.types import Message

from app.bots.operator_bot.handlers.start import _operator_ids
from app.services.operator_notifier_service import (
    ClientNotifierService,
    OperatorNotifierService,
)
from app.services.operator_ticket_service import OperatorTicketService

router = Router()

_TICKET_ID_PATTERN = re.compile(r"(?:^|\n)ID:\s*(\S+)")


def _telegram_name(user_id: int | None, username: str = "") -> str:
    username = (username or "").strip()
    if username:
        return username if username.startswith("@") else f"@{username}"
    return f"Telegram ID {user_id}" if user_id else "не указан"


def _operator_name(message: Message) -> str:
    if not message.from_user:
        return "не указан"
    if message.from_user.username:
        return f"@{message.from_user.username}"
    return message.from_user.full_name or f"Telegram ID {message.from_user.id}"


def _operator_reply_notification(
    request_id: str, client_name: str, operator_name: str
) -> str:
    return (
        f"Клиенту {client_name} ответил на request_id {request_id} "
        f"оператор {operator_name}"
    )

def _operator_done_notification(
    request_id: str, client_name: str, operator_name: str
) -> str:
    return (
        f"Оператор {operator_name} выполнил действие по request_id {request_id} "
        f"для клиента {client_name}. Остальным операторам выполнять это действие не нужно."
    )

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


def _client_name_for_ticket(
    svc: OperatorTicketService, telegram_user_id: int | None
) -> str:
    return _telegram_name(telegram_user_id, svc.get_client_username(telegram_user_id))


def _safe_filename(value: str, fallback: str) -> str:
    filename = Path(value or fallback).name.strip() or fallback
    return "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in filename)


def _operator_file_from_message(message: Message) -> dict[str, str] | None:
    if message.document:
        return {
            "file_id": message.document.file_id,
            "name": message.document.file_name or "policy-document.pdf",
        }
    if message.photo:
        return {"file_id": message.photo[-1].file_id, "name": "policy-photo.jpg"}
    return None


async def _send_operator_reply(message: Message, request_id: str, text: str) -> None:
    if not _allowed(message):
        await message.answer(
            message.bot["i18n"].get_text("en", "operator.access_denied")
        )
        return
    svc = OperatorTicketService()
    ticket = svc.get_ticket(request_id)
    if not ticket or not ticket.telegram_user_id:
        await message.answer("Ticket not found or has no client Telegram ID")
        return
    assigned_operator_id = ticket.operator_id
    if assigned_operator_id and assigned_operator_id != message.from_user.id:
        await message.answer(
            f"Request {request_id} is already assigned to operator {assigned_operator_id}"
        )
        return

    is_first_operator_reply = assigned_operator_id is None
    svc.assign_operator_if_empty(request_id, message.from_user.id)
    ClientNotifierService().send_to_client(ticket.telegram_user_id, text)
    svc.set_status(request_id, "waiting_client")
    svc.log_action(request_id, message.from_user.id, "reply", text)
    if is_first_operator_reply:

        OperatorNotifierService().notify_operator_reply_sent(
            _operator_reply_notification(
                request_id,
                _client_name_for_ticket(svc, ticket.telegram_user_id),
                _operator_name(message),
            ),

            exclude_operator_id=message.from_user.id if message.from_user else None,
        )
    await message.answer(message.bot["i18n"].get_text("en", "operator.reply_sent"))


async def _send_operator_file_reply(message: Message, request_id: str) -> None:
    if not _allowed(message):
        await message.answer(
            message.bot["i18n"].get_text("en", "operator.access_denied")
        )
        return
    file_info = _operator_file_from_message(message)
    if not file_info:
        return

    svc = OperatorTicketService()
    ticket = svc.get_ticket(request_id)
    if not ticket or not ticket.telegram_user_id:
        await message.answer("Ticket not found or has no client Telegram ID")
        return
    assigned_operator_id = ticket.operator_id
    if assigned_operator_id and assigned_operator_id != message.from_user.id:
        await message.answer(
            f"Request {request_id} is already assigned to operator {assigned_operator_id}"
        )
        return

    is_first_operator_action = assigned_operator_id is None
    svc.assign_operator_if_empty(request_id, message.from_user.id)
    telegram_file = await message.bot.get_file(file_info["file_id"])
    with tempfile.TemporaryDirectory() as tmp_dir:
        destination = Path(tmp_dir) / _safe_filename(
            file_info["name"], "policy-file.bin"
        )
        await message.bot.download_file(
            telegram_file.file_path, destination=destination
        )
        ClientNotifierService().send_document_to_client(
            ticket.telegram_user_id, str(destination)
        )
    svc.set_status(request_id, "waiting_client")
    svc.log_action(
        request_id, message.from_user.id, "send_policy_file", file_info["name"]
    )
    if is_first_operator_action:
        OperatorNotifierService().notify_operator_reply_sent(
            _operator_done_notification(
                request_id,
                _client_name_for_ticket(svc, ticket.telegram_user_id),
                _operator_name(message),
            ),
            exclude_operator_id=message.from_user.id if message.from_user else None,
        )
    await message.answer(
        "Файл отправлен клиенту. Если есть еще файлы, отправьте их следующим "
        "сообщением ответом на этот же request_id."
    )


async def _mark_operator_action_done(message: Message, request_id: str) -> None:
    if not _allowed(message):
        await message.answer(
            message.bot["i18n"].get_text("en", "operator.access_denied")
        )
        return
    svc = OperatorTicketService()
    ticket = svc.get_ticket(request_id)
    if not ticket:
        await message.answer("Ticket not found")
        return
    assigned_operator_id = ticket.operator_id
    if ticket.status == "closed":
        await message.answer("Действие уже отмечено выполненным.")
        return
    if assigned_operator_id and assigned_operator_id != message.from_user.id:
        await message.answer(
            f"Request {request_id} is already assigned to operator {assigned_operator_id}"
        )
        return
    svc.assign_operator_if_empty(request_id, message.from_user.id)
    svc.set_status(request_id, "closed")
    svc.log_action(request_id, message.from_user.id, "done")
    OperatorNotifierService().notify_operator_reply_sent(
        _operator_done_notification(
            request_id,
            _client_name_for_ticket(svc, ticket.telegram_user_id),
            _operator_name(message),
        ),
        exclude_operator_id=message.from_user.id if message.from_user else None,
    )
    await message.answer("Действие отмечено выполненным.")


@router.message(F.text.startswith("/reply "))
async def reply(message: Message) -> None:
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Usage: /reply <request_id> <message>")
        return
    request_id, text = parts[1], parts[2]
    await _send_operator_reply(message, request_id, text)


@router.message(F.text.startswith("/done "))
async def done(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /done <request_id>")
        return
    await _mark_operator_action_done(message, parts[1])


@router.message(F.reply_to_message & F.text)
async def reply_to_ticket_message(message: Message) -> None:
    original_text = message.reply_to_message.text or message.reply_to_message.caption
    request_id = _extract_request_id(original_text)
    if not request_id:
        return
    await _send_operator_reply(message, request_id, message.text)


@router.message(F.reply_to_message & (F.document | F.photo))
async def reply_file_to_ticket_message(message: Message) -> None:
    original_text = message.reply_to_message.text or message.reply_to_message.caption
    request_id = _extract_request_id(original_text)
    if not request_id:
        return
    await _send_operator_file_reply(message, request_id)
