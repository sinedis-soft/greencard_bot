import hashlib
import hmac
import json
from urllib.parse import urlencode

from app.services.telegram_auth_service import TelegramAuthService


def build_init_data(bot_token: str, user: dict, chat: dict | None = None) -> str:
    data = {
        "auth_date": "1710000000",
        "query_id": "AAEAAAE",
        "user": json.dumps(user, separators=(",", ":")),
    }
    if chat:
        data["chat"] = json.dumps(chat, separators=(",", ":"))
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_validate_init_data_uses_chat_id_when_present():
    context = TelegramAuthService("test-token").validate_init_data(
        build_init_data("test-token", {"id": 12345, "username": "john"}, {"id": -10067890})
    )

    assert context.telegram_user_id == 12345
    assert context.telegram_chat_id == -10067890


def test_validate_init_data_falls_back_to_user_id_as_chat_id():
    context = TelegramAuthService("test-token").validate_init_data(
        build_init_data("test-token", {"id": 12345, "username": "john"})
    )

    assert context.telegram_chat_id == 12345
