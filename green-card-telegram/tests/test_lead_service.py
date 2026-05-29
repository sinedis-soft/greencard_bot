from pathlib import Path

from app.schemas.application import ApplicationCreate
from app.services.lead_service import BITRIX_LANGUAGE_FIELD, LeadService

MAPPING_FILE = Path(__file__).resolve().parents[1] / "app" / "config" / "bitrix_mapping.yaml"


class FakeBitrixClient:
    def __init__(self):
        self.contacts = []
        self.companies = []
        self.deals = []

    def create_or_update_contact(self, payload):
        self.contacts.append(payload)
        return 101

    def create_or_update_company(self, payload):
        self.companies.append(payload)
        return 201

    def create_deal(self, payload):
        self.deals.append(payload)
        return 300 + len(self.deals)


def application_payload(**overrides):
    payload = {
        "first_name": "Ivan",
        "last_name": "Petrov",
        "phone": "+995555000111",
        "email": "ivan@example.com",
        "preferred_language": "ru",
        "policyholder_type": "individual",
        "birth_date": "1990-05-12",
        "registration_address": "Addr",
        "passport_series_number": "AB123456",
        "vehicles": [
            {
                "vehicle_country_registration": "GE",
                "vehicle_type": "car",
                "insurance_period_days": 30,
                "insurance_start_date": "2026-07-01",
                "license_plate": "AA123BB",
                "vin": "WVWZZZ1JZXW000001",
                "brand_model": "VW",
                "manufacture_year": 2020,
                "engine_type": "petrol",
                "engine_capacity_cc": 1600,
                "engine_power": 110,
                "power_unit": "hp",
            },
            {
                "vehicle_country_registration": "PL",
                "vehicle_type": "truck",
                "insurance_period_days": 60,
                "insurance_start_date": "2026-07-02",
                "license_plate": "BB456CC",
                "vin": "WVWZZZ1JZXW000002",
                "brand_model": "MAN",
                "manufacture_year": 2021,
                "engine_type": "diesel",
                "engine_capacity_cc": 4000,
                "engine_power": 300,
                "power_unit": "hp",
            },
        ],
        "terms_accepted": True,
        "privacy_accepted": True,
        "telegram_init_data": "init-data",
    }
    payload.update(overrides)
    return ApplicationCreate(**payload)


def test_lead_service_creates_one_deal_per_vehicle():
    bitrix = FakeBitrixClient()
    service = LeadService(bitrix, MAPPING_FILE)

    result = service.create_application_leads(application_payload())

    assert result["contact_id"] == 101
    assert result["deals"] == [301, 302]
    assert len(bitrix.deals) == 2
    assert bitrix.deals[0]["UF_CRM_1686152485641"] == "AA123BB"
    assert bitrix.deals[1]["UF_CRM_1686152485641"] == "BB456CC"
    assert bitrix.deals[0][BITRIX_LANGUAGE_FIELD] == "3937"
    assert bitrix.deals[1][BITRIX_LANGUAGE_FIELD] == "3937"


def test_lead_service_maps_telegram_language_to_bitrix_enumeration_id():
    bitrix = FakeBitrixClient()
    service = LeadService(bitrix, MAPPING_FILE)

    service.create_application_leads(application_payload(preferred_language="ka"))

    assert bitrix.contacts[0][BITRIX_LANGUAGE_FIELD] == "3941"
    assert bitrix.deals[0][BITRIX_LANGUAGE_FIELD] == "3941"


def test_bitrix_client_flattens_nested_fields_for_bitrix_form_encoding():
    from app.services.bitrix24_client import Bitrix24Client

    payload = {
        "fields": {
            "NAME": "Ivan",
            "PHONE": [{"VALUE": "+995555000111", "VALUE_TYPE": "WORK"}],
        },
        "select": ["ID"],
    }

    assert Bitrix24Client("https://example.test/rest")._flatten_payload(payload) == [
        ("fields[NAME]", "Ivan"),
        ("fields[PHONE][0][VALUE]", "+995555000111"),
        ("fields[PHONE][0][VALUE_TYPE]", "WORK"),
        ("select[]", "ID"),
    ]


def test_lead_service_adds_telegram_fields_to_contact_payload():
    from app.services.bitrix24_client import TELEGRAM_USERNAME_FIELD, TELEGRAM_USER_ID_FIELD

    bitrix = FakeBitrixClient()
    service = LeadService(bitrix, MAPPING_FILE)

    service.create_application_leads(application_payload(), "john", 12345)

    assert bitrix.contacts[0][TELEGRAM_USERNAME_FIELD] == "john"
    assert bitrix.contacts[0][TELEGRAM_USER_ID_FIELD] == 12345


def test_bitrix_client_searches_existing_contact_by_email_before_create():
    from app.services.bitrix24_client import Bitrix24Client, TELEGRAM_USERNAME_FIELD, TELEGRAM_USER_ID_FIELD

    calls = []

    class Client(Bitrix24Client):
        def _post(self, method, payload):
            calls.append((method, payload))
            if method == "crm.contact.list" and payload["filter"].get("EMAIL") == "ivan@example.com":
                return {
                    "result": [
                        {
                            "ID": "77",
                            "EMAIL": [{"VALUE": "ivan@example.com"}],
                            "PHONE": [{"VALUE": "+995555000111"}],
                        }
                    ]
                }
            if method == "crm.contact.update":
                return {"result": True}
            raise AssertionError(f"unexpected Bitrix call {method}: {payload}")

    contact_id = Client("https://example.test/rest").create_or_update_contact(
        {
            "NAME": "Ivan",
            "PHONE_WORK": "+995555000111",
            "EMAIL_WORK": "ivan@example.com",
            TELEGRAM_USERNAME_FIELD: "john",
            TELEGRAM_USER_ID_FIELD: 12345,
        }
    )

    assert contact_id == 77
    assert calls[0] == ("crm.contact.list", {"filter": {"EMAIL": "ivan@example.com"}, "select": ["ID", "PHONE", "EMAIL", TELEGRAM_USERNAME_FIELD, TELEGRAM_USER_ID_FIELD]})
    assert calls[1][0] == "crm.contact.update"
    assert "EMAIL" not in calls[1][1]["fields"]
    assert "PHONE" not in calls[1][1]["fields"]
    assert calls[1][1]["fields"][TELEGRAM_USERNAME_FIELD] == "john"
    assert calls[1][1]["fields"][TELEGRAM_USER_ID_FIELD] == 12345


def test_bitrix_client_creates_contact_only_after_email_miss():
    from app.services.bitrix24_client import Bitrix24Client, TELEGRAM_USERNAME_FIELD

    calls = []

    class Client(Bitrix24Client):
        def _post(self, method, payload):
            calls.append((method, payload))
            if method == "crm.contact.list":
                return {"result": []}
            if method == "crm.contact.add":
                return {"result": 88}
            raise AssertionError(f"unexpected Bitrix call {method}: {payload}")

    contact_id = Client("https://example.test/rest").create_or_update_contact(
        {
            "NAME": "Ivan",
            "EMAIL_WORK": "ivan@example.com",
            TELEGRAM_USERNAME_FIELD: "john",
        }
    )

    assert contact_id == 88
    assert [method for method, _ in calls] == ["crm.contact.list", "crm.contact.add"]
    assert calls[0][1]["filter"] == {"EMAIL": "ivan@example.com"}


def test_bitrix_client_prefill_search_uses_telegram_username():
    from app.services.bitrix24_client import Bitrix24Client, TELEGRAM_USERNAME_FIELD, TELEGRAM_USER_ID_FIELD

    calls = []

    class Client(Bitrix24Client):
        def _post(self, method, payload):
            calls.append((method, payload))
            return {"result": [{"ID": "77", TELEGRAM_USERNAME_FIELD: "john", TELEGRAM_USER_ID_FIELD: "12345"}]}

    contact = Client("https://example.test/rest").find_contact_by_telegram_username("john")

    assert contact["ID"] == "77"
    assert calls == [
        (
            "crm.contact.list",
            {
                "filter": {TELEGRAM_USERNAME_FIELD: "john"},
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
            },
        )
    ]


def test_bitrix_client_vehicle_lookup_selects_contact_id_for_privacy_check():
    from app.services.bitrix24_client import Bitrix24Client

    calls = []

    class Client(Bitrix24Client):
        def _post(self, method, payload):
            calls.append((method, payload))
            return {"result": []}

    assert Client("https://example.test/rest").find_deal_by_license_plate("AA123BB") is None

    assert calls[0][0] == "crm.deal.list"
    assert "CONTACT_ID" in calls[0][1]["select"]
