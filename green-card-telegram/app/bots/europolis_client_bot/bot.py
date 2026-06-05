import asyncio

from app.bots.client_bot.runtime import run_client_bot


async def main() -> None:
    await run_client_bot(
        token_env="EUROPOLIS_BOT_TOKEN",
        dictionaries_dir="europolis_dictionaries",
        client_bot_code="europolis",
        default_language_env="EUROPOLIS_DEFAULT_LANGUAGE",
        mini_app_url_env="EUROPOLIS_MINI_APP_URL",
        bitrix_webhook_env="EUROPOLIS_BITRIX24_WEBHOOK_URL",
    )


if __name__ == "__main__":
    asyncio.run(main())
