from aiogram import F, Router
from aiogram.types import Message

from app.bots.operator_bot.keyboards.ticket_actions import ticket_actions_keyboard
from app.services.operator_ticket_service import OperatorTicketService
from app.db.session import SessionLocal
from app.db.models import Application

router = Router()


@router.message(F.text == "/tickets")
async def tickets(message: Message) -> None:
    ids = message.bot.get("operator_ids", set())
    if message.from_user.id not in ids:
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
        await message.answer(f"{t.request_id} | CRM status: {crm_status} | {sla}", reply_markup=ticket_actions_keyboard(t.request_id))
