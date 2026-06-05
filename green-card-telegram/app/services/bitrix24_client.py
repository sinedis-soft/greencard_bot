from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib import error, parse, request


TELEGRAM_USERNAME_FIELD = "UF_CRM_1697013093804"
TELEGRAM_USER_ID_FIELD = "UF_CRM_1780051881466"
TELEGRAM_CHAT_ID_FIELD = "UF_CRM_1780237379152"
REQUEST_ID_FIELD = "UF_CRM_1780595513795"
SHOW_IN_TELEGRAM_FIELD = "UF_CRM_1780595576304"
REPEAT_FROM_DEAL_FIELD = "UF_CRM_REPEAT_FROM_DEAL_ID"
REPEAT_MODE_FIELD = "UF_CRM_REPEAT_MODE"
DOCS_REUSE_REQUESTED_FIELD = "UF_CRM_DOCS_REUSE_REQUESTED"
PRODUCT_TYPE_FIELD = "UF_CRM_PRODUCT_TYPE"
POLICY_EXPECTED_AT_FIELD = "UF_CRM_POLICY_EXPECTED_AT"
POLICY_SENT_AT_FIELD = "UF_CRM_POLICY_SENT_AT"
PUBLIC_STATUS_FIELD = "UF_CRM_PUBLIC_STATUS"


POLICY_NUMBER_FIELD = "UF_CRM_1694177619522"
POLICY_STATUS_FIELD = "UF_CRM_1718956082020"
POLICY_FILES_FIELD = "UF_CRM_1714480913426"
LICENSE_PLATE_FIELD = "UF_CRM_1686152485641"
VIN_FIELD = "UF_CRM_1686152659867"

POLICY_STATUS_VALUES = {
    "2607": "Действующий",
    "2609": "Аннулирован",
    "2611": "В процессе оформления",
    "2613": "Срок действия страховки завершен",
    "2643": "Дубликат полиса",
    "2645": "Зарегистрирован",
}


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
                use_positional_scalars = prefix.endswith("[fileData]") or prefix.endswith("[fileContent]")
                for index, nested in enumerate(value):
                    if isinstance(nested, (dict, list)):
                        add(f"{prefix}[{index}]", nested)
                    elif use_positional_scalars:
                        pairs.append((f"{prefix}[{index}]", nested))
                    else:
                        pairs.append((f"{prefix}[]", nested))
            elif value is not None:
                pairs.append((prefix, value))

        for key, value in payload.items():
            add(key, value)
        return pairs

    def find_contact_by_telegram_username(self, username: str) -> dict[str, Any] | None:
        return self.find_contact_by_telegram_identity(username=username)

    def find_contact_by_email(self, email: str) -> dict[str, Any] | None:
        email = (email or "").strip()
        if not email:
            return None
        return self._find_first("crm.contact.list", "EMAIL", email, self._prefill_contact_select_fields())

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
                "select": self._prefill_contact_select_fields(),
            }
            res = self._post("crm.contact.list", payload)
            items = res.get("result") or []
            if items:
                return items[0]
        return None

    def _prefill_contact_select_fields(self) -> list[str]:
        return [
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
            TELEGRAM_CHAT_ID_FIELD,
        ]

    def find_deal_by_license_plate(self, plate: str) -> dict[str, Any] | None:
        return self._find_deal_by_vehicle_field(LICENSE_PLATE_FIELD, plate)

    def find_deal_by_vin(self, vin: str) -> dict[str, Any] | None:
        return self._find_deal_by_vehicle_field(VIN_FIELD, vin)

    def _find_deal_by_vehicle_field(self, field: str, value: str) -> dict[str, Any] | None:
        if not value:
            return None
        payload = {
            "order": {"ID": "DESC"},
            "filter": {field: value},
            "select": [
                "ID",
                "TITLE",
                "STAGE_ID",
                "DATE_CREATE",
                "CONTACT_ID",
                "CLOSED",
                "UF_CRM_1686154280439",
                "UF_CRM_1686152306664",
                "UF_CRM_1686152515152",
                "UF_CRM_1686152614718",
                VIN_FIELD,
                "UF_CRM_1686152567597",
                "UF_CRM_1686152745455",
                "UF_CRM_1686152831791",
                "UF_CRM_1686152861297",
                "UF_CRM_1686152902186",
                LICENSE_PLATE_FIELD,
                PRODUCT_TYPE_FIELD,
                SHOW_IN_TELEGRAM_FIELD,
            ],
        }
        res = self._post("crm.deal.list", payload)
        items = res.get("result") or []
        if not items:
            return None
        return items[0]

    def find_latest_deal_by_telegram_identity(
        self, username: str | None = None, user_id: int | str | None = None
    ) -> dict[str, Any] | None:
        contact = self.find_contact_by_telegram_identity(
            username=username, user_id=user_id
        )
        if contact and contact.get("ID"):
            deal = self.find_latest_deal_by_contact_id(contact["ID"])
            if deal:
                return deal

        if user_id:
            deal = self._find_latest_deal({TELEGRAM_CHAT_ID_FIELD: str(user_id)})
            if deal:
                return deal
        return None

    def find_latest_deal_by_contact_id(self, contact_id: int | str) -> dict[str, Any] | None:
        if not contact_id:
            return None
        return self._find_latest_deal({"CONTACT_ID": str(contact_id)})


    def list_deals_by_contact_id(
        self,
        contact_id: int | str,
        limit: int = 10,
        show_in_telegram_only: bool = True,
    ) -> list[dict[str, Any]]:
        if not contact_id:
            return []
        crm_filter: dict[str, Any] = {"CONTACT_ID": str(contact_id)}
        if show_in_telegram_only:
            crm_filter[SHOW_IN_TELEGRAM_FIELD] = "1"

        res = self._post(
            "crm.deal.list",
            {
                "order": {"DATE_CREATE": "DESC", "ID": "DESC"},
                "filter": crm_filter,
                "select": self._client_application_deal_select_fields(),
            },
        )
        items = res.get("result") or []
        return [item for item in items if isinstance(item, dict)][: max(limit, 0)]

    def _client_application_deal_select_fields(self) -> list[str]:
        return [
            "ID",
            "TITLE",
            "STAGE_ID",
            "DATE_CREATE",
            "CATEGORY_ID",
            "CONTACT_ID",
            "COMPANY_ID",
            REQUEST_ID_FIELD,
            TELEGRAM_CHAT_ID_FIELD,
            LICENSE_PLATE_FIELD,
            "UF_CRM_1686152306664",
            "UF_CRM_1686152149204",
            "UF_CRM_1686152209741",
            "UF_CRM_1686152567597",
            "UF_CRM_1686152659867",
            "UF_CRM_1686152515152",
            "UF_CRM_1686152614718",
            "UF_CRM_1686152745455",
            "UF_CRM_1686152831791",
            "UF_CRM_1686152861297",
            "UF_CRM_1686152902186",
            PRODUCT_TYPE_FIELD,
            POLICY_NUMBER_FIELD,
            POLICY_STATUS_FIELD,
            POLICY_FILES_FIELD,
            POLICY_EXPECTED_AT_FIELD,
            POLICY_SENT_AT_FIELD,
            PUBLIC_STATUS_FIELD,
            SHOW_IN_TELEGRAM_FIELD,
        ]

    def _find_latest_deal(self, crm_filter: dict[str, Any]) -> dict[str, Any] | None:
        res = self._post(
            "crm.deal.list",
            {
                "order": {"ID": "DESC"},
                "filter": crm_filter,
                "select": self._latest_deal_select_fields(),
            },
        )
        items = res.get("result") or []
        if not items:
            return None
        return items[0]

    def _latest_deal_select_fields(self) -> list[str]:
        return [
            "ID",
            "TITLE",
            "COMMENTS",
            "CONTACT_ID",
            TELEGRAM_CHAT_ID_FIELD,
            POLICY_NUMBER_FIELD,
            POLICY_STATUS_FIELD,
            POLICY_FILES_FIELD,
            LICENSE_PLATE_FIELD,
        ]


    def deal_url(self, deal_id: int | str) -> str:
        return parse.urljoin(self._portal_base_url(), f"crm/deal/details/{deal_id}/")

    def get_deal(self, deal_id: int | str) -> dict[str, Any] | None:
        if not deal_id:
            return None
        result = self._post("crm.deal.get", {"id": deal_id}).get("result")
        return result if isinstance(result, dict) else None

    def get_deal_file_infos(
        self, deal_id: int | str, field_name: str = POLICY_FILES_FIELD
    ) -> list[dict[str, Any]]:
        deal = self.get_deal(deal_id)
        if not deal:
            return []
        return self._normalize_file_infos(deal.get(field_name))

    def download_deal_file(
        self, file_info: dict[str, Any], target_dir: str | Path
    ) -> str:
        url = self._file_download_url(file_info)
        if not url:
            raise RuntimeError(f"Bitrix file metadata has no download URL: {file_info}")

        req = request.Request(url, headers={"User-Agent": "OCGraniczneTelegramBot/1.0"})
        try:
            with request.urlopen(req, timeout=60) as resp:
                content_type = str(resp.headers.get("Content-Type", "")).lower()
                content_disposition = str(resp.headers.get("Content-Disposition", ""))
                content = resp.read()
        except (error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Bitrix file download failed: {exc}") from exc

        if self._looks_like_html(content_type, content):
            raise RuntimeError(
                "Bitrix returned an HTML login page instead of a deal file"
            )

        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)
        filename = self._download_filename(file_info, content_disposition)
        path = target / filename
        path.write_bytes(content)
        return str(path)

    def _normalize_file_infos(self, value: Any) -> list[dict[str, Any]]:
        if not value:
            return []
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    def _file_download_url(self, file_info: dict[str, Any]) -> str:
        url = str(
            file_info.get("downloadUrl")
            or file_info.get("DOWNLOAD_URL")
            or file_info.get("url")
            or file_info.get("URL")
            or file_info.get("showUrl")
            or file_info.get("SHOW_URL")
            or ""
        ).strip()
        if not url:
            return ""
        if url.startswith("/"):
            url = parse.urljoin(self._portal_base_url(), url)
        return self._with_webhook_auth(url)

    def _portal_base_url(self) -> str:
        parsed = parse.urlparse(self.webhook_url)
        return f"{parsed.scheme}://{parsed.netloc}/"

    def _webhook_code(self) -> str:
        parts = [
            part
            for part in parse.urlparse(self.webhook_url).path.split("/")
            if part
        ]
        if len(parts) >= 3 and parts[0] == "rest":
            return parts[2]
        return ""

    def _with_webhook_auth(self, url: str) -> str:
        webhook_code = self._webhook_code()
        if not webhook_code:
            return url
        parsed = parse.urlparse(url)
        query = parse.parse_qsl(parsed.query, keep_blank_values=True)
        filtered = [(key, value) for key, value in query if key != "auth"]
        filtered.append(("auth", webhook_code))
        return parse.urlunparse(parsed._replace(query=parse.urlencode(filtered)))

    def _looks_like_html(self, content_type: str, content: bytes) -> bool:
        if "text/html" in content_type:
            return True
        prefix = content[:500].lstrip().lower()
        return prefix.startswith(b"<!doctype html") or b"<html" in prefix

    def _download_filename(
        self, file_info: dict[str, Any], content_disposition: str
    ) -> str:
        filename = self._filename_from_content_disposition(content_disposition)
        if not filename:
            filename = str(
                file_info.get("name")
                or file_info.get("NAME")
                or file_info.get("fileName")
                or file_info.get("FILE_NAME")
                or f"bitrix_file_{file_info.get('id') or file_info.get('ID') or 'file'}"
            )
        filename = Path(filename).name.strip() or "bitrix_file"
        return "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in filename)

    def _filename_from_content_disposition(self, value: str) -> str:
        if not value:
            return ""
        utf_match = re.search(r"filename\*=UTF-8''([^;]+)", value, flags=re.I)
        if utf_match:
            return parse.unquote(utf_match.group(1).strip().strip('"'))
        match = re.search(r'filename="?([^";]+)"?', value, flags=re.I)
        if match:
            return parse.unquote(match.group(1).strip())
        return ""

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
        return ["ID", "PHONE", "EMAIL", TELEGRAM_USERNAME_FIELD, TELEGRAM_USER_ID_FIELD, TELEGRAM_CHAT_ID_FIELD]

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
