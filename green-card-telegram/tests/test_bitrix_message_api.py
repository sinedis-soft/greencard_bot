import sys
import types

requests_stub = types.SimpleNamespace(post=lambda *args, **kwargs: None)
sys.modules.setdefault("requests", requests_stub)

from fastapi.testclient import TestClient

from app.main import app
from app.services.bitrix24_client import TELEGRAM_CHAT_ID_FIELD


def test_bitrix_message_api_sends_text_to_stored_chat_id(monkeypatch):
    calls = []
    monkeypatch.setenv("BITRIX_MESSAGE_API_TOKEN", "secret")
    monkeypatch.setenv("BOT_TOKEN", "bot-token")
    monkeypatch.setattr(
        "app.services.operator_notifier_service.requests.post",
        lambda url, json, timeout: calls.append((url, json, timeout)),
    )

    response = TestClient(app).post(
        "/api/bitrix/send-message",
        headers={"X-Bitrix-Token": "secret"},
        json={TELEGRAM_CHAT_ID_FIELD: "12345", "message": "Стоимость полиса: 10 USD"},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "chat_id": 12345}
    assert calls == [
        (
            "https://api.telegram.org/botbot-token/sendMessage",
            {"chat_id": 12345, "text": "Стоимость полиса: 10 USD"},
            5,
        )
    ]


def test_bitrix_message_api_requires_token(monkeypatch):
    monkeypatch.setenv("BITRIX_MESSAGE_API_TOKEN", "secret")
    monkeypatch.setenv("BOT_TOKEN", "bot-token")

    response = TestClient(app).post(
        "/api/bitrix/send-message",
        json={"chat_id": 12345, "text": "hello"},
    )

    assert response.status_code == 403
