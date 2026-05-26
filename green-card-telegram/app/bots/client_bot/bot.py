import asyncio
import os
from pathlib import Path

from aiogram import Bot, Dispatcher

from app.bots.client_bot.handlers import apply, calculator, coverage, faq, language, menu
from app.services.calculator_service import CalculatorService
from app.services.i18n_service import I18nService


async def main() -> None:
    token = os.getenv("BOT_TOKEN", "")
    default_language = os.getenv("DEFAULT_LANGUAGE", "ru")
    mini_app_url = os.getenv("MINI_APP_URL", "")

    bot = Bot(token=token)
    dp = Dispatcher()

    app_dir = Path(__file__).resolve().parents[2]
    i18n = I18nService(app_dir / "dictionaries")
    calculator_service = CalculatorService(app_dir / "config" / "tariffs.yaml")

    lang_store: dict[int, str] = {}
    bot.i18n = i18n
    bot.lang_store = lang_store
    bot.default_language = default_language
    bot.calculator_service = calculator_service
    bot.mini_app_url = mini_app_url
    bot.storage = {}

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
    dp.include_router(menu.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
