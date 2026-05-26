import asyncio
import os
from pathlib import Path

from aiogram import Bot, Dispatcher

from app.bots.operator_bot.handlers import replies, start, status, tickets
from app.services.i18n_service import I18nService


async def main() -> None:
    token = os.getenv("OPERATOR_BOT_TOKEN", "")
    operator_ids = {int(x.strip()) for x in os.getenv("OPERATOR_IDS", "").split(",") if x.strip()}

    bot = Bot(token=token)
    dp = Dispatcher()
    i18n = I18nService(Path(__file__).resolve().parents[2] / "dictionaries")

    dp["operator_ids"] = operator_ids
    dp["i18n"] = i18n

    dp.include_router(start.router)
    dp.include_router(tickets.router)
    dp.include_router(status.router)
    dp.include_router(replies.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
