import asyncio

from app.bots.client_bot.runtime import run_client_bot


async def main() -> None:
    await run_client_bot(client_bot_code="default")


if __name__ == "__main__":
    asyncio.run(main())
