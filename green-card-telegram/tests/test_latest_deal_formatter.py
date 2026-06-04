from app.services.bitrix24_client import (
    LICENSE_PLATE_FIELD,
    POLICY_FILES_FIELD,
    POLICY_NUMBER_FIELD,
    POLICY_STATUS_FIELD,
)
from app.services.latest_deal_formatter import deal_file_items, latest_deal_text


class FakeI18n:
    texts = {
        "ru": {
            "latest_deal.title_label": "TITLE",
            "latest_deal.policy_number_label": "Номер полиса",
            "latest_deal.policy_status_label": "Состояние полиса",
            "latest_deal.comments_label": "COMMENTS",
            "latest_deal.payment_instructions": "Оплата для {license_plate}",
        },
        "be": {
            "latest_deal.title_label": "TITLE",
            "latest_deal.policy_number_label": "Нумар поліса",
            "latest_deal.policy_status_label": "Стан поліса",
            "latest_deal.comments_label": "COMMENTS",
            "latest_deal.payment_instructions": (
                "Ваша заяўка на страхаванне аўтамабіля {license_plate} ўхвалена.\n"
                "Прызначэнне плацяжу: za ubezpieczenie auto {license_plate}"
            ),
        },
    }

    def get_text(self, lang, key, fallback_lang="en"):
        return self.texts[lang][key]


I18N = FakeI18n()


def test_latest_deal_text_includes_policy_fields_when_present():
    text = latest_deal_text(
        I18N,
        "ru",
        {
            "TITLE": "Green Card AA123BB",
            POLICY_NUMBER_FIELD: "POL-1",
            POLICY_STATUS_FIELD: "2607",
        },
    )

    assert "TITLE: Green Card AA123BB" in text
    assert "Номер полиса: POL-1" in text
    assert "Состояние полиса: Действующий" in text


def test_latest_deal_text_for_invoice_includes_comments_and_localized_payment_text():
    text = latest_deal_text(
        I18N,
        "be",
        {
            "TITLE": "Счет/коммерческое предложение 4538EX1",
            "COMMENTS": "Да аплаты 100 PLN",
            LICENSE_PLATE_FIELD: "4538EX1",
        },
    )

    assert "TITLE: Счет/коммерческое предложение 4538EX1" in text
    assert "COMMENTS: Да аплаты 100 PLN" in text
    assert "Ваша заяўка на страхаванне аўтамабіля 4538EX1 ўхвалена." in text
    assert "Прызначэнне плацяжу: za ubezpieczenie auto 4538EX1" in text


def test_deal_file_items_extracts_bitrix_file_download_urls():
    items = deal_file_items(
        {
            POLICY_FILES_FIELD: [
                {
                    "name": "policy.pdf",
                    "downloadUrl": "/bitrix/download/1207185/policy.pdf",
                    "showUrl": "/bitrix/components/bitrix/crm.deal.show/show_file.php?fileId=10",
                },
                {
                    "NAME": "green-card.pdf",
                    "DOWNLOAD_URL": "https://cdn.example.test/green-card.pdf",
                },
            ]
        },
        "https://example.bitrix24.com/rest/1/webhook",
    )

    assert items == [
        (
            "policy.pdf",
            "https://example.bitrix24.com/bitrix/download/1207185/policy.pdf",
        ),
        ("green-card.pdf", "https://cdn.example.test/green-card.pdf"),
    ]


def test_bitrix_client_reads_deal_file_metadata_via_rest():
    from app.services.bitrix24_client import Bitrix24Client

    calls = []

    class FakeBitrixClient(Bitrix24Client):
        def _post(self, method, payload):
            calls.append((method, payload))
            return {
                "result": {
                    POLICY_FILES_FIELD: {
                        "id": 1207185,
                        "downloadUrl": "/bitrix/download/1207185/policy.pdf",
                    }
                }
            }

    client = FakeBitrixClient("https://example.bitrix24.com/rest/7/webhook-code")

    assert client.get_deal_file_infos(82163) == [
        {
            "id": 1207185,
            "downloadUrl": "/bitrix/download/1207185/policy.pdf",
        }
    ]
    assert calls == [("crm.deal.get", {"id": 82163})]


def test_bitrix_client_download_file_adds_webhook_auth_and_rejects_html(
    monkeypatch, tmp_path
):
    from app.services.bitrix24_client import Bitrix24Client
    from app.services import bitrix24_client

    opened_urls = []

    class HtmlResponse:
        headers = {"Content-Type": "text/html; charset=UTF-8"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"<!DOCTYPE html><html>login</html>"

    def fake_urlopen(req, timeout):
        opened_urls.append(req.full_url)
        return HtmlResponse()

    monkeypatch.setattr(bitrix24_client.request, "urlopen", fake_urlopen)
    client = Bitrix24Client("https://example.bitrix24.com/rest/7/webhook-code")

    try:
        client.download_deal_file(
            {"id": 1207185, "downloadUrl": "/bitrix/download/1207185/policy.pdf"},
            tmp_path,
        )
    except RuntimeError as exc:
        assert "HTML login page" in str(exc)
    else:
        raise AssertionError("Expected HTML login page download to fail")

    assert opened_urls == [
        "https://example.bitrix24.com/bitrix/download/1207185/policy.pdf"
        "?auth=webhook-code"
    ]


def test_bitrix_client_download_file_saves_non_html_content(monkeypatch, tmp_path):
    from app.services.bitrix24_client import Bitrix24Client
    from app.services import bitrix24_client

    class PdfResponse:
        headers = {
            "Content-Type": "application/pdf",
            "Content-Disposition": 'attachment; filename="policy.pdf"',
        }

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"%PDF-1.4"

    monkeypatch.setattr(
        bitrix24_client.request, "urlopen", lambda req, timeout: PdfResponse()
    )
    client = Bitrix24Client("https://example.bitrix24.com/rest/7/webhook-code")

    path = client.download_deal_file(
        {"id": 1207185, "downloadUrl": "/bitrix/download/1207185/policy.pdf"},
        tmp_path,
    )

    assert path.endswith("policy.pdf")
    assert (tmp_path / "policy.pdf").read_bytes() == b"%PDF-1.4"
