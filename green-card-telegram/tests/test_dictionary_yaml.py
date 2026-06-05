from pathlib import Path

import pytest

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

pytestmark = pytest.mark.skipif(yaml is None, reason="PyYAML is not installed")

ROOT = Path(__file__).resolve().parents[1]
DICTIONARY_DIRS = (
    ROOT / "app" / "dictionaries",
    ROOT / "app" / "europolis_dictionaries",
)
REQUIRED_TOP_LEVEL_KEYS = {
    "main_menu",
    "menu",
    "language",
    "calculator",
    "application",
    "operator",
    "faq",
    "coverage",
    "latest_deal",
    "payment_confirmation",
    "my_applications",
}
REQUIRED_MAIN_MENU_KEYS = {
    "calculator",
    "faq",
    "coverage",
    "apply",
    "operator",
    "payment_confirmation",
    "latest_deal",
    "my_applications",
    "language",
}
REQUIRED_LANGUAGE_KEYS = {"select", "changed"}


def _dictionary_files():
    for dictionary_dir in DICTIONARY_DIRS:
        yield from sorted(dictionary_dir.glob("*.yaml"))


def test_dictionary_yaml_files_parse():
    for path in _dictionary_files():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), (
            f"{path.relative_to(ROOT)} must contain a mapping"
        )


def test_dictionary_yaml_files_have_required_client_bot_keys():
    for path in _dictionary_files():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        missing_top_level = REQUIRED_TOP_LEVEL_KEYS - set(data)
        assert not missing_top_level, (
            f"{path.relative_to(ROOT)} missing {missing_top_level}"
        )

        main_menu = data["main_menu"]
        missing_menu = REQUIRED_MAIN_MENU_KEYS - set(main_menu)
        assert not missing_menu, (
            f"{path.relative_to(ROOT)} main_menu missing {missing_menu}"
        )

        language = data["language"]
        missing_language = REQUIRED_LANGUAGE_KEYS - set(language)
        assert not missing_language, (
            f"{path.relative_to(ROOT)} language missing {missing_language}"
        )
