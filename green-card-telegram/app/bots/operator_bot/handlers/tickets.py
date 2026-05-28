from aiogram import F, Router
from aiogram.types import Message

from app.bots.operator_bot.handlers.start import _operator_ids
from app.bots.operator_bot.keyboards.ticket_actions import reply_instruction, ticket_actions_keyboard
from app.db.models import Application
from app.db.session import SessionLocal
from app.services.operator_ticket_service import OperatorTicketService

router = Router()


@router.message(F.text == "/tickets")
async def tickets(message: Message) -> None:
    if message.from_user.id not in _operator_ids():
        await message.answer(message.bot["i18n"].get_text("en", "operator.access_denied"))
        return
    items = OperatorTicketService().list_new()
    if not items:
        await message.answer(message.bot["i18n"].get_text("en", "operator.no_tickets"))
        return
    for t in items:
        crm_status = "pending"
        with SessionLocal() as db:
            app = db.query(Application).filter(Application.request_id == t.request_id).first()
            if app and app.status == "bitrix_created":
                crm_status = "created"
            elif app and app.status == "failed":
                crm_status = "failed"
        sla = "SLA breached" if t.sla_breach else "SLA ok"
        await message.answer(
            f"ID: {t.request_id}\nCRM status: {crm_status}\n{sla}\n{reply_instruction(t.request_id)}",
            reply_markup=ticket_actions_keyboard(t.request_id),
        )
