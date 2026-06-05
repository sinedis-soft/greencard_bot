CLIENT_BOT_TITLES = {
    "default": "GreenCard .agency",
    "europolis": "EuroPolis",
}


def operator_language_line(preferred_language: str | None) -> str:
    language = (preferred_language or "").strip() or "не указан"
    return f"Язык клиента: {language}"


def operator_client_bot_line(client_bot: str | None) -> str:
    bot_code = (client_bot or "").strip() or "default"
    bot_title = CLIENT_BOT_TITLES.get(bot_code, bot_code)
    return f"Бот клиента: {bot_title}"
