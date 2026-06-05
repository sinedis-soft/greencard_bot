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
    "latest_deal": ("main_menu.latest_deal",),
    "my_applications": ("main_menu.my_applications",),
    "payment_confirmation": ("main_menu.payment_confirmation",),
    "language": ("main_menu.language",),
}

COMMAND_ACTIONS = {
    "/calc": "calculator",
    "/faq": "faq",
    "/coverage": "coverage",
    "/apply": "apply",
    "/operator": "operator",
    "/latest": "latest_deal",
    "/last": "latest_deal",
    "/my": "my_applications",
    "/applications": "my_applications",
    "/orders": "my_applications",
    "/payment": "payment_confirmation",
    "/paid": "payment_confirmation",
    "/language": "language",
    "/lang": "language",
}

MENU_ACTION_ALIASES = {
    "calculator": ("калькулятор", "калькулятар", "calculator"),
    "faq": ("faq",),
    "coverage": (
        "где работает?",
        "дзе дзейнічае?",
        "where does it work?",
    ),
    "apply": (
        "оформить заявку",
        "аформіць заяўку",
        "аформіць",
        "submit an application",
    ),
    "operator": (
        "связаться с оператором",
        "звязацца з аператарам",
        "contact an operator",
    ),
    "latest_deal": (
        "моя последняя заявка",
        "мая апошняя заяўка",
        "my latest application",
    ),
    "my_applications": ("мои заявки", "мае заяўкі", "my applications"),
    "payment_confirmation": (
        "подтверждение оплаты",
        "пацвярджэнне аплаты",
        "payment confirmation",
    ),
    "language": ("язык", "мова", "language"),
}

_EMOJI_PREFIX_CHARS = frozenset(
    "🧮❓🌍📝📄💳👨💼🌐👩‍️☘️✅🔘▫️▪️• "
)
_VARIATION_CHARS = "\ufe0e\ufe0f\u200d"


def _without_emoji_variation(text: str) -> str:
    return "".join(char for char in text if char not in _VARIATION_CHARS)


def _without_leading_icon(text: str) -> str:
    return text.lstrip("".join(_EMOJI_PREFIX_CHARS)).strip()


def _normalized(text: str) -> str:
    return " ".join(_without_emoji_variation(text).casefold().split())


def _normalized_variants(text: str) -> tuple[str, ...]:
    normalized = _normalized(text)
    without_icon = _normalized(_without_leading_icon(text))
    return tuple(dict.fromkeys(value for value in (normalized, without_icon) if value))


def _languages_to_check(
    i18n: MenuI18n, lang: str, default_language: str
) -> tuple[str, ...]:
    ordered = [lang, default_language, "ru", "en"]
    ordered.extend(i18n.available_languages())
    return tuple(dict.fromkeys(language for language in ordered if language))


def menu_action_for_text(
    i18n: MenuI18n, text: str, lang: str, default_language: str
) -> str | None:
    normalized_texts = _normalized_variants(text)
    if not normalized_texts:
        return None
    if normalized_texts[0] in COMMAND_ACTIONS:
        return COMMAND_ACTIONS[normalized_texts[0]]

    languages = _languages_to_check(i18n, lang, default_language)
    for action, keys in MENU_ACTION_TEXT_KEYS.items():
        for language in languages:
            for key in keys:
                localized_variants = _normalized_variants(i18n.get_text(language, key))
                if any(
                    normalized_text == localized_text
                    for normalized_text in normalized_texts
                    for localized_text in localized_variants
                ):
                    return action

    for action, aliases in MENU_ACTION_ALIASES.items():
        if any(
            normalized_text == _normalized(alias)
            for normalized_text in normalized_texts
            for alias in aliases
        ):
            return action
    return None
