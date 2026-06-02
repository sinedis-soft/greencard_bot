from app.services.operator_message_formatter import operator_language_line


def test_operator_language_line_includes_language_code():
    assert operator_language_line("ka") == "Язык клиента: ka"


def test_operator_language_line_falls_back_when_missing():
    assert operator_language_line("") == "Язык клиента: не указан"
    assert operator_language_line(None) == "Язык клиента: не указан"
