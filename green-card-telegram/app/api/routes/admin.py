import os

from fastapi import APIRouter, Body, Header, HTTPException, Query

from app.services.analytics_service import AnalyticsService
from app.services.content_text_service import ContentTextService
from app.services.notification_admin_service import NotificationAdminService
from app.services.operator_service import OperatorService
from app.services.tariff_admin_service import TariffAdminService

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(x_admin_token: str | None) -> None:
    if not x_admin_token or x_admin_token != os.getenv("ADMIN_API_TOKEN", ""):
        raise HTTPException(status_code=403, detail="forbidden")


def _not_found() -> None:
    raise HTTPException(status_code=404, detail="not_found")


@router.get("/applications/{request_id}/events")
def get_application_events(request_id: str, x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
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


@router.get("/operators")
def list_operators(
    include_inactive: bool = Query(default=True),
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _require_admin(x_admin_token)
    return {"items": OperatorService().list_operators(include_inactive=include_inactive)}


@router.post("/operators")
def create_operator(payload: dict = Body(...), x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    try:
        return OperatorService().create_operator(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc) or "invalid_payload") from exc


@router.patch("/operators/{operator_id}")
def update_operator(operator_id: int, payload: dict = Body(...), x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    try:
        result = OperatorService().update_operator(operator_id, payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc) or "invalid_payload") from exc
    if not result:
        _not_found()
    return result


@router.post("/operators/{operator_id}/activate")
def activate_operator(operator_id: int, x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    result = OperatorService().set_active(operator_id, True)
    if not result:
        _not_found()
    return result


@router.post("/operators/{operator_id}/deactivate")
def deactivate_operator(operator_id: int, x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    result = OperatorService().set_active(operator_id, False)
    if not result:
        _not_found()
    return result


@router.get("/tariffs")
def list_tariffs(active_only: bool = Query(default=False), x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    return {"items": TariffAdminService().list_tariffs(active_only=active_only)}


@router.post("/tariffs")
def create_tariff(payload: dict = Body(...), x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    try:
        return TariffAdminService().create_tariff(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc) or "invalid_payload") from exc


@router.patch("/tariffs/{tariff_id}")
def update_tariff(tariff_id: int, payload: dict = Body(...), x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    try:
        result = TariffAdminService().update_tariff(tariff_id, payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc) or "invalid_payload") from exc
    if not result:
        _not_found()
    return result


@router.post("/tariffs/{tariff_id}/activate")
def activate_tariff(tariff_id: int, x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    result = TariffAdminService().set_active(tariff_id, True)
    if not result:
        _not_found()
    return result


@router.post("/tariffs/{tariff_id}/deactivate")
def deactivate_tariff(tariff_id: int, x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    result = TariffAdminService().set_active(tariff_id, False)
    if not result:
        _not_found()
    return result


@router.get("/texts")
def list_texts(
    category: str | None = Query(default=None),
    language: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _require_admin(x_admin_token)
    return {"items": ContentTextService().list_texts(category=category, language=language, active_only=active_only)}


@router.post("/texts")
def create_text(payload: dict = Body(...), x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    try:
        return ContentTextService().create_text(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc) or "invalid_payload") from exc


@router.patch("/texts/{text_id}")
def update_text(text_id: int, payload: dict = Body(...), x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    result = ContentTextService().update_text(text_id, payload)
    if not result:
        _not_found()
    return result


@router.post("/texts/{text_id}/activate")
def activate_text(text_id: int, x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    result = ContentTextService().set_active(text_id, True)
    if not result:
        _not_found()
    return result


@router.post("/texts/{text_id}/deactivate")
def deactivate_text(text_id: int, x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    result = ContentTextService().set_active(text_id, False)
    if not result:
        _not_found()
    return result

@router.get("/notification-templates")
def list_notification_templates(
    event_key: str | None = Query(default=None),
    recipient_type: str | None = Query(default=None),
    language: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _require_admin(x_admin_token)
    return {"items": NotificationAdminService().list_templates(event_key=event_key, recipient_type=recipient_type, language=language)}


@router.post("/notification-templates")
def create_notification_template(payload: dict = Body(...), x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    try:
        return NotificationAdminService().create_template(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc) or "invalid_payload") from exc


@router.patch("/notification-templates/{template_id}")
def update_notification_template(template_id: int, payload: dict = Body(...), x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    result = NotificationAdminService().update_template(template_id, payload)
    if not result:
        _not_found()
    return result


@router.get("/notification-rules")
def list_notification_rules(
    event_key: str | None = Query(default=None),
    recipient_type: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _require_admin(x_admin_token)
    return {"items": NotificationAdminService().list_rules(event_key=event_key, recipient_type=recipient_type, channel=channel)}


@router.post("/notification-rules")
def create_notification_rule(payload: dict = Body(...), x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    try:
        return NotificationAdminService().create_rule(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc) or "invalid_payload") from exc


@router.patch("/notification-rules/{rule_id}")
def update_notification_rule(rule_id: int, payload: dict = Body(...), x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    result = NotificationAdminService().update_rule(rule_id, payload)
    if not result:
        _not_found()
    return result
