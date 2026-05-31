def operator_language_line(preferred_language: str | None) -> str:
    language = (preferred_language or "").strip() or "не указан"
    return f"Язык клиента: {language}"
