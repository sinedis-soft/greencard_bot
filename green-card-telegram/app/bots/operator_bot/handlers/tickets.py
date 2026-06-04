from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bots.operator_bot.handlers.start import _operator_ids
from app.services.operator_service import OperatorService
from app.bots.operator_bot.keyboards.ticket_actions import (
    reply_command,
    reply_instruction,
    ticket_actions_keyboard,
    ticket_close_keyboard,
    ticket_list_item_keyboard,
    ticket_queue_keyboard,
    quick_comment_keyboard,
    ticket_template_preview_keyboard,
    ticket_templates_keyboard,
    ticket_transfer_operator_keyboard,
    ticket_transfer_reason_keyboard,
)
from app.db.models import OperatorTicket
from app.services.bitrix_deal_summary_service import BitrixDealSummaryService
from app.services.client_bot_notifier import notify_client_operator_connected
from app.services.operator_notifier_service import ClientNotifierService, OperatorNotifierService
from app.services.operator_template_service import InternalCommentTemplateService, OperatorTemplateService
from app.services.operator_ticket_service import (
    TICKET_REASON_TITLES,
    TICKET_STATUS_TITLES,
    OperatorTicketService,
)

router = Router()


class TicketCommentForm(StatesGroup):
    waiting_comment = State()


TRANSFER_REASON_TITLES = {
    "shift_end": "Конец смены",
    "overload": "Перегрузка",
    "client_language": "Язык клиента",
    "senior_needed": "Нужен старший оператор",
    "absence": "Отпуск/отсутствие",
    "other": "Другая причина",
}

FILTER_TITLES = {
    "new": "Новые тикеты",
    "mine": "Мои тикеты в работе",
    "waiting_operator": "Клиент ждёт ответа",
    "sla": "Просроченные SLA",
    "bitrix_errors": "Ошибки Bitrix",
    "waiting_client": "Ожидают клиента",
}


def _allowed(message: Message | CallbackQuery) -> bool:
    return bool(message.from_user and message.from_user.id in _operator_ids())


def _privileged_operator_ids() -> set[int]:
    return OperatorService().privileged_operator_ids()


def _operator_list() -> list[int]:
    return sorted(_operator_ids())


def _deny_text(message: Message | CallbackQuery) -> str:
    return message.bot["i18n"].get_text("en", "operator.access_denied")


@router.message(F.text.in_({"/tickets", "📋 Очередь"}))
async def tickets(message: Message) -> None:
    if not _allowed(message):
        await message.answer(_deny_text(message))
        return
    counts = OperatorTicketService().queue_counts(message.from_user.id)
    await message.answer(
        "📋 Очередь заявок\n\n"
        f"Новые: {counts['new']}\n"
        f"В работе у меня: {counts['mine']}\n"
        f"Клиент ждёт ответа: {counts['waiting_operator']}\n"
        f"Просроченные SLA: {counts['sla']}\n"
        f"Ошибки Bitrix: {counts['bitrix_errors']}\n"
        f"Ожидают клиента: {counts['waiting_client']}",
        reply_markup=ticket_queue_keyboard(),
    )


@router.callback_query(F.data.startswith("tq:list:"))
async def ticket_list_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    filter_type = (callback.data or "").rsplit(":", maxsplit=1)[-1]
    await _send_ticket_list(callback.message, filter_type, callback.from_user.id)
    await callback.answer()


async def _send_ticket_list(message: Message, filter_type: str, operator_id: int) -> None:
    svc = OperatorTicketService()
    items = svc.list_tickets(filter_type, operator_id=operator_id, limit=10)
    await message.answer(FILTER_TITLES.get(filter_type, "Тикеты"))
    if not items:
        await message.answer("В этой категории тикетов нет.")
        return
    summary_service = BitrixDealSummaryService()
    for index, ticket in enumerate(items, start=1):
        bitrix_url = summary_service.deal_url(ticket.bitrix_deal_id)
        await message.answer(
            _ticket_list_text(ticket, index),
            reply_markup=ticket_list_item_keyboard(ticket.request_id, bitrix_url),
        )


@router.callback_query(F.data.startswith("tq:open:"))
async def ticket_open_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    request_id = (callback.data or "").split(":", maxsplit=2)[2]
    await _send_ticket_card(callback.message, request_id)
    await callback.answer()


async def _send_ticket_card(message: Message, request_id: str) -> None:
    svc = OperatorTicketService()
    ticket = svc.get_ticket(request_id)
    if not ticket:
        await message.answer("Тикет не найден.")
        return
    summary_service = BitrixDealSummaryService()
    summary = summary_service.get_safe_summary(ticket.bitrix_deal_id)
    comments = svc.list_internal_comments(ticket.request_id, limit=3)
    bitrix_url = summary_service.deal_url(ticket.bitrix_deal_id)
    await message.answer(
        _ticket_card_text(ticket, summary, comments),
        reply_markup=ticket_actions_keyboard(ticket.request_id, bitrix_url),
    )
    await message.answer(reply_command(ticket.request_id))


@router.callback_query(F.data.startswith("tq:take:"))
async def ticket_take_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    request_id = (callback.data or "").split(":", maxsplit=2)[2]
    svc = OperatorTicketService()
    ok, reason = svc.take_ticket(request_id, callback.from_user.id)
    if not ok and reason == "already_assigned":
        await callback.message.answer("Тикет уже в работе у другого оператора.")
        await callback.answer()
        return
    if not ok:
        await callback.message.answer("Тикет не найден.")
        await callback.answer()
        return
    svc.log_action(request_id, callback.from_user.id, "ticket_taken")
    notify_client_operator_connected(request_id)
    OperatorNotifierService().notify_operator_reply_sent(
        f"Тикет {request_id} взят оператором {callback.from_user.id}.",
        exclude_operator_id=callback.from_user.id,
    )
    await callback.message.answer(f"Тикет взят в работу.\n{reply_instruction(request_id)}")
    await callback.answer()


@router.callback_query(F.data.startswith("tq:reply:"))
async def ticket_reply_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    request_id = (callback.data or "").split(":", maxsplit=2)[2]
    await callback.message.answer(reply_instruction(request_id))
    await callback.message.answer(reply_command(request_id))
    await callback.answer()


@router.callback_query(F.data.startswith("tq:templates:"))
async def ticket_templates_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    request_id = (callback.data or "").split(":", maxsplit=2)[2]
    templates = OperatorTemplateService().list_templates()
    await callback.message.answer(
        "Выберите шаблон:",
        reply_markup=ticket_templates_keyboard(request_id, templates),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tq:tpl:"))
async def ticket_template_preview_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    _, _, request_id, template_key = (callback.data or "").split(":", maxsplit=3)
    ticket = OperatorTicketService().get_ticket(request_id)
    if not ticket:
        await callback.message.answer("Тикет не найден.")
        await callback.answer()
        return
    template, text = OperatorTemplateService().render(
        template_key,
        ticket.preferred_language or "ru",
        request_id=ticket.request_id,
    )
    await callback.message.answer(
        f"Будет отправлено клиенту:\n\n{text}\n\nШаблон: {template.title}",
        reply_markup=ticket_template_preview_keyboard(request_id, template_key),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tq:tplsend:"))
async def ticket_template_send_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    _, _, request_id, template_key = (callback.data or "").split(":", maxsplit=3)
    svc = OperatorTicketService()
    ticket = svc.get_ticket(request_id)
    if not ticket or not ticket.telegram_user_id:
        await callback.message.answer("Тикет не найден или нет Telegram ID клиента.")
        await callback.answer()
        return
    template, text = OperatorTemplateService().render(
        template_key,
        ticket.preferred_language or "ru",
        request_id=ticket.request_id,
    )
    assigned = svc.assign_operator_if_empty(request_id, callback.from_user.id)
    if assigned and assigned != callback.from_user.id:
        await callback.message.answer(f"Тикет уже назначен оператору {assigned}.")
        await callback.answer()
        return
    ClientNotifierService().send_to_client(ticket.telegram_user_id, text)
    svc.set_status(request_id, template.next_status)
    svc.log_action(
        request_id,
        callback.from_user.id,
        "template_sent",
        text,
        {"template_key": template_key, "template_modified": False},
    )
    await callback.message.answer("Шаблон отправлен клиенту.")
    await callback.answer()


@router.callback_query(F.data.startswith("tq:doc:"))
async def ticket_doc_request_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    request_id = (callback.data or "").split(":", maxsplit=2)[2]
    await callback.message.answer(
        "Какой документ запросить?",
        reply_markup=ticket_templates_keyboard(
            request_id,
            [t for t in OperatorTemplateService().list_templates() if t.expected_client_action == "upload_document"],
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tq:pay:"))
async def ticket_payment_request_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    request_id = (callback.data or "").split(":", maxsplit=2)[2]
    await _send_template_direct(callback, request_id, "waiting_payment", action="payment_requested")


async def _send_template_direct(callback: CallbackQuery, request_id: str, template_key: str, action: str) -> None:
    svc = OperatorTicketService()
    ticket = svc.get_ticket(request_id)
    if not ticket or not ticket.telegram_user_id:
        await callback.message.answer("Тикет не найден или нет Telegram ID клиента.")
        await callback.answer()
        return
    template, text = OperatorTemplateService().render(
        template_key,
        ticket.preferred_language or "ru",
        request_id=ticket.request_id,
    )
    ClientNotifierService().send_to_client(ticket.telegram_user_id, text)
    svc.set_status(request_id, template.next_status)
    svc.log_action(request_id, callback.from_user.id, action, text, {"template_key": template_key})
    await callback.message.answer("Запрос отправлен клиенту.")
    await callback.answer()


@router.callback_query(F.data.startswith("tq:transfer:"))
async def ticket_transfer_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    request_id = (callback.data or "").split(":", maxsplit=2)[2]
    ticket = OperatorTicketService().get_ticket(request_id)
    if not ticket:
        await callback.message.answer("Тикет не найден.")
        await callback.answer()
        return
    if not OperatorTicketService().can_transfer_ticket(
        request_id, callback.from_user.id, _privileged_operator_ids()
    ):
        await callback.message.answer("Вы можете передавать только свои тикеты.")
        await callback.answer()
        return
    await callback.message.answer(
        "Кому передать тикет?",
        reply_markup=ticket_transfer_operator_keyboard(
            request_id, _operator_list(), ticket.operator_id
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tq:trto:"))
async def ticket_transfer_to_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    _, _, request_id, raw_to_operator = (callback.data or "").split(":", maxsplit=3)
    await callback.message.answer(
        "Укажите причину передачи:",
        reply_markup=ticket_transfer_reason_keyboard(request_id, raw_to_operator),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tq:trwhy:"))
async def ticket_transfer_reason_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    _, _, request_id, raw_to_operator, reason_key = (callback.data or "").split(":", maxsplit=4)
    to_operator_id = None if raw_to_operator == "free" else int(raw_to_operator)
    reason = TRANSFER_REASON_TITLES.get(reason_key, reason_key)
    svc = OperatorTicketService()
    ok, error, ticket = svc.transfer_ticket(
        request_id,
        from_operator_id=callback.from_user.id,
        to_operator_id=to_operator_id,
        reason=reason,
        privileged_operator_ids=_privileged_operator_ids(),
    )
    if not ok:
        await callback.message.answer("Не удалось передать тикет: " + error)
        await callback.answer()
        return
    if to_operator_id:
        pinned = svc.pinned_internal_comments(request_id)
        OperatorNotifierService().notify_operator_direct(
            to_operator_id,
            _transfer_notification(ticket, reason, pinned),
        )
        await callback.message.answer(f"Тикет {request_id} передан оператору {to_operator_id}.")
    else:
        await callback.message.answer(f"Тикет {request_id} снят с ответственного оператора.")
    await callback.answer()


@router.callback_query(F.data.startswith("tq:comment:"))
async def ticket_comment_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    request_id = (callback.data or "").split(":", maxsplit=2)[2]
    await callback.message.answer(
        "Добавьте внутренний комментарий. Клиент его не увидит.",
        reply_markup=quick_comment_keyboard(
            request_id, InternalCommentTemplateService().list_templates()
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tq:cquick:"))
async def ticket_quick_comment_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    _, _, request_id, template_key = (callback.data or "").split(":", maxsplit=3)
    template = InternalCommentTemplateService().get(template_key)
    if not template:
        await callback.message.answer("Шаблон комментария не найден.")
        await callback.answer()
        return
    comment = OperatorTicketService().add_internal_comment(
        request_id,
        callback.from_user.id,
        template["text"],
        comment_type=template["type"],
        is_pinned=template["pinned"],
    )
    await callback.message.answer("Комментарий добавлен." if comment else "Не удалось добавить комментарий.")
    await callback.answer()


@router.callback_query(F.data.startswith("tq:cadd:"))
async def ticket_comment_add_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    request_id = (callback.data or "").split(":", maxsplit=2)[2]
    await state.set_state(TicketCommentForm.waiting_comment)
    await state.update_data(comment_ticket_id=request_id)
    await callback.message.answer("Введите внутренний комментарий. Он не будет отправлен клиенту.")
    await callback.answer()


@router.message(TicketCommentForm.waiting_comment, F.text)
async def ticket_comment_text(message: Message, state: FSMContext) -> None:
    if not _allowed(message):
        await message.answer(_deny_text(message))
        return
    data = await state.get_data()
    request_id = str(data.get("comment_ticket_id") or "")
    comment = OperatorTicketService().add_internal_comment(
        request_id, message.from_user.id, message.text, comment_type="general", is_pinned=False
    )
    await state.clear()
    await message.answer("Комментарий добавлен." if comment else "Не удалось добавить комментарий.")


@router.callback_query(F.data.startswith("tq:comments:"))
async def ticket_comments_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    request_id = (callback.data or "").split(":", maxsplit=2)[2]
    comments = OperatorTicketService().list_internal_comments(request_id, limit=20)
    await callback.message.answer(_comments_text(comments))
    await callback.answer()


@router.callback_query(F.data.startswith("tq:close:"))
async def ticket_close_callback(callback: CallbackQuery) -> None:
    if not _allowed(callback):
        await callback.answer(_deny_text(callback), show_alert=True)
        return
    parts = (callback.data or "").split(":", maxsplit=3)
    request_id = parts[2]
    if len(parts) == 3:
        await callback.message.answer("Причина закрытия:", reply_markup=ticket_close_keyboard(request_id))
        await callback.answer()
        return
    close_reason = parts[3]
    svc = OperatorTicketService()
    if svc.close_ticket(request_id, callback.from_user.id, close_reason=close_reason):
        svc.log_action(request_id, callback.from_user.id, "ticket_closed", details={"close_reason": close_reason})
        await callback.message.answer("Тикет закрыт.")
    else:
        await callback.message.answer("Не удалось закрыть тикет.")
    await callback.answer()


def _ticket_list_text(ticket: OperatorTicket, index: int) -> str:
    return (
        f"{index}. {ticket.request_id}\n"
        f"Причина: {TICKET_REASON_TITLES.get(ticket.reason or '', ticket.reason or '—')}\n"
        f"Заявка: {ticket.request_id}\n"
        f"Сделка Bitrix: {ticket.bitrix_deal_id or '—'}\n"
        f"Приоритет: {ticket.priority}\n"
        f"Создан: {_age(ticket.created_at)}\n"
        f"SLA: {_sla_text(ticket)}"
    )


def _ticket_card_text(ticket: OperatorTicket, summary: dict, comments: list = None) -> str:
    comments_text = _comments_preview(comments or [])
    return (
        f"{ticket.request_id}\n\n"
        f"Причина: {TICKET_REASON_TITLES.get(ticket.reason or '', ticket.reason or '—')}\n"
        f"Статус: {TICKET_STATUS_TITLES.get(ticket.status, ticket.status)}\n"
        f"Оператор: {ticket.operator_id or 'свободный'}\n"
        f"Приоритет: {ticket.priority}\n"
        f"SLA: {_sla_text(ticket)}\n\n"
        f"Заявка: {summary.get('request_number') or ticket.request_id}\n"
        f"Сделка Bitrix: {ticket.bitrix_deal_id or '—'}\n"
        f"Продукт: {summary.get('product_type') or 'Green Card'}\n"
        f"Авто: {summary.get('vehicle_plate_masked') or '—'}\n"
        f"Дата начала: {summary.get('insurance_start_date') or '—'}\n"
        f"Статус: {summary.get('public_status') or '—'}\n\n"
        f"Внутренние комментарии:\n{comments_text}\n\n"
        f"Последнее сообщение клиента:\n{ticket.last_message_preview or '—'}"
    )


def _age(value: datetime | None) -> str:
    if not value:
        return "—"
    minutes = max(0, int((datetime.utcnow() - value).total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} мин назад"
    return f"{minutes // 60} ч {minutes % 60} мин назад"


def _sla_text(ticket: OperatorTicket) -> str:
    if ticket.status == "waiting_client":
        return "ждём клиента"
    if ticket.sla_breach:
        return "просрочен"
    if not ticket.sla_due_at:
        return "ok"
    minutes = int((ticket.sla_due_at - datetime.utcnow()).total_seconds() // 60)
    if minutes < 0:
        return f"просрочен на {abs(minutes)} мин"
    return f"осталось {minutes} мин"

def _comments_preview(comments: list) -> str:
    if not comments:
        return "—"
    lines = []
    for index, comment in enumerate(comments[:3], start=1):
        prefix = "⚠️ " if comment.is_pinned else ""
        lines.append(f"{index}. {prefix}{comment.comment_text}")
    return "\n".join(lines)


def _comments_text(comments: list) -> str:
    if not comments:
        return "Внутренних комментариев пока нет."
    lines = ["Внутренние комментарии:"]
    for index, comment in enumerate(comments, start=1):
        prefix = "⚠️ " if comment.is_pinned else ""
        lines.append(f"{index}. {prefix}{comment.comment_text} ({comment.comment_type})")
    return "\n".join(lines)


def _transfer_notification(ticket: OperatorTicket | None, reason: str, pinned_comments: list) -> str:
    request_id = ticket.request_id if ticket else "—"
    comments = _comments_preview(pinned_comments)
    return (
        f"Вам передан тикет {request_id}.\n\n"
        f"Причина передачи: {reason}\n"
        f"Статус: {TICKET_STATUS_TITLES.get(ticket.status, ticket.status) if ticket else '—'}\n\n"
        f"Важные комментарии:\n{comments}\n\n"
        f"Открыть тикет: /tickets"
    )
