import json
from datetime import datetime

from sqlalchemy import select

from app.db.models import AnalyticsEvent
from app.db.session import SessionLocal


class AnalyticsService:
    def track(self, event_name: str, request_id: str | None = None, telegram_user_id: int | None = None, payload: dict | None = None) -> None:
        with SessionLocal() as db:
            db.add(
                AnalyticsEvent(
                    request_id=request_id,
                    telegram_user_id=telegram_user_id,
                    event_name=event_name,
                    event_payload_json=json.dumps(payload or {}),
                    created_at=datetime.utcnow(),
                )
            )
            db.commit()

    def get_events(self, request_id: str) -> list[AnalyticsEvent]:
        with SessionLocal() as db:
            return list(db.scalars(select(AnalyticsEvent).where(AnalyticsEvent.request_id == request_id).order_by(AnalyticsEvent.created_at.asc())))
