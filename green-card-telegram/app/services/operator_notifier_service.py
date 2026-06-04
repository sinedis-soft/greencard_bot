import os
from pathlib import Path

import requests



class OperatorNotifierService:
    def __init__(self) -> None:
        self.token = os.getenv("OPERATOR_BOT_TOKEN", "")
        self.operator_ids = self._operator_ids()


    def _operator_ids(self) -> list[str]:
        try:
            from app.services.operator_service import OperatorService

            ids = OperatorService().active_operator_ids()
        except Exception:
            ids = set()
        if not ids:
            ids = {int(x.strip()) for x in os.getenv("OPERATOR_IDS", "").split(",") if x.strip()}
        return [str(operator_id) for operator_id in sorted(ids)]

    def notify_new_ticket(self, text: str, reply_command: str | None = None) -> None:
        if not self.token:
            return
        for operator_id in self.operator_ids:
            chat_id = int(operator_id)
            self._send_operator_message(chat_id, text)
            if reply_command:
                self._send_operator_message(chat_id, reply_command)

    def notify_operator_direct(
        self, operator_id: int, text: str, reply_command: str | None = None
    ) -> None:
        if not self.token:
            return
        self._send_operator_message(operator_id, text)
        if reply_command:
            self._send_operator_message(operator_id, reply_command)

    def notify_operator_reply_sent(
        self, text: str, exclude_operator_id: int | None = None
    ) -> None:
        if not self.token:
            return
        for operator_id in self.operator_ids:
            chat_id = int(operator_id)
            if exclude_operator_id is not None and chat_id == exclude_operator_id:
                continue
            self._send_operator_message(chat_id, text)

    def notify_payment_confirmation(self, text: str, local_paths: list[str]) -> None:
        if not self.token:
            return
        for operator_id in self.operator_ids:
            chat_id = int(operator_id)
            self._send_operator_message(chat_id, text)
            for local_path in local_paths:
                self._send_operator_document(chat_id, local_path)

    def _send_operator_message(self, chat_id: int, text: str) -> None:
        requests.post(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5,
        )

    def _send_operator_document(self, chat_id: int, local_path: str) -> None:
        path = Path(local_path)
        with path.open("rb") as file_obj:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendDocument",
                data={"chat_id": chat_id},
                files={"document": (path.name, file_obj)},
                timeout=10,
            )


class ClientNotifierService:
    def __init__(self) -> None:
        self.client_token = os.getenv("BOT_TOKEN", "")

    def send_to_client(
        self, telegram_user_id: int, text: str, reply_markup: dict | None = None
    ) -> bool:
        if not self.client_token:
            return False
        payload = {"chat_id": telegram_user_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        response = requests.post(
            f"https://api.telegram.org/bot{self.client_token}/sendMessage",
            json=payload,
            timeout=5,
        )
        return getattr(response, "ok", True)

    def send_document_to_client(self, telegram_user_id: int, local_path: str) -> bool:
        if not self.client_token:
            return False
        path = Path(local_path)
        with path.open("rb") as file_obj:
            response = requests.post(
                f"https://api.telegram.org/bot{self.client_token}/sendDocument",
                data={"chat_id": telegram_user_id},
                files={"document": (path.name, file_obj)},
                timeout=10,
            )
        return getattr(response, "ok", True)

    def send_restart_notice(self, telegram_user_id: int, text: str) -> bool:
        return self.send_to_client(
            telegram_user_id,
            text,
            {"keyboard": [[{"text": "/start"}]], "resize_keyboard": True},
        )
