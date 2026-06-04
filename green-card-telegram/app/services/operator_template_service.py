from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from app.core.config import app_root
from app.services.content_text_service import ContentTextService


@dataclass(frozen=True)
class OperatorTemplate:
    key: str
    title: str
    text: dict[str, str]
    next_status: str
    expected_client_action: str = "none"


class InternalCommentTemplateService:
    def __init__(self, path: Path | None = None):
        self.path = path or (app_root() / "operator_templates" / "templates.yaml")
        self._templates = self._load()

    def list_templates(self) -> list[dict]:
        return list(self._templates.values())

    def get(self, key: str) -> dict | None:
        return self._templates.get(key)

    def _load(self) -> dict[str, dict]:
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        raw_templates = data.get("internal_comment_templates") or {}
        return {
            key: {
                "key": key,
                "title": str(value.get("title") or key),
                "text": str(value.get("text") or ""),
                "type": str(value.get("type") or "general"),
                "pinned": bool(value.get("pinned", False)),
            }
            for key, value in raw_templates.items()
        }


class OperatorTemplateService:
    def __init__(self, path: Path | None = None):
        self.path = path or (app_root() / "operator_templates" / "templates.yaml")
        self._templates = self._load()

    def list_templates(self) -> list[OperatorTemplate]:
        return list(self._templates.values())

    def get(self, key: str) -> OperatorTemplate | None:
        return self._templates.get(key)

    def render(self, key: str, lang: str, **context) -> tuple[OperatorTemplate, str]:
        template = self._templates[key]
        text = ContentTextService().get(f"operator_template.{key}", lang)
        if text is None:
            text = template.text.get(lang) or template.text.get("ru") or template.text.get("en") or ""
        return template, text.format(**context)

    def _load(self) -> dict[str, OperatorTemplate]:
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        raw_templates = data.get("operator_templates") or {}
        return {
            key: OperatorTemplate(
                key=key,
                title=str(value.get("title") or key),
                text=dict(value.get("text") or {}),
                next_status=str(value.get("next_status") or "in_progress"),
                expected_client_action=str(value.get("expected_client_action") or "none"),
            )
            for key, value in raw_templates.items()
        }
