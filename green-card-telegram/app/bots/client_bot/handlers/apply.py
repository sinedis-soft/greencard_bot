from aiogram import F, Router
from aiogram.types import Message

from app.bots.client_bot.keyboards.apply import apply_webapp_keyboard
from app.services.i18n_service import I18nService

router = Router()


@router.message(F.text == "/apply")
async def apply_command(message: Message, i18n: I18nService, lang_store: dict[int, str], default_language: str) -> None:
    lang = lang_store.get(message.from_user.id, default_language)
    mini_app_url = message.bot.mini_app_url
    if not mini_app_url:
        await message.answer(i18n.get_text(lang, "application.temporarily_unavailable"))
        return

    await message.answer(
        i18n.get_text(lang, "application.mini_app_soon"),
        reply_markup=apply_webapp_keyboard(i18n.get_text(lang, "application.open_form_button"), mini_app_url),
    )


async def send_apply(message: Message) -> None:
    await apply_command(
    message,
    message.bot.i18n,
    message.bot.lang_store,
    message.bot.default_language,
)