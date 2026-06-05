import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bots.client_bot.keyboards.calculator import (
    apply_cta_keyboard,
    periods_keyboard,
    vehicle_types_keyboard,
)
from app.services.calculator_service import CalculatorService
from app.services.i18n_service import I18nService

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == "/calc")
async def calc_command(
    message: Message,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    await message.answer(
        i18n.get_text(lang, "calculator.select_vehicle_type"),
        reply_markup=vehicle_types_keyboard(
            i18n, lang, getattr(message.bot, "calculator_vehicle_types", None)
        ),
    )


async def start_calculator(message: Message) -> None:
    await calc_command(
        message,
        message.bot.i18n,
        message.bot.lang_store,
        message.bot.default_language,
    )


@router.callback_query(F.data.startswith("calc:vehicle:"))
async def calc_choose_vehicle(
    callback: CallbackQuery,
    i18n: I18nService,
    lang_store: dict[int, str],
    default_language: str,
) -> None:
    vehicle_type = callback.data.split(":")[-1]
    callback.bot.storage[f"vehicle:{callback.from_user.id}"] = vehicle_type
    lang = lang_store.get(callback.from_user.id, default_language)
    await callback.message.answer(
        i18n.get_text(lang, "calculator.select_period"),
        reply_markup=periods_keyboard(i18n, lang),
    )
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
    result = calculator_service.estimate(
        vehicle_type=vehicle_type, insurance_period_days=period
    )
    if result["estimated_price"] is None:
        await callback.message.answer(
            i18n.get_text(lang, "calculator.price_unavailable")
        )
        await callback.answer()
        return

    estimated_price = result["estimated_price"]
    currency = result["currency"]
    if result.get("currency_symbol"):
        estimated_price = f"{result['currency_symbol']} {float(estimated_price):.2f}"
        currency = ""

    text = i18n.get_text(lang, "calculator.result_template").format(
        estimated_price=estimated_price,
        currency=currency,
        disclaimer=i18n.get_text(lang, "calculator.disclaimer"),
    )
    await callback.message.answer(text, reply_markup=apply_cta_keyboard(i18n, lang))
    from app.services.reminder_service import ReminderService

    try:
        ReminderService().create_calculator_followup(
            telegram_user_id=callback.from_user.id,
            telegram_chat_id=callback.message.chat.id,
            vehicle_type=vehicle_type,
            insurance_period_days=period,
            estimated_price=result.get("estimated_price"),
            currency=result.get("currency"),
            language=lang,
            client_bot=getattr(callback.bot, "client_bot_code", "default"),
            apply_button_text=i18n.get_text(lang, "calculator.apply_cta"),
        )
    except Exception as exc:
        logger.exception(
            "calculator_followup_reminder_failed user_id=%s error=%s",
            callback.from_user.id,
            exc,
        )
    await callback.answer()


@router.callback_query(F.data == "calc:apply")
async def calc_apply(callback: CallbackQuery, state: FSMContext) -> None:
    from app.bots.client_bot.handlers.apply import send_apply

    await send_apply(callback.message, state, user=callback.from_user)
    await callback.answer()
