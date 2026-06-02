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

                    "downloadUrl": "/bitrix/components/bitrix/crm.deal.show/show_file.php?auth=&fileId=10",
                    "urlMachine": "/bitrix/components/bitrix/crm.deal.show/show_file.php?auth=token&fileId=10",

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

            "https://example.bitrix24.com/bitrix/components/bitrix/crm.deal.show/show_file.php?auth=token&fileId=10",

        ),
        ("green-card.pdf", "https://cdn.example.test/green-card.pdf"),
    ]
