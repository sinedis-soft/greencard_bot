from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

from app.services.bitrix24_client import (
    LICENSE_PLATE_FIELD,
    POLICY_FILES_FIELD,
    POLICY_NUMBER_FIELD,
    POLICY_STATUS_FIELD,
    POLICY_STATUS_VALUES,
)

if TYPE_CHECKING:
    from app.services.i18n_service import I18nService

INVOICE_TITLE_MARKERS = ("счет", "счёт", "коммерческое предложение")


def is_invoice_deal(deal: dict[str, Any]) -> bool:
    title = str(deal.get("TITLE") or "").casefold()
    return any(marker in title for marker in INVOICE_TITLE_MARKERS)


def latest_deal_text(i18n: "I18nService", lang: str, deal: dict[str, Any]) -> str:
    title = _clean(deal.get("TITLE"))
    if is_invoice_deal(deal):
        parts = [f"{i18n.get_text(lang, 'latest_deal.title_label')}: {title}"]
        comments = _clean(deal.get("COMMENTS"))
        if comments:
            parts.append(
                f"{i18n.get_text(lang, 'latest_deal.comments_label')}: {comments}"
            )
        parts.append(
            i18n.get_text(lang, "latest_deal.payment_instructions").format(
                license_plate=_clean(deal.get(LICENSE_PLATE_FIELD))
            )
        )
        return "\n\n".join(parts)

    parts = [f"{i18n.get_text(lang, 'latest_deal.title_label')}: {title}"]
    policy_number = _clean(deal.get(POLICY_NUMBER_FIELD))
    if policy_number:
        parts.append(
            f"{i18n.get_text(lang, 'latest_deal.policy_number_label')}: {policy_number}"
        )
    policy_status = policy_status_text(deal.get(POLICY_STATUS_FIELD))
    if policy_status:
        parts.append(
            f"{i18n.get_text(lang, 'latest_deal.policy_status_label')}: {policy_status}"
        )
    return "\n".join(parts)


def policy_status_text(value: Any) -> str:
    if isinstance(value, dict):
        value = (
            value.get("VALUE")
            or value.get("value")
            or value.get("ID")
            or value.get("id")
        )
    if isinstance(value, list):
        return ", ".join(filter(None, (policy_status_text(item) for item in value)))
    cleaned = _clean(value)
    if not cleaned:
        return ""
    return POLICY_STATUS_VALUES.get(cleaned, cleaned)


def deal_file_items(deal: dict[str, Any], webhook_url: str = "") -> list[tuple[str, str]]:
    return _extract_file_items(deal.get(POLICY_FILES_FIELD), _bitrix_base_url(webhook_url))


def _extract_file_items(value: Any, base_url: str) -> list[tuple[str, str]]:
    if not value:
        return []
    if isinstance(value, dict):
        url = _clean(

            value.get("downloadUrl")
            or value.get("DOWNLOAD_URL")
            or value.get("url")
            or value.get("URL")

        )
        name = _clean(
            value.get("name")
            or value.get("NAME")
            or value.get("fileName")
            or value.get("FILE_NAME")
            or value.get("id")
            or value.get("ID")
            or "policy-file"
        )
        return [(name, _absolute_url(url, base_url))] if url else []
    if isinstance(value, list):
        items: list[tuple[str, str]] = []
        for item in value:
            items.extend(_extract_file_items(item, base_url))
        return items
    url = _clean(value)
    if url.startswith(("http://", "https://", "/")):
        return [("policy-file", _absolute_url(url, base_url))]
    return []


def _absolute_url(url: str, base_url: str) -> str:
    if not url or url.startswith(("http://", "https://")):
        return url
    return urljoin(base_url, url)


def _bitrix_base_url(webhook_url: str) -> str:
    if not webhook_url:
        return ""
    parts = webhook_url.split("/rest", 1)
    return parts[0].rstrip("/") + "/"


def _clean(value: Any) -> str:
    return str(value or "").strip()
