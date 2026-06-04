from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.db.models import NotificationRule, NotificationTemplate
from app.db.session import SessionLocal


def _template_to_dict(item: NotificationTemplate) -> dict:
    return {
        "id": item.id,
        "event_key": item.event_key,
        "recipient_type": item.recipient_type,
        "language": item.language,
        "title": item.title,
        "body": item.body,
        "is_active": item.is_active,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _rule_to_dict(item: NotificationRule) -> dict:
    return {
        "id": item.id,
        "event_key": item.event_key,
        "recipient_type": item.recipient_type,
        "channel": item.channel,
        "is_enabled": item.is_enabled,
        "throttle_seconds": item.throttle_seconds,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


class NotificationAdminService:
    def list_templates(self, event_key: str | None = None, recipient_type: str | None = None, language: str | None = None) -> list[dict]:
        with SessionLocal() as db:
            stmt = select(NotificationTemplate).order_by(NotificationTemplate.event_key, NotificationTemplate.recipient_type, NotificationTemplate.language)
            if event_key:
                stmt = stmt.where(NotificationTemplate.event_key == event_key)
            if recipient_type:
                stmt = stmt.where(NotificationTemplate.recipient_type == recipient_type)
            if language:
                stmt = stmt.where(NotificationTemplate.language == language)
            return [_template_to_dict(item) for item in db.scalars(stmt)]

    def create_template(self, data: dict) -> dict:
        with SessionLocal() as db:
            item = NotificationTemplate(
                event_key=str(data["event_key"]),
                recipient_type=str(data["recipient_type"]),
                language=str(data.get("language") or "ru"),
                title=data.get("title"),
                body=str(data["body"]),
                is_active=bool(data.get("is_active", True)),
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            return _template_to_dict(item)

    def update_template(self, template_id: int, data: dict) -> dict | None:
        with SessionLocal() as db:
            item = db.get(NotificationTemplate, template_id)
            if not item:
                return None
            for key in ("event_key", "recipient_type", "language", "title", "body"):
                if key in data:
                    setattr(item, key, str(data[key]) if data[key] is not None else None)
            if "is_active" in data:
                item.is_active = bool(data["is_active"])
            item.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(item)
            return _template_to_dict(item)

    def list_rules(self, event_key: str | None = None, recipient_type: str | None = None, channel: str | None = None) -> list[dict]:
        with SessionLocal() as db:
            stmt = select(NotificationRule).order_by(NotificationRule.event_key, NotificationRule.recipient_type, NotificationRule.channel)
            if event_key:
                stmt = stmt.where(NotificationRule.event_key == event_key)
            if recipient_type:
                stmt = stmt.where(NotificationRule.recipient_type == recipient_type)
            if channel:
                stmt = stmt.where(NotificationRule.channel == channel)
            return [_rule_to_dict(item) for item in db.scalars(stmt)]

    def create_rule(self, data: dict) -> dict:
        with SessionLocal() as db:
            item = NotificationRule(
                event_key=str(data["event_key"]),
                recipient_type=str(data["recipient_type"]),
                channel=str(data["channel"]),
                is_enabled=bool(data.get("is_enabled", True)),
                throttle_seconds=int(data.get("throttle_seconds") or 0),
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            return _rule_to_dict(item)

    def update_rule(self, rule_id: int, data: dict) -> dict | None:
        with SessionLocal() as db:
            item = db.get(NotificationRule, rule_id)
            if not item:
                return None
            for key in ("event_key", "recipient_type", "channel"):
                if key in data:
                    setattr(item, key, str(data[key]))
            if "is_enabled" in data:
                item.is_enabled = bool(data["is_enabled"])
            if "throttle_seconds" in data:
                item.throttle_seconds = int(data["throttle_seconds"])
            db.commit()
            db.refresh(item)
            return _rule_to_dict(item)
