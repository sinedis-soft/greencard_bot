from aiogram import F, Router
from aiogram.types import Message

from app.bots.client_bot.handlers.apply import send_apply
from app.bots.client_bot.handlers.calculator import start_calculator
from app.bots.client_bot.handlers.coverage import send_coverage
from app.bots.client_bot.handlers.faq import show_faq_categories

router = Router()


@router.message(F.text)
async def menu_click_router(message: Message) -> None:
    text = message.text.lower()
    if "калькуля" in text or "calculator" in text:
        await start_calculator(message)
    elif "faq" in text:
        await show_faq_categories(message)
    elif "coverage" in text or "покрыт" in text:
        await send_coverage(message)
    elif "оформ" in text or "apply" in text:
        await send_apply(message)
