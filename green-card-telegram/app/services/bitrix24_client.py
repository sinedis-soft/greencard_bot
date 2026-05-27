from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request


class Bitrix24Client:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url.rstrip("/")

    def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.webhook_url}/{method}.json"
        data = parse.urlencode(payload, doseq=True).encode("utf-8")
        req = request.Request(url, data=data, method="POST")
        try:
            with request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            return parsed if isinstance(parsed, dict) else {}
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return {}

    def find_contact_by_telegram_username(self, username: str) -> dict[str, Any] | None:
        if not username:
            return None
        payload = {
            "filter[UF_CRM_1697013093804]": username,
            "select[]": [
                "LAST_NAME",
                "NAME",
                "BIRTHDATE",
                "ADDRESS",
                "PHONE",
                "EMAIL",
                "UF_CRM_CONTACT_1686145698592",
            ],
        }
        res = self._post("crm.contact.list", payload)
        items = res.get("result") or []
        if not items:
            return None
        return items[0]


    def find_deal_by_license_plate(self, plate: str) -> dict[str, Any] | None:
        if not plate:
            return None
        payload = {
            "filter[UF_CRM_1686152485641]": plate,
            "select[]": [
                "UF_CRM_1686154280439",
                "UF_CRM_1686152306664",
                "UF_CRM_1686152515152",
                "UF_CRM_1686152614718",
                "UF_CRM_1686152659867",
                "UF_CRM_1686152567597",
                "UF_CRM_1686152745455",
                "UF_CRM_1686152831791",
                "UF_CRM_1686152861297",
                "UF_CRM_1686152902186",
                "UF_CRM_1686152485641",
            ],
        }
        res = self._post("crm.deal.list", payload)
        items = res.get("result") or []
        if not items:
            return None
        return items[0]

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
