import hmac
import os
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query

from app.services.bitrix24_client import TELEGRAM_CHAT_ID_FIELD
from app.services.operator_notifier_service import ClientNotifierService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/bitrix", tags=["bitrix"])


def _validate_bitrix_token(header_token: str | None, query_token: str | None) -> None:
    expected_token = os.getenv("BITRIX_MESSAGE_API_TOKEN", "")
    if not expected_token:
        raise HTTPException(status_code=503, detail="bitrix_message_api_token_not_configured")

    received_token = header_token or query_token or ""
    if not hmac.compare_digest(received_token, expected_token):
        raise HTTPException(status_code=403, detail="forbidden")


def _payload_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


@router.post("/send-message")
def send_message_to_telegram_chat(
    payload: dict[str, Any] = Body(...),
    x_bitrix_token: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> dict[str, Any]:
    _validate_bitrix_token(x_bitrix_token, token)

    raw_chat_id = _payload_value(payload, "chat_id", TELEGRAM_CHAT_ID_FIELD)
    raw_text = _payload_value(payload, "text", "message")
    if raw_chat_id is None:
        raise HTTPException(status_code=400, detail="chat_id_required")
    if raw_text is None or not str(raw_text).strip():
        raise HTTPException(status_code=400, detail="text_required")

    try:
        chat_id = int(raw_chat_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="chat_id_invalid") from exc

    sent = ClientNotifierService().send_to_client(chat_id, str(raw_text).strip())
    if not sent:
        raise HTTPException(status_code=503, detail="bot_token_not_configured")

    return {"success": True, "chat_id": chat_id}

@router.post("/events")
def handle_bitrix_event(
    payload: dict[str, Any] = Body(...),
    x_bitrix_token: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> dict[str, Any]:
    _validate_bitrix_token(x_bitrix_token, token)

    event_key = str(_payload_value(payload, "event", "event_key") or "").strip()
    if not event_key:
        raise HTTPException(status_code=400, detail="event_required")

    telegram_chat_id = _payload_value(payload, "telegram_chat_id", "chat_id", TELEGRAM_CHAT_ID_FIELD)
    recipient_type = str(payload.get("recipient_type") or "client")
    channel = str(payload.get("channel") or f"{recipient_type}_telegram")
    language = str(payload.get("language") or "ru")
    context = dict(payload.get("context") or {})
    for key in ("request_id", "deal_id", "bitrix_deal_id", "policy_status", "vehicle_plate_masked", "end_date"):
        if key in payload and key not in context:
            context[key] = payload[key]

    recipient_id = str(payload.get("recipient_id") or telegram_chat_id or "broadcast")
    result = NotificationService().send(
        event_key=event_key,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        channel=channel,
        language=language,
        context=context,
        dedupe_key=str(payload.get("dedupe_key") or f"{event_key}:{payload.get('deal_id') or payload.get('request_id') or recipient_id}"),
    )
    return result.to_dict()
