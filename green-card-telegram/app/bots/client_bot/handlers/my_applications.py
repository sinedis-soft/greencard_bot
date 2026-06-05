from __future__ import annotations

import tempfile
from uuid import uuid4

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.bots.client_bot.states.payment import PaymentConfirmationForm
from app.bots.client_bot.states.repeat import RepeatApplicationForm
from app.bots.client_bot.keyboards.my_applications import (
    application_actions_keyboard,
    contact_operator_keyboard,
    policy_status_keyboard,
    repeat_confirm_keyboard,
    repeat_docs_keyboard,
    repeat_periods_keyboard,
)
from app.bots.operator_bot.keyboards.ticket_actions import reply_command
from app.core.config import get_settings
from app.services.bitrix24_client import Bitrix24Client, LICENSE_PLATE_FIELD, POLICY_FILES_FIELD
from app.services.bitrix_deal_mapper import safe_deal_card, safe_deal_text
from app.services.client_application_service import ClientApplicationService
from app.services.operator_message_formatter import operator_language_line
from app.services.operator_notifier_service import OperatorNotifierService
from app.services.operator_ticket_service import OperatorTicketService, TicketPayload
from app.services.repeat_application_service import RepeatApplicationError, RepeatApplicationService
from app.services.policy_status_service import PolicyStatusError, PolicyStatusService

router = Router()


def _bitrix_client(bot) -> Bitrix24Client:
    return getattr(bot, "bitrix_client", None) or Bitrix24Client(
        get_settings().bitrix24_webhook_url
    )


def _service(bot) -> ClientApplicationService:
    return ClientApplicationService(_bitrix_client(bot))


def _repeat_service(bot) -> RepeatApplicationService:
    return RepeatApplicationService(_bitrix_client(bot))


def _policy_status_service(bot) -> PolicyStatusService:
    return PolicyStatusService(_service(bot))


def _lang(message: Message | CallbackQuery) -> str:
    bot = message.bot
    user = message.from_user
    return bot.lang_store.get(user.id, bot.default_language) if user else bot.default_language


async def send_my_applications(
    message: Message,
    telegram_user_id: int | None = None,
    telegram_chat_id: int | None = None,
    lang: str | None = None,
) -> None:
    lang = lang or _lang(message)
    user_id = telegram_user_id or (message.from_user.id if message.from_user else None)
    if not user_id:
        return
    try:
        result = _service(message.bot).list_my_applications(
            telegram_user_id=user_id,
            telegram_chat_id=telegram_chat_id or message.chat.id,
            limit=10,
        )
    except RuntimeError:
        await message.answer(message.bot.i18n.get_text(lang, "my_applications.unavailable"))
        return

    items = result.get("items", [])
    if not items:
        await message.answer(
            message.bot.i18n.get_text(lang, "my_applications.empty"),
            reply_markup=contact_operator_keyboard(message.bot.i18n, lang),
        )
        return

    await message.answer(message.bot.i18n.get_text(lang, "my_applications.title"))
    for index, card in enumerate(items, start=1):
        deal_id = card.get("deal_id")
        if not deal_id:
            continue
        await message.answer(
            safe_deal_text(card, index=index),
            reply_markup=application_actions_keyboard(
                message.bot.i18n, lang, deal_id, card.get("actions") or {}
            ),
        )


@router.message(F.text.in_({"/my", "/applications", "/orders"}))
async def my_applications_command(message: Message) -> None:
    await send_my_applications(message)


async def _verified_card(callback: CallbackQuery, deal_id: str) -> dict | None:
    lang = _lang(callback)
    if not callback.from_user:
        return None
    try:
        deal = _service(callback.bot).get_client_deal(
            telegram_user_id=callback.from_user.id,
            telegram_chat_id=callback.message.chat.id if callback.message else callback.from_user.id,
            deal_id=deal_id,
        )
    except RuntimeError:
        await callback.message.answer(callback.bot.i18n.get_text(lang, "my_applications.unavailable"))
        return None
    if not deal:
        await callback.message.answer(callback.bot.i18n.get_text(lang, "my_applications.not_found"))
        return None
    return safe_deal_card(deal) | {"_raw_deal": deal}


@router.callback_query(F.data.startswith("myapp:open:"))
async def open_application(callback: CallbackQuery) -> None:
    lang = _lang(callback)
    deal_id = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    card = await _verified_card(callback, deal_id)
    if card:
        await callback.message.answer(
            safe_deal_text(card),
            reply_markup=application_actions_keyboard(
                callback.bot.i18n, lang, int(deal_id), card.get("actions") or {}
            ),
        )
    await callback.answer()





@router.callback_query(F.data == "myapp:list")
async def my_applications_callback(callback: CallbackQuery) -> None:
    if callback.message and callback.from_user:
        await send_my_applications(
            callback.message,
            telegram_user_id=callback.from_user.id,
            telegram_chat_id=callback.message.chat.id,
            lang=_lang(callback),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("myapp:policy_status:"))
async def check_policy_status(callback: CallbackQuery) -> None:
    lang = _lang(callback)
    if not callback.from_user:
        await callback.answer()
        return
    deal_id = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    try:
        result = _policy_status_service(callback.bot).check(
            telegram_user_id=callback.from_user.id,
            telegram_chat_id=callback.message.chat.id if callback.message else callback.from_user.id,
            deal_id=int(deal_id),
            preferred_language=lang,
            client_name=callback.from_user.full_name,
            client_bot=getattr(callback.bot, "client_bot_code", "default"),
        )
    except (RuntimeError, PolicyStatusError):
        await callback.message.answer(callback.bot.i18n.get_text(lang, "policy_status.unavailable"))
        await callback.answer()
        return

    await callback.message.answer(
        result.get("message") or callback.bot.i18n.get_text(lang, "policy_status.unavailable"),
        reply_markup=policy_status_keyboard(
            callback.bot.i18n, lang, int(deal_id), result.get("actions") or {}
        ),
    )
    await callback.answer()

@router.callback_query(F.data.startswith("myapp:repeat:"))
async def repeat_application_start(callback: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(callback)
    if not callback.from_user:
        await callback.answer()
        return
    deal_id = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    try:
        result = _repeat_service(callback.bot).start(
            telegram_user_id=callback.from_user.id,
            telegram_chat_id=callback.message.chat.id if callback.message else callback.from_user.id,
            old_deal_id=int(deal_id),
        )
    except (RuntimeError, RepeatApplicationError):
        await callback.message.answer(callback.bot.i18n.get_text(lang, "repeat_application.unavailable"))
        await callback.answer()
        return
    await state.set_state(RepeatApplicationForm.waiting_start_date)
    await state.update_data(draft_id=result["draft_id"], old_deal_id=int(deal_id))
    await callback.message.answer(
        callback.bot.i18n.get_text(lang, "repeat_application.start_prompt").format(
            vehicle_plate_masked=result.get("vehicle_plate_masked") or "—",
            vehicle_type=result.get("vehicle_type") or "—",
            registration_country=result.get("registration_country") or "—",
        )
    )
    await callback.answer()


@router.message(RepeatApplicationForm.waiting_start_date, F.text)
async def repeat_application_start_date(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    data = await state.get_data()
    try:
        _repeat_service(message.bot).update(
            draft_id=str(data.get("draft_id") or ""),
            telegram_user_id=message.from_user.id,
            new_start_date=message.text,
        )
    except RepeatApplicationError:
        await message.answer(message.bot.i18n.get_text(lang, "repeat_application.invalid_start_date"))
        return
    except RuntimeError:
        await message.answer(message.bot.i18n.get_text(lang, "repeat_application.unavailable"))
        return
    await state.set_state(RepeatApplicationForm.waiting_period)
    await message.answer(
        message.bot.i18n.get_text(lang, "repeat_application.ask_period"),
        reply_markup=repeat_periods_keyboard(message.bot.i18n, lang),
    )


@router.callback_query(F.data.startswith("repeat:period:"), RepeatApplicationForm.waiting_period)
async def repeat_application_period(callback: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(callback)
    data = await state.get_data()
    period = int((callback.data or "").rsplit(":", maxsplit=1)[-1])
    try:
        _repeat_service(callback.bot).update(
            draft_id=str(data.get("draft_id") or ""),
            telegram_user_id=callback.from_user.id,
            new_period_days=period,
        )
    except (RuntimeError, RepeatApplicationError):
        await callback.message.answer(callback.bot.i18n.get_text(lang, "repeat_application.unavailable"))
        await callback.answer()
        return
    await state.set_state(RepeatApplicationForm.waiting_docs_mode)
    await callback.message.answer(
        callback.bot.i18n.get_text(lang, "repeat_application.ask_docs"),
        reply_markup=repeat_docs_keyboard(callback.bot.i18n, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("repeat:docs:"), RepeatApplicationForm.waiting_docs_mode)
async def repeat_application_docs(callback: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(callback)
    data = await state.get_data()
    docs_mode = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    try:
        preview = _repeat_service(callback.bot).update(
            draft_id=str(data.get("draft_id") or ""),
            telegram_user_id=callback.from_user.id,
            docs_mode=docs_mode,
        )
    except (RuntimeError, RepeatApplicationError):
        await callback.message.answer(callback.bot.i18n.get_text(lang, "repeat_application.unavailable"))
        await callback.answer()
        return
    await state.set_state(RepeatApplicationForm.waiting_confirmation)
    await state.update_data(docs_mode=docs_mode)
    await callback.message.answer(
        callback.bot.i18n.get_text(lang, "repeat_application.preview").format(
            vehicle_plate_masked=preview.get("vehicle_plate_masked") or "—",
            new_start_date=preview.get("new_start_date") or "—",
            new_period_days=preview.get("new_period_days") or "—",
            docs_mode_title=preview.get("docs_mode_title") or "—",
        ),
        reply_markup=repeat_confirm_keyboard(callback.bot.i18n, lang),
    )
    await callback.answer()


@router.callback_query(F.data == "repeat:change", RepeatApplicationForm.waiting_confirmation)
async def repeat_application_change(callback: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(callback)
    await state.set_state(RepeatApplicationForm.waiting_start_date)
    await callback.message.answer(callback.bot.i18n.get_text(lang, "repeat_application.ask_start_date"))
    await callback.answer()


@router.callback_query(F.data == "repeat:cancel", RepeatApplicationForm.waiting_confirmation)
async def repeat_application_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(callback)
    await state.clear()
    await callback.message.answer(callback.bot.i18n.get_text(lang, "repeat_application.cancelled"))
    await callback.answer()


@router.callback_query(F.data == "repeat:confirm", RepeatApplicationForm.waiting_confirmation)
async def repeat_application_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(callback)
    data = await state.get_data()
    try:
        result = _repeat_service(callback.bot).confirm(
            draft_id=str(data.get("draft_id") or ""),
            telegram_user_id=callback.from_user.id,
            telegram_chat_id=callback.message.chat.id if callback.message else callback.from_user.id,
        )
    except (RuntimeError, RepeatApplicationError):
        await callback.message.answer(callback.bot.i18n.get_text(lang, "repeat_application.unavailable"))
        await callback.answer()
        return
    if data.get("docs_mode") == "reuse":
        await _create_operator_ticket(
            callback,
            {
                "deal_id": result.bitrix_deal_id,
                "product_type": "OC graniczne (border insurance)",
                "vehicle_plate_masked": "—",
                "public_status": result.public_status,
            },
            "repeat_docs_reuse_requested",
        )
    await state.clear()
    await callback.message.answer(
        callback.bot.i18n.get_text(lang, "repeat_application.created").format(
            request_id=result.request_id,
            bitrix_deal_id=result.bitrix_deal_id,
            public_status=result.public_status,
        )
    )
    await callback.answer()

@router.callback_query(F.data.startswith("myapp:payment:"))
async def start_payment_for_application(callback: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(callback)
    deal_id = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    card = await _verified_card(callback, deal_id)
    if not card:
        await callback.answer()
        return
    await state.set_state(PaymentConfirmationForm.awaiting_file)
    await state.update_data(
        payment_files=[],
        request_id=f"pay-{callback.from_user.id}-{uuid4().hex[:8]}",
        deal_id=str(deal_id),
        license_plate=str((card.get("_raw_deal") or {}).get(LICENSE_PLATE_FIELD) or ""),
    )
    _service(callback.bot).log_action(
        callback.from_user.id, "payment_confirmation_started", int(deal_id)
    )
    await callback.message.answer(
        callback.bot.i18n.get_text(lang, "payment_confirmation.attach_prompt")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("myapp:policy:"))
async def send_policy_for_application(callback: CallbackQuery) -> None:
    lang = _lang(callback)
    deal_id = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    card = await _verified_card(callback, deal_id)
    if not card:
        await callback.answer()
        return
    deal = card.get("_raw_deal") or {}
    file_infos = _policy_file_infos(deal)
    if not file_infos:
        await _create_operator_ticket(callback, card, "policy_not_found")
        await callback.message.answer(callback.bot.i18n.get_text(lang, "my_applications.policy_not_found"))
        await callback.answer()
        return

    _service(callback.bot).log_action(callback.from_user.id, "policy_requested", int(deal_id))
    bitrix_client = getattr(callback.bot, "bitrix_client", None)
    if bitrix_client is None:
        await callback.message.answer(callback.bot.i18n.get_text(lang, "my_applications.unavailable"))
        await callback.answer()
        return
    with tempfile.TemporaryDirectory(prefix="policy_download_") as tmpdir:
        for file_info in file_infos:
            local_path = bitrix_client.download_deal_file(file_info, tmpdir)
            await callback.bot.send_document(callback.from_user.id, FSInputFile(local_path))
    await callback.answer()


@router.callback_query(F.data.startswith("myapp:operator:"))
async def operator_for_application(callback: CallbackQuery) -> None:
    lang = _lang(callback)
    deal_id = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    card = None
    if deal_id != "none":
        card = await _verified_card(callback, deal_id)
        if not card:
            await callback.answer()
            return
    else:
        card = {"deal_id": None, "product_type": "OC graniczne (border insurance)", "vehicle_plate_masked": "—", "public_status": "—"}
    await _create_operator_ticket(callback, card, "client_requested_operator")
    await callback.message.answer(callback.bot.i18n.get_text(lang, "operator.operator_connected"))
    await callback.answer()


async def _create_operator_ticket(callback: CallbackQuery, card: dict, reason: str) -> None:
    lang = _lang(callback)
    deal_id = card.get("deal_id")
    request_id = f"myapp-{callback.from_user.id}-{uuid4().hex[:8]}"
    OperatorTicketService().create_ticket(
        TicketPayload(
            request_id=request_id,
            telegram_user_id=callback.from_user.id,
            telegram_chat_id=callback.message.chat.id if callback.message else callback.from_user.id,
            bitrix_deal_id=deal_id,
            reason=reason,
            client_name=callback.from_user.full_name if callback.from_user else "",
            client_phone="",
            preferred_language=lang,
            vehicle_type=str(card.get("product_type") or "OC graniczne (border insurance)"),
            license_plate=str(card.get("vehicle_plate_masked") or ""),
            vin="",
            insurance_period_days=0,
            insurance_start_date=str(card.get("insurance_start_date") or ""),
            comment=f"{reason}; Bitrix deal {deal_id or '—'}",
            client_bot=getattr(callback.bot, "client_bot_code", "default"),
        )
    )
    _service(callback.bot).log_action(
        callback.from_user.id, "operator_requested", int(deal_id) if deal_id else None
    )
    OperatorNotifierService().notify_new_ticket(
        "🆘 Клиент запросил оператора по заявке\n\n"
        f"ID: {request_id}\n"
        f"Сделка: {deal_id or '—'}\n"
        f"Тип: {card.get('product_type') or 'OC graniczne (border insurance)'}\n"
        f"Авто: {card.get('vehicle_plate_masked') or '—'}\n"
        f"Статус: {card.get('public_status') or '—'}\n"
        f"{operator_language_line(lang)}",
        reply_command(request_id),
    )


def _policy_file_infos(deal: dict) -> list[dict]:
    value = deal.get(POLICY_FILES_FIELD)
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []
