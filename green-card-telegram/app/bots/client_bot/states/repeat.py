from aiogram.fsm.state import State, StatesGroup


class RepeatApplicationForm(StatesGroup):
    waiting_start_date = State()
    waiting_period = State()
    waiting_docs_mode = State()
    waiting_confirmation = State()
