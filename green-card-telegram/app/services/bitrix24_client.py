from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request


TELEGRAM_USERNAME_FIELD = "UF_CRM_1697013093804"
TELEGRAM_USER_ID_FIELD = "UF_CRM_1780051881466"


class Bitrix24Client:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url.rstrip("/")

    def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.webhook_url}/{method}.json"
        data = parse.urlencode(self._flatten_payload(payload), doseq=True).encode("utf-8")
        req = request.Request(url, data=data, method="POST")
        try:
            with request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Bitrix request failed for {method}: {exc}") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError(f"Bitrix returned invalid response for {method}")
        if parsed.get("error"):
            description = parsed.get("error_description") or parsed.get("error")
            raise RuntimeError(f"Bitrix error for {method}: {description}")
        return parsed

    def _flatten_payload(self, payload: dict[str, Any]) -> list[tuple[str, Any]]:
        pairs: list[tuple[str, Any]] = []

        def add(prefix: str, value: Any) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    add(f"{prefix}[{key}]", nested)
            elif isinstance(value, list):
                for index, nested in enumerate(value):
                    if isinstance(nested, (dict, list)):
                        add(f"{prefix}[{index}]", nested)
                    else:
                        pairs.append((f"{prefix}[]", nested))
            elif value is not None:
                pairs.append((prefix, value))

        for key, value in payload.items():
            add(key, value)
        return pairs

    def find_contact_by_telegram_username(self, username: str) -> dict[str, Any] | None:
        return self.find_contact_by_telegram_identity(username=username)

    def find_contact_by_telegram_identity(self, username: str | None = None, user_id: int | str | None = None) -> dict[str, Any] | None:
        username = (username or "").strip()
        user_id = str(user_id or "").strip()
        if not username and not user_id:
            return None

        filters: list[dict[str, Any]] = []
        if user_id:
            filters.append({TELEGRAM_USER_ID_FIELD: user_id})
        if username:
            filters.append({TELEGRAM_USERNAME_FIELD: username})

        for crm_filter in filters:
            payload = {
                "filter": crm_filter,
                "select": [
                    "ID",
                    "LAST_NAME",
                    "NAME",
                    "BIRTHDATE",
                    "ADDRESS",
                    "PHONE",
                    "EMAIL",
                    "UF_CRM_CONTACT_1686145698592",
                    TELEGRAM_USERNAME_FIELD,
                    TELEGRAM_USER_ID_FIELD,
                ],
            }
            res = self._post("crm.contact.list", payload)
            items = res.get("result") or []
            if items:
                return items[0]
        return None

    def find_deal_by_license_plate(self, plate: str) -> dict[str, Any] | None:
        if not plate:
            return None
        payload = {
            "order": {"ID": "DESC"},
            "filter": {"UF_CRM_1686152485641": plate},
            "select": [
                "ID",
                "CONTACT_ID",
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
        fields = self._contact_fields(payload)
        existing = self._find_contact(fields)
        if existing:
            update_fields = self._contact_update_fields(fields, existing)
            if update_fields:
                self._post("crm.contact.update", {"id": existing["ID"], "fields": update_fields})
            return int(existing["ID"])
        return self._extract_id("crm.contact.add", self._post("crm.contact.add", {"fields": fields}))

    def create_or_update_company(self, payload: dict[str, Any]) -> int:
        fields = {key: value for key, value in payload.items() if value not in (None, "")}
        company_id = self._find_company_id(fields)
        if company_id:
            self._post("crm.company.update", {"id": company_id, "fields": fields})
            return company_id
        return self._extract_id("crm.company.add", self._post("crm.company.add", {"fields": fields}))

    def create_deal(self, payload: dict[str, Any]) -> int:
        fields = {key: value for key, value in payload.items() if value not in (None, "")}
        return self._extract_id("crm.deal.add", self._post("crm.deal.add", {"fields": fields}))

    def upload_file(self, file_path: str) -> str:
        return f"uploaded:{file_path}"

    def add_timeline_comment(self, entity_type: str, entity_id: int, comment: str) -> bool:
        entity_type_id = 2 if entity_type.lower() == "deal" else 3
        self._post(
            "crm.timeline.comment.add",
            {
                "fields": {
                    "ENTITY_ID": entity_id,
                    "ENTITY_TYPE": entity_type.upper(),
                    "ENTITY_TYPE_ID": entity_type_id,
                    "COMMENT": comment,
                }
            },
        )
        return True

    def _contact_fields(self, payload: dict[str, Any]) -> dict[str, Any]:
        fields = {key: value for key, value in payload.items() if value not in (None, "")}
        phone = fields.pop("PHONE_WORK", None)
        email = fields.pop("EMAIL_WORK", None)
        if phone:
            fields["PHONE"] = [{"VALUE": phone, "VALUE_TYPE": "WORK"}]
        if email:
            fields["EMAIL"] = [{"VALUE": email, "VALUE_TYPE": "WORK"}]
        return fields

    def _find_contact(self, fields: dict[str, Any]) -> dict[str, Any] | None:
        user_id = fields.get(TELEGRAM_USER_ID_FIELD)
        if user_id:
            existing = self._find_first("crm.contact.list", TELEGRAM_USER_ID_FIELD, user_id, self._contact_select_fields())
            if existing:
                return existing
        username = fields.get(TELEGRAM_USERNAME_FIELD)
        if username:
            existing = self._find_first("crm.contact.list", TELEGRAM_USERNAME_FIELD, username, self._contact_select_fields())
            if existing:
                return existing
        email = self._first_multifield_value(fields.get("EMAIL"))
        if email:
            return self._find_first("crm.contact.list", "EMAIL", email, self._contact_select_fields())
        return None

    def _contact_update_fields(self, fields: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
        update_fields = dict(fields)
        if self._multifield_contains(existing.get("EMAIL"), self._first_multifield_value(fields.get("EMAIL"))):
            update_fields.pop("EMAIL", None)
        if self._multifield_contains(existing.get("PHONE"), self._first_multifield_value(fields.get("PHONE"))):
            update_fields.pop("PHONE", None)
        return update_fields

    def _contact_select_fields(self) -> list[str]:
        return ["ID", "PHONE", "EMAIL", TELEGRAM_USERNAME_FIELD, TELEGRAM_USER_ID_FIELD]

    def _find_company_id(self, fields: dict[str, Any]) -> int | None:
        company_inn = fields.get("UF_CRM_COMPANY_1692911328252")
        company_id = self._find_first_id("crm.company.list", "UF_CRM_COMPANY_1692911328252", company_inn)
        if company_id:
            return company_id
        return self._find_first_id("crm.company.list", "TITLE", fields.get("TITLE"))

    def _find_first(self, method: str, field: str, value: Any, select: list[str]) -> dict[str, Any] | None:
        if not value:
            return None
        response = self._post(method, {"filter": {field: value}, "select": select})
        items = response.get("result") or []
        if not items:
            return None
        return items[0]

    def _find_first_id(self, method: str, field: str, value: Any) -> int | None:
        item = self._find_first(method, field, value, ["ID"])
        if not item:
            return None
        item_id = item.get("ID")
        return int(item_id) if item_id else None

    def _extract_id(self, method: str, response: dict[str, Any]) -> int:
        result = response.get("result")
        if isinstance(result, dict):
            result = result.get("ID")
        if result is None:
            raise RuntimeError(f"Bitrix response for {method} does not contain result ID")
        return int(result)

    def _first_multifield_value(self, value: Any) -> Any:
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                return first.get("VALUE")
        return value

    def _multifield_contains(self, existing: Any, value: Any) -> bool:
        if not value:
            return False
        needle = str(value).strip().lower()
        if isinstance(existing, list):
            for item in existing:
                if isinstance(item, dict) and str(item.get("VALUE", "")).strip().lower() == needle:
                    return True
        return str(existing or "").strip().lower() == needle
