from typing import Any


class Bitrix24Client:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def create_or_update_contact(self, payload: dict[str, Any]) -> int:
        return 1001

    def create_or_update_company(self, payload: dict[str, Any]) -> int:
        return 2001

    def create_deal(self, payload: dict[str, Any]) -> int:
        return 3001

    def upload_file(self, file_path: str) -> str:
        return f"uploaded:{file_path}"

    def add_timeline_comment(self, entity_type: str, entity_id: int, comment: str) -> bool:
        return True
