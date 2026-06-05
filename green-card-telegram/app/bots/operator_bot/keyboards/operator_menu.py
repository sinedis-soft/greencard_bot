from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def operator_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/help"), KeyboardButton(text="📋 Очередь")],
        ],
        resize_keyboard=True,
    )
