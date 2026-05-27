from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from uuid import uuid4

from app.bots.client_bot.handlers.apply import send_apply
from app.bots.client_bot.handlers.calculator import start_calculator
from app.bots.client_bot.handlers.coverage import send_coverage
from app.bots.client_bot.handlers.faq import show_faq_categories
from app.services.operator_notifier_service import OperatorNotifierService
from app.services.operator_ticket_service import OperatorTicketService, TicketPayload

router = Router()


@router.message(F.text)
async def menu_click_router(message: Message, state: FSMContext) -> None:
    text = message.text.lower()
    if "калькуля" in text or "calculator" in text:
        await start_calculator(message)
    elif "faq" in text:
        await show_faq_categories(message)
    elif "coverage" in text or "покрыт" in text:
        await send_coverage(message)
    elif "оформ" in text or "apply" in text:
        await send_apply(message, state)
    elif "оператор" in text or "operator" in text:
        request_id = f"op-{message.from_user.id}-{uuid4().hex[:8]}"
        client_name = message.from_user.full_name if message.from_user else ""
        OperatorTicketService().create_ticket(
            TicketPayload(
                request_id=request_id,
                telegram_user_id=message.from_user.id if message.from_user else None,
                client_name=client_name,
                client_phone="",
                preferred_language=message.bot.lang_store.get(message.from_user.id, message.bot.default_language),
                vehicle_type="",
                license_plate="",
                vin="",
                insurance_period_days=0,
                insurance_start_date="",
                comment="Main menu: user requested operator assistance.",
            )
        )
        OperatorNotifierService().notify_new_ticket(
            f"🆘 Новый запрос оператора\nID: {request_id}\nКлиент: {client_name}\nИсточник: Главное меню"
        )
        await message.answer(message.bot.i18n.get_text(message.bot.lang_store.get(message.from_user.id, message.bot.default_language), "operator.operator_connected"))
