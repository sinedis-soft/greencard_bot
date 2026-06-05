import os
from pathlib import Path

from aiogram import Bot, Dispatcher

from app.bots.client_bot.handlers import apply, calculator, coverage, faq, language, my_applications, menu
from app.services.bitrix24_client import Bitrix24Client
from app.services.calculator_service import CalculatorService
from app.services.i18n_service import I18nService


async def run_client_bot(
    *,
    token_env: str = "BOT_TOKEN",
    dictionaries_dir: str = "dictionaries",
    client_bot_code: str = "default",
    default_language_env: str = "DEFAULT_LANGUAGE",
    mini_app_url_env: str = "MINI_APP_URL",
    bitrix_webhook_env: str = "BITRIX24_WEBHOOK_URL",
) -> None:
    token = os.getenv(token_env, "")
    default_language = os.getenv(default_language_env) or os.getenv("DEFAULT_LANGUAGE", "ru")
    mini_app_url = os.getenv(mini_app_url_env) or os.getenv("MINI_APP_URL", "")
    bitrix_webhook = os.getenv(bitrix_webhook_env) or os.getenv(
        "BITRIX24_WEBHOOK_URL", "https://example.bitrix24.com/rest"
    )

    bot = Bot(token=token)
    dp = Dispatcher()

    app_dir = Path(__file__).resolve().parents[2]
    i18n = I18nService(app_dir / dictionaries_dir)
    calculator_service = CalculatorService(app_dir / "config" / "tariffs.yaml")

    lang_store: dict[int, str] = {}
    bot.i18n = i18n
    bot.lang_store = lang_store
    bot.default_language = default_language
    bot.calculator_service = calculator_service
    bot.mini_app_url = mini_app_url
    bot.storage = {}
    bot.bitrix_client = Bitrix24Client(bitrix_webhook)
    bot.client_bot_code = client_bot_code

    dp["i18n"] = i18n
    dp["lang_store"] = lang_store
    dp["default_language"] = default_language
    dp["calculator_service"] = calculator_service
    dp["mini_app_url"] = mini_app_url

    dp.include_router(language.router)
    dp.include_router(calculator.router)
    dp.include_router(faq.router)
    dp.include_router(coverage.router)
    dp.include_router(apply.router)
    dp.include_router(my_applications.router)
    dp.include_router(menu.router)

    await dp.start_polling(bot)
