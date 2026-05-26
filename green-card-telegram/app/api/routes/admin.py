import os

from fastapi import APIRouter, Header, HTTPException

from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/applications/{request_id}/events")
def get_application_events(request_id: str, x_admin_token: str | None = Header(default=None)) -> dict:
    if not x_admin_token or x_admin_token != os.getenv("ADMIN_API_TOKEN", ""):
        raise HTTPException(status_code=403, detail="forbidden")

    events = AnalyticsService().get_events(request_id)
    return {
        "request_id": request_id,
        "events": [
            {
                "id": e.id,
                "event_name": e.event_name,
                "event_payload_json": e.event_payload_json,
                "telegram_user_id": e.telegram_user_id,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }
