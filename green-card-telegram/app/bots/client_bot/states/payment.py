from aiogram.fsm.state import State, StatesGroup


class PaymentConfirmationForm(StatesGroup):
    awaiting_file = State()
    review_files = State()
