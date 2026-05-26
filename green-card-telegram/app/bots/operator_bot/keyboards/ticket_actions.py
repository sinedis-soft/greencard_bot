from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def ticket_actions_keyboard(request_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="take", callback_data=f"take:{request_id}")
    b.button(text="close", callback_data=f"close:{request_id}")
    return b.as_markup()
