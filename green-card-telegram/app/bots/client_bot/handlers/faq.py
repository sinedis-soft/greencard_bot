from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from uuid import uuid4

from app.services.i18n_service import I18nService
from app.services.operator_notifier_service import OperatorNotifierService
from app.services.operator_ticket_service import OperatorTicketService, TicketPayload

router = Router()
FAQ_CATEGORIES = ["documents", "payment", "coverage", "mistakes", "refund"]


def _faq_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=i18n.get_text(lang, f"faq.categories.{cat}"), callback_data=f"faq:{cat}")] for cat in FAQ_CATEGORIES]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == "/faq")
async def faq_command(message: Message, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    await message.answer(i18n.get_text(lang, "faq.title"), reply_markup=_faq_keyboard(i18n, lang))


async def show_faq_categories(message: Message) -> None:
    await faq_command(
    message,
    message.bot.i18n,
    message.bot.lang_store,
    message.bot.default_language,
)


@router.callback_query(F.data.startswith("faq:"))
async def faq_answer(callback: CallbackQuery, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    category = callback.data.split(":", maxsplit=1)[1]
    feedback = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👍", callback_data="faq_fb:up"), InlineKeyboardButton(text="👎", callback_data="faq_fb:down")]
        ]
    )
    await callback.message.answer(i18n.get_text(lang, f"faq.answers.{category}"), reply_markup=feedback)
    await callback.answer()


@router.callback_query(F.data == "faq_fb:down")
async def faq_feedback_down(callback: CallbackQuery, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(callback.from_user.id, default_language)
    request_id = f"faq-{callback.from_user.id}-{uuid4().hex[:8]}"
    client_name = callback.from_user.full_name if callback.from_user else ""
    OperatorTicketService().create_ticket(
        TicketPayload(
            request_id=request_id,
            telegram_user_id=callback.from_user.id if callback.from_user else None,
            client_name=client_name,
            client_phone="",
            preferred_language=lang,
            vehicle_type="",
            license_plate="",
            vin="",
            insurance_period_days=0,
            insurance_start_date="",
            comment="FAQ dislike: user requested operator assistance.",
        )
    )
    OperatorNotifierService().notify_new_ticket(
        f"🆘 Новый запрос оператора\nID: {request_id}\nКлиент: {client_name}\nИсточник: FAQ (dislike)"
    )
    await callback.message.answer(i18n.get_text(lang, "operator.operator_connected"))
    await callback.answer()


@router.callback_query(F.data == "faq_fb:up")
async def faq_feedback_up(callback: CallbackQuery) -> None:
    await callback.answer()
