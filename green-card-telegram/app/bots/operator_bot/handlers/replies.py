import re
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bots.operator_bot.handlers.start import _operator_ids
from app.services.operator_notifier_service import (
    ClientNotifierService,
    OperatorNotifierService,
)
from app.services.operator_ticket_service import OperatorTicketService

router = Router()

_TICKET_ID_PATTERN = re.compile(r"(?:^|\n)ID:\s*(\S+)")


class PolicyFileDeliveryForm(StatesGroup):
    awaiting_file = State()
    review_files = State()


def _policy_file_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Отправить", callback_data="policy_files:send")
    builder.button(text="Добавить еще файл", callback_data="policy_files:add_more")
    builder.adjust(1)
    return builder.as_markup()

def _telegram_name(user_id: int | None, username: str = "") -> str:
    username = (username or "").strip()
    if username:
        return username if username.startswith("@") else f"@{username}"
    return f"Telegram ID {user_id}" if user_id else "не указан"


def _operator_name(message: Message | CallbackQuery) -> str:
    user = message.from_user
    if not user:
        return "не указан"
    if user.username:
        return f"@{user.username}"
    return user.full_name or f"Telegram ID {user.id}"



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

def _allowed(message: Message | CallbackQuery) -> bool:

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


def _ticket_for_operator_action(
    request_id: str, operator_id: int | None
):

    svc = OperatorTicketService()
    ticket = svc.get_ticket(request_id)
    if not ticket or not ticket.telegram_user_id:
        return svc, ticket, "Ticket not found or has no client Telegram ID"
    assigned_operator_id = ticket.operator_id
    if assigned_operator_id and assigned_operator_id != operator_id:
        return svc, ticket, (
            f"Request {request_id} is already assigned to operator "
            f"{assigned_operator_id}"
        )
    return svc, ticket, ""


async def _download_operator_file(
    message: Message, file_info: dict[str, str], tmp_dir: str, index: int = 1
) -> str:
    telegram_file = await message.bot.get_file(file_info["file_id"])
    filename = _safe_filename(file_info["name"], f"policy-file-{index}.bin")
    destination = Path(tmp_dir) / f"{index}-{filename}"
    await message.bot.download_file(telegram_file.file_path, destination=destination)
    return str(destination)


async def _send_operator_reply(message: Message, request_id: str, text: str) -> None:
    if not _allowed(message):
        await message.answer(
            message.bot["i18n"].get_text("en", "operator.access_denied")
        )
        return
    svc, ticket, error = _ticket_for_operator_action(request_id, message.from_user.id)
    if error:
        await message.answer(error)
        return
    is_first_operator_reply = ticket.operator_id is None

    svc.assign_operator_if_empty(request_id, message.from_user.id)
    ClientNotifierService().send_to_client(
        ticket.telegram_user_id, text, client_bot=ticket.client_bot
    )
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

    svc, ticket, error = _ticket_for_operator_action(request_id, message.from_user.id)
    if error:
        await message.answer(error)
        return

    is_first_operator_action = ticket.operator_id is None
    svc.assign_operator_if_empty(request_id, message.from_user.id)
    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = await _download_operator_file(message, file_info, tmp_dir)
        ClientNotifierService().send_document_to_client(
            ticket.telegram_user_id, local_path, client_bot=ticket.client_bot
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


async def _start_policy_file_session(
    message: Message, state: FSMContext, request_id: str
) -> None:
    if not _allowed(message):
        await message.answer(
            message.bot["i18n"].get_text("en", "operator.access_denied")
        )
        return
    svc, ticket, error = _ticket_for_operator_action(request_id, message.from_user.id)
    if error:
        await message.answer(error)
        return
    svc.assign_operator_if_empty(request_id, message.from_user.id)
    await state.set_state(PolicyFileDeliveryForm.awaiting_file)
    await state.update_data(request_id=request_id, policy_files=[])
    await message.answer(
        "Прикрепите полис документом/фото. Можно прикрепить несколько файлов: "
        "после каждого файла нажмите «Добавить еще файл» или «Отправить»."
    )


async def _send_policy_file_session(
    event: Message | CallbackQuery, state: FSMContext
) -> None:
    user_id = event.from_user.id if event.from_user else None
    if not _allowed(event):
        target = event.message if isinstance(event, CallbackQuery) else event
        await target.answer(target.bot["i18n"].get_text("en", "operator.access_denied"))
        return
    data = await state.get_data()
    request_id = str(data.get("request_id") or "")
    files = list(data.get("policy_files") or [])
    target_message = event.message if isinstance(event, CallbackQuery) else event
    if not request_id or not files:
        await target_message.answer("Прикрепите хотя бы один файл полиса.")
        return

    svc, ticket, error = _ticket_for_operator_action(request_id, user_id)
    if error:
        await target_message.answer(error)
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        for index, file_info in enumerate(files, start=1):
            local_path = await _download_operator_file(
                target_message, file_info, tmp_dir, index
            )
            ClientNotifierService().send_document_to_client(
                ticket.telegram_user_id, local_path, client_bot=ticket.client_bot
            )
    svc.set_status(request_id, "waiting_client")
    svc.log_action(
        request_id,
        user_id,
        "send_policy_files",
        ", ".join(file_info.get("name", "") for file_info in files),
    )
    OperatorNotifierService().notify_operator_reply_sent(
        _operator_done_notification(
            request_id,
            _client_name_for_ticket(svc, ticket.telegram_user_id),
            _operator_name(event),
        ),
        exclude_operator_id=user_id,
    )
    await state.clear()
    await target_message.answer("Полис отправлен клиенту.")

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
async def reply(message: Message, state: FSMContext) -> None:
    parts = message.text.split(maxsplit=2)
    if len(parts) == 2:
        await _start_policy_file_session(message, state, parts[1])
        return
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


@router.message(PolicyFileDeliveryForm.awaiting_file, F.document | F.photo)
@router.message(PolicyFileDeliveryForm.review_files, F.document | F.photo)
async def policy_file_session_file(message: Message, state: FSMContext) -> None:
    if not _allowed(message):
        await message.answer(
            message.bot["i18n"].get_text("en", "operator.access_denied")
        )
        return
    file_info = _operator_file_from_message(message)
    if not file_info:
        await message.answer("Прикрепите документ или фото полиса.")
        return
    data = await state.get_data()
    files = list(data.get("policy_files") or [])
    files.append(file_info)
    await state.update_data(policy_files=files)
    await state.set_state(PolicyFileDeliveryForm.review_files)
    await message.answer(
        "Файл добавлен. Отправить клиенту или добавить еще файл?",
        reply_markup=_policy_file_keyboard(),
    )


@router.message(PolicyFileDeliveryForm.awaiting_file)
@router.message(PolicyFileDeliveryForm.review_files)
async def policy_file_session_non_file(message: Message) -> None:
    await message.answer("Прикрепите документ или фото полиса.")


@router.callback_query(
    F.data == "policy_files:add_more", PolicyFileDeliveryForm.review_files
)
async def policy_file_session_add_more(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await state.set_state(PolicyFileDeliveryForm.awaiting_file)
    await callback.message.answer("Прикрепите следующий файл полиса.")
    await callback.answer()


@router.callback_query(F.data == "policy_files:send", PolicyFileDeliveryForm.review_files)
async def policy_file_session_send(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await _send_policy_file_session(callback, state)
    await callback.answer()

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
