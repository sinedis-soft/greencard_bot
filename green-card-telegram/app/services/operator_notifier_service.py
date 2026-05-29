import os

import requests


class OperatorNotifierService:
    def __init__(self) -> None:
        self.token = os.getenv("OPERATOR_BOT_TOKEN", "")
        self.operator_ids = [x.strip() for x in os.getenv("OPERATOR_IDS", "").split(",") if x.strip()]

    def notify_new_ticket(self, text: str, reply_command: str | None = None) -> None:
        if not self.token:
            return
        for operator_id in self.operator_ids:
            chat_id = int(operator_id)
            self._send_operator_message(chat_id, text)
            if reply_command:
                self._send_operator_message(chat_id, reply_command)

    def _send_operator_message(self, chat_id: int, text: str) -> None:
        requests.post(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5,
        )


class ClientNotifierService:
    def __init__(self) -> None:
        self.client_token = os.getenv("BOT_TOKEN", "")

    def send_to_client(self, telegram_user_id: int, text: str) -> None:
        if not self.client_token:
            return
        requests.post(
            f"https://api.telegram.org/bot{self.client_token}/sendMessage",
            json={"chat_id": telegram_user_id, "text": text},
            timeout=5,
        )
