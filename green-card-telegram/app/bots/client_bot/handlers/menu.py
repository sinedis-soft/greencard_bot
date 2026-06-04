import tempfile
from pathlib import Path
from uuid import uuid4

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bots.client_bot.handlers.apply import send_apply
from app.bots.client_bot.handlers.calculator import start_calculator
from app.bots.client_bot.handlers.coverage import send_coverage
from app.bots.client_bot.handlers.faq import show_faq_categories
from app.bots.client_bot.keyboards.language import language_keyboard
from app.bots.client_bot.keyboards.main_menu import main_menu_keyboard
from app.bots.client_bot.menu_actions import menu_action_for_text
from app.bots.operator_bot.keyboards.ticket_actions import (
    reply_command,
    reply_instruction,
)
from app.services.bitrix24_client import LICENSE_PLATE_FIELD, POLICY_FILES_FIELD
from app.services.latest_deal_formatter import is_invoice_deal, latest_deal_text
from app.services.operator_message_formatter import operator_language_line
from app.services.operator_notifier_service import OperatorNotifierService
from app.services.operator_ticket_service import OperatorTicketService, TicketPayload

router = Router()


class PaymentConfirmationForm(StatesGroup):
    awaiting_file = State()
    review_files = State()


def _policy_delivery_keyboard(i18n, lang: str, deal_id: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.get_text(lang, "latest_deal.delivery_email_button"),
        callback_data=f"latest_deal_policy:email:{deal_id}",
    )
    builder.button(
        text=i18n.get_text(lang, "latest_deal.delivery_chat_button"),
        callback_data=f"latest_deal_policy:chat:{deal_id}",
    )
    builder.adjust(1)
    return builder.as_markup()


def _policy_file_infos_from_deal(deal: dict, bitrix_client) -> list[dict]:
    deal_id = deal.get("ID")
    if deal_id:
        try:
            infos = bitrix_client.get_deal_file_infos(deal_id)
            if infos:
                return infos
        except RuntimeError:
            pass
    value = deal.get(POLICY_FILES_FIELD)
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _client_summary(user, lang: str) -> str:
    username = f"@{user.username}" if user and user.username else "—"
    return (
        f"Клиент: {user.full_name if user else '—'}\n"
        f"Telegram ID: {user.id if user else '—'}\n"
        f"Username: {username}\n"
        f"{operator_language_line(lang)}"
    )


def _policy_delivery_request_text(
    request_id: str, delivery_method: str, deal_id: str, user, lang: str
) -> str:
    client = _client_summary(user, lang)
    if delivery_method == "email":
        return (
            "📧 Клиент просит прислать полис на почту\n"
            f"ID: {request_id}\n"
            f"{client}\n"
            f"ID сделки: {deal_id}\n"
            f"Необходимо перевести сделку {deal_id} в стадию ОТПРАВИТЬ ПОЛИС.\n"
            f"Когда действие выполнено, отправьте: /done {request_id}"
        )
    return (
        "📎 Клиент просит прислать полис сюда, в Telegram-диалог\n"
        f"ID: {request_id}\n"
        f"{client}\n"
        f"ID сделки: {deal_id}\n"
        "Необходимо прислать клиенту полис в диалог. "
        "Ответьте на это сообщение документом/фото. "
        "Если файлов несколько, отправьте их поочередно ответом на это сообщение.\n"
        f"Текстовый ответ клиенту: {reply_command(request_id)}"
    )


async def _create_policy_delivery_ticket(
    callback: CallbackQuery, delivery_method: str, deal_id: str, lang: str
) -> None:
    request_id = f"policy-{delivery_method}-{deal_id}-{uuid4().hex[:8]}"
    OperatorTicketService().create_ticket(
        TicketPayload(
            request_id=request_id,
            telegram_user_id=callback.from_user.id if callback.from_user else None,
            client_name=callback.from_user.full_name if callback.from_user else "",
            client_phone="",
            preferred_language=lang,
            vehicle_type="",
            license_plate="",
            vin="",
            insurance_period_days=0,
            insurance_start_date="",
            comment=(
                f"Policy delivery request ({delivery_method}) "
                f"for Bitrix deal {deal_id}."
            ),
        )
    )
    OperatorNotifierService().notify_new_ticket(
        _policy_delivery_request_text(
            request_id, delivery_method, deal_id, callback.from_user, lang
        )
    )
    await callback.message.answer(
        callback.bot.i18n.get_text(lang, "latest_deal.delivery_request_sent")
    )


def _payment_confirmation_keyboard(i18n, lang: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.get_text(lang, "payment_confirmation.send_button"),
        callback_data="payment_confirmation:send",
    )
    builder.button(
        text=i18n.get_text(lang, "payment_confirmation.add_more_button"),
        callback_data="payment_confirmation:add_more",
    )
    builder.adjust(1)
    return builder.as_markup()


def _latest_deal_offer_keyboard(i18n, lang: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.get_text(lang, "main_menu.latest_deal"),
        callback_data="payment_confirmation:latest_deal",
    )
    return builder.as_markup()


def _payment_file_from_message(message: Message) -> dict[str, str] | None:
    if message.document:
        return {
            "type": "document",
            "file_id": message.document.file_id,
            "name": message.document.file_name or "payment-confirmation.pdf",
        }
    if message.photo:
        return {
            "type": "photo",
            "file_id": message.photo[-1].file_id,
            "name": "payment-confirmation.jpg",
        }
    return None


def _safe_filename(value: str, fallback: str) -> str:
    filename = Path(value or fallback).name.strip() or fallback
    return "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in filename)


async def _download_payment_files(
    message: Message, files: list[dict[str, str]], target_dir: Path
) -> list[str]:
    downloaded: list[str] = []
    for index, file_info in enumerate(files, start=1):
        telegram_file = await message.bot.get_file(file_info["file_id"])
        filename = _safe_filename(
            file_info.get("name", ""), f"payment-confirmation-{index}.bin"
        )
        destination = target_dir / f"{index}-{filename}"
        await message.bot.download_file(telegram_file.file_path, destination=destination)
        downloaded.append(str(destination))
    return downloaded


def _payment_operator_text(lang: str, data: dict, user) -> str:
    client_name = user.full_name if user else ""
    username = f"@{user.username}" if user and user.username else "—"
    request_id = str(data.get("request_id") or "")
    return (
        "💳 Подтверждение оплаты\n"
        f"ID: {request_id}\n"
        f"Клиент: {client_name}\n"
        f"Telegram ID: {user.id if user else '—'}\n"
        f"Username: {username}\n"
        f"{operator_language_line(lang)}\n"
        f"Госномер авто: {data.get('license_plate') or '—'}\n"
        f"ID сделки: {data.get('deal_id') or '—'}\n"
        f"Ответ клиенту: {reply_command(request_id)}"
    )


def _operator_ticket_text(request_id: str, client_name: str, source: str, preferred_language: str) -> str:
    return (
        "🆘 Новый запрос оператора\n"
        f"ID: {request_id}\n"
        f"Клиент: {client_name}\n"
        f"{operator_language_line(preferred_language)}\n"
        f"Источник: {source}\n"
        f"{reply_instruction(request_id)}"
    )


async def _forward_client_message_to_operator(message: Message) -> bool:
    if not message.from_user or not message.text:
        return False
    ticket = OperatorTicketService().get_active_by_user(message.from_user.id)
    if not ticket:
        return False
    client_name = message.from_user.full_name
    OperatorTicketService().mark_client_message(ticket.request_id)
    operator_message = (
        "💬 Сообщение клиента\n"
        f"ID: {ticket.request_id}\n"
        f"Клиент: {client_name}\n"
        f"{operator_language_line(ticket.preferred_language)}\n"
        f"Текст: {message.text}\n"
        f"{reply_instruction(ticket.request_id)}"
    )
    notifier = OperatorNotifierService()
    if ticket.operator_id:
        notifier.notify_operator_direct(
            ticket.operator_id, operator_message, reply_command(ticket.request_id)
        )
    else:
        notifier.notify_new_ticket(operator_message, reply_command(ticket.request_id))
    await message.answer(
        message.bot.i18n.get_text(
            message.bot.lang_store.get(
                message.from_user.id, message.bot.default_language
            ),
            "operator.request_received",
        )
    )
    return True


async def _send_latest_deal(message: Message, lang: str, user=None) -> None:
    user = user or message.from_user
    if not user:
        return
    bitrix_client = getattr(message.bot, "bitrix_client", None)
    if bitrix_client is None:
        await message.answer(message.bot.i18n.get_text(lang, "latest_deal.unavailable"))
        return

    username = user.username or ""
    try:
        deal = bitrix_client.find_latest_deal_by_telegram_identity(
            username=username,
            user_id=user.id,
        )
    except RuntimeError:
        await message.answer(message.bot.i18n.get_text(lang, "latest_deal.unavailable"))
        return
    if not deal:
        await message.answer(message.bot.i18n.get_text(lang, "latest_deal.not_found"))
        return

    await message.answer(latest_deal_text(message.bot.i18n, lang, deal))
    deal_id = str(deal.get("ID") or "")
    if deal_id and _policy_file_infos_from_deal(deal, bitrix_client):
        await message.answer(
            message.bot.i18n.get_text(lang, "latest_deal.delivery_prompt"),
            reply_markup=_policy_delivery_keyboard(message.bot.i18n, lang, deal_id),
        )


async def _start_payment_confirmation(
    message: Message, state: FSMContext, lang: str
) -> None:
    if not message.from_user:
        return
    bitrix_client = getattr(message.bot, "bitrix_client", None)
    if bitrix_client is None:
        await message.answer(message.bot.i18n.get_text(lang, "latest_deal.unavailable"))
        return

    try:
        contact = bitrix_client.find_contact_by_telegram_identity(
            username=message.from_user.username or "",
            user_id=message.from_user.id,
        )
        deal = (
            bitrix_client.find_latest_deal_by_contact_id(contact["ID"])
            if contact and contact.get("ID")
            else None
        )
    except RuntimeError:
        await message.answer(message.bot.i18n.get_text(lang, "latest_deal.unavailable"))
        return

    if not deal or not is_invoice_deal(deal):
        await message.answer(
            message.bot.i18n.get_text(lang, "payment_confirmation.no_unpaid"),
            reply_markup=_latest_deal_offer_keyboard(message.bot.i18n, lang),
        )
        return

    await state.set_state(PaymentConfirmationForm.awaiting_file)
    await state.update_data(
        payment_files=[],
        request_id=f"pay-{message.from_user.id}-{uuid4().hex[:8]}",
        deal_id=str(deal.get("ID") or ""),
        license_plate=str(deal.get(LICENSE_PLATE_FIELD) or ""),
    )
    await message.answer(
        message.bot.i18n.get_text(lang, "payment_confirmation.attach_prompt")
    )


@router.message(PaymentConfirmationForm.awaiting_file, F.document | F.photo)
@router.message(PaymentConfirmationForm.review_files, F.document | F.photo)
async def payment_confirmation_file(message: Message, state: FSMContext) -> None:
    lang = message.bot.lang_store.get(message.from_user.id, message.bot.default_language)
    file_info = _payment_file_from_message(message)
    if not file_info:
        await message.answer(
            message.bot.i18n.get_text(lang, "payment_confirmation.attach_prompt")
        )
        return

    data = await state.get_data()
    files = list(data.get("payment_files") or [])
    files.append(file_info)
    await state.update_data(payment_files=files)
    await state.set_state(PaymentConfirmationForm.review_files)
    await message.answer(
        message.bot.i18n.get_text(lang, "payment_confirmation.file_received"),
        reply_markup=_payment_confirmation_keyboard(message.bot.i18n, lang),
    )


@router.message(PaymentConfirmationForm.awaiting_file)
@router.message(PaymentConfirmationForm.review_files)
async def payment_confirmation_non_file(message: Message) -> None:
    lang = message.bot.lang_store.get(message.from_user.id, message.bot.default_language)
    await message.answer(
        message.bot.i18n.get_text(lang, "payment_confirmation.attach_prompt")
    )


@router.callback_query(
    F.data == "payment_confirmation:add_more", PaymentConfirmationForm.review_files
)
async def payment_confirmation_add_more(
    callback: CallbackQuery, state: FSMContext
) -> None:
    lang = callback.bot.lang_store.get(
        callback.from_user.id, callback.bot.default_language
    )
    await state.set_state(PaymentConfirmationForm.awaiting_file)
    await callback.message.answer(
        callback.bot.i18n.get_text(lang, "payment_confirmation.attach_prompt")
    )
    await callback.answer()


@router.callback_query(
    F.data == "payment_confirmation:send", PaymentConfirmationForm.review_files
)
async def payment_confirmation_send(
    callback: CallbackQuery, state: FSMContext
) -> None:
    lang = callback.bot.lang_store.get(
        callback.from_user.id, callback.bot.default_language
    )
    data = await state.get_data()
    files = list(data.get("payment_files") or [])
    if not files:
        await callback.message.answer(
            callback.bot.i18n.get_text(lang, "payment_confirmation.attach_prompt")
        )
        await callback.answer()
        return

    request_id = str(
        data.get("request_id") or f"pay-{callback.from_user.id}-{uuid4().hex[:8]}"
    )
    data["request_id"] = request_id
    OperatorTicketService().create_ticket(
        TicketPayload(
            request_id=request_id,
            telegram_user_id=callback.from_user.id if callback.from_user else None,
            client_name=callback.from_user.full_name if callback.from_user else "",
            client_phone="",
            preferred_language=lang,
            vehicle_type="",
            license_plate=str(data.get("license_plate") or ""),
            vin="",
            insurance_period_days=0,
            insurance_start_date="",
            comment=f"Payment confirmation for Bitrix deal {data.get('deal_id') or '—'}.",
        )
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        local_paths = await _download_payment_files(
            callback.message, files, Path(tmp_dir)
        )
        OperatorNotifierService().notify_payment_confirmation(
            _payment_operator_text(lang, data, callback.from_user),
            local_paths,
        )

    await state.clear()
    await callback.message.answer(
        callback.bot.i18n.get_text(lang, "payment_confirmation.sent"),
        reply_markup=main_menu_keyboard(callback.bot.i18n, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("latest_deal_policy:"))
async def latest_deal_policy_delivery(callback: CallbackQuery) -> None:
    lang = callback.bot.lang_store.get(
        callback.from_user.id, callback.bot.default_language
    )
    parts = (callback.data or "").split(":", maxsplit=2)
    if len(parts) != 3 or parts[1] not in {"email", "chat"}:
        await callback.answer()
        return
    await _create_policy_delivery_ticket(callback, parts[1], parts[2], lang)
    await callback.answer()


@router.callback_query(F.data == "payment_confirmation:latest_deal")
async def payment_confirmation_latest_deal(callback: CallbackQuery) -> None:
    lang = callback.bot.lang_store.get(
        callback.from_user.id, callback.bot.default_language
    )
    await _send_latest_deal(callback.message, lang, callback.from_user)
    await callback.answer()


@router.message(F.text)
async def menu_click_router(message: Message, state: FSMContext) -> None:
    lang = message.bot.lang_store.get(
        message.from_user.id, message.bot.default_language
    )
    action = menu_action_for_text(
        message.bot.i18n, message.text, lang, message.bot.default_language
    )

    if action == "calculator":
        await start_calculator(message)
    elif action == "faq":
        await show_faq_categories(message)
    elif action == "coverage":
        await send_coverage(message)
    elif action == "apply":
        await send_apply(message, state)
    elif action == "latest_deal":
        await _send_latest_deal(message, lang)
    elif action == "payment_confirmation":
        await _start_payment_confirmation(message, state, lang)
    elif action == "language":
        await message.answer(
            message.bot.i18n.get_text(lang, "language.select"),
            reply_markup=language_keyboard(),
        )
    elif action == "operator":
        request_id = f"op-{message.from_user.id}-{uuid4().hex[:8]}"
        client_name = message.from_user.full_name if message.from_user else ""
        OperatorTicketService().create_ticket(
            TicketPayload(
                request_id=request_id,
                telegram_user_id=message.from_user.id if message.from_user else None,
                client_name=client_name,
                client_phone="",
                preferred_language=lang,
                vehicle_type="",
                license_plate="",
                vin="",
                insurance_period_days=0,
                insurance_start_date="",
                comment="Main menu: user requested operator assistance.",
            )
        )
        OperatorNotifierService().notify_new_ticket(
            _operator_ticket_text(request_id, client_name, "Главное меню", lang),
            reply_command(request_id),
        )
        await message.answer(
            message.bot.i18n.get_text(lang, "operator.operator_connected")
        )
    else:
        await _forward_client_message_to_operator(message)
