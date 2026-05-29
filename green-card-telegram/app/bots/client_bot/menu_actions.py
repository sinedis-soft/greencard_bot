from typing import Protocol


class MenuI18n(Protocol):
    def available_languages(self) -> tuple[str, ...]: ...

    def get_text(self, lang: str, key: str, fallback_lang: str = "en") -> str: ...


MENU_ACTION_TEXT_KEYS = {
    "calculator": ("main_menu.calculator",),
    "faq": ("main_menu.faq",),
    "coverage": ("main_menu.coverage",),
    "apply": ("main_menu.apply", "calculator.apply_cta"),
    "operator": ("main_menu.operator",),
    "language": ("main_menu.language",),
}

COMMAND_ACTIONS = {
    "/calc": "calculator",
    "/faq": "faq",
    "/coverage": "coverage",
    "/apply": "apply",
    "/operator": "operator",
    "/language": "language",
    "/lang": "language",
}


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _languages_to_check(
    i18n: MenuI18n, lang: str, default_language: str
) -> tuple[str, ...]:
    ordered = [lang, default_language, "ru", "en"]
    ordered.extend(i18n.available_languages())
    return tuple(dict.fromkeys(language for language in ordered if language))


def menu_action_for_text(
    i18n: MenuI18n, text: str, lang: str, default_language: str
) -> str | None:
    normalized_text = _normalized(text)
    if normalized_text in COMMAND_ACTIONS:
        return COMMAND_ACTIONS[normalized_text]

    languages = _languages_to_check(i18n, lang, default_language)
    for action, keys in MENU_ACTION_TEXT_KEYS.items():
        for language in languages:
            for key in keys:
                if normalized_text == _normalized(i18n.get_text(language, key)):
                    return action
    return None
