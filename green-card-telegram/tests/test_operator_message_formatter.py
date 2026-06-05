from app.services.operator_message_formatter import (
    operator_client_bot_line,
    operator_language_line,
)


def test_operator_language_line_includes_language_code():
    assert operator_language_line("ka") == "Язык клиента: ka"


def test_operator_language_line_falls_back_when_missing():
    assert operator_language_line("") == "Язык клиента: не указан"
    assert operator_language_line(None) == "Язык клиента: не указан"


def test_operator_client_bot_line_formats_known_bots():
    assert operator_client_bot_line("default") == "Бот клиента: GreenCard .agency"
    assert operator_client_bot_line("europolis") == "Бот клиента: EuroPolis"


def test_operator_client_bot_line_falls_back_to_default_or_code():
    assert operator_client_bot_line("") == "Бот клиента: GreenCard .agency"
    assert operator_client_bot_line(None) == "Бот клиента: GreenCard .agency"
    assert operator_client_bot_line("custom_bot") == "Бот клиента: custom_bot"
