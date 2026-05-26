import hashlib
import hmac
import json
from dataclasses import dataclass
from urllib.parse import parse_qsl


@dataclass
class TelegramUserContext:
    telegram_user_id: int | None
    username: str | None
    language_code: str | None


class TelegramAuthError(ValueError):
    pass


class TelegramAuthService:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token

    def validate_init_data(self, init_data: str) -> TelegramUserContext:
        if not init_data:
            raise TelegramAuthError("telegram_init_data is required")

        data = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = data.pop("hash", None)
        if not received_hash:
            raise TelegramAuthError("hash is missing in telegram_init_data")

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        secret = hmac.new(b"WebAppData", self.bot_token.encode("utf-8"), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            raise TelegramAuthError("invalid telegram initData signature")

        user_raw = data.get("user")
        user = json.loads(user_raw) if user_raw else {}
        return TelegramUserContext(
            telegram_user_id=user.get("id"),
            username=user.get("username"),
            language_code=user.get("language_code"),
        )
