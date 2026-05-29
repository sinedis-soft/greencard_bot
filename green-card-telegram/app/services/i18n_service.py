from pathlib import Path
from typing import Any

import yaml


class I18nService:
    def __init__(self, dictionaries_path: Path):
        self._path = dictionaries_path
        self._cache: dict[str, dict[str, Any]] = {}

    def available_languages(self) -> tuple[str, ...]:
        return tuple(
            sorted(path.stem for path in self._path.glob("*.yaml") if path.is_file())
        )

    def get_text(self, lang: str, key: str, fallback_lang: str = "en") -> str:
        data = self._load(lang) or self._load(fallback_lang)
        current: Any = data
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return key
            current = current[part]
        return str(current)

    def _load(self, lang: str) -> dict[str, Any]:
        if lang in self._cache:
            return self._cache[lang]
        fpath = self._path / f"{lang}.yaml"
        if not fpath.exists():
            self._cache[lang] = {}
        else:
            self._cache[lang] = yaml.safe_load(fpath.read_text(encoding="utf-8")) or {}
        return self._cache[lang]
