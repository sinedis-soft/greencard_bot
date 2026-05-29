from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def reply_instruction(request_id: str) -> str:
    return "Ответ клиенту: отправьте ваш текст после"


def reply_command(request_id: str) -> str:
    return f"/reply {request_id}"


def ticket_actions_keyboard(request_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="take", callback_data=f"take:{request_id}")
    b.button(text="reply", callback_data=f"reply_help:{request_id}")
    b.button(text="close", callback_data=f"close:{request_id}")
    return b.as_markup()
