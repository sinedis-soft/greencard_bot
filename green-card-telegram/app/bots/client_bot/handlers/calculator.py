from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bots.client_bot.keyboards.calculator import periods_keyboard, vehicle_types_keyboard
from app.services.calculator_service import CalculatorService
from app.services.i18n_service import I18nService

router = Router()


@router.message(F.text == "/calc")
async def calc_command(message: Message, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    await message.answer(i18n.get_text(lang, "calculator.select_vehicle_type"), reply_markup=vehicle_types_keyboard(i18n, lang))


async def start_calculator(message: Message) -> None:
    await calc_command(
    message,
    message.bot.i18n,
    message.bot.lang_store,
    message.bot.default_language,
)


@router.callback_query(F.data.startswith("calc:vehicle:"))
async def calc_choose_vehicle(callback: CallbackQuery, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    vehicle_type = callback.data.split(":")[-1]
    callback.bot.storage[f"vehicle:{callback.from_user.id}"] = vehicle_type
    lang = lang_store.get(callback.from_user.id, default_language)
    await callback.message.answer(i18n.get_text(lang, "calculator.select_period"), reply_markup=periods_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("calc:period:"))
async def calc_choose_period(
    callback: CallbackQuery,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
    calculator_service: CalculatorService,
) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    period = int(callback.data.split(":")[-1])
    vehicle_type = callback.bot.storage.get(f"vehicle:{callback.from_user.id}", "car")
    result = calculator_service.estimate(vehicle_type=vehicle_type, insurance_period_days=period)
    text = i18n.get_text(lang, "calculator.result_template").format(
        estimated_price=result["estimated_price"],
        currency=result["currency"],
        disclaimer=result["disclaimer"],
    )
    await callback.message.answer(text)
    await callback.message.answer(i18n.get_text(lang, "calculator.apply_cta"))
    await callback.answer()
