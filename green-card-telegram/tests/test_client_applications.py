from app.services.bitrix24_client import (
    LICENSE_PLATE_FIELD,
    POLICY_FILES_FIELD,
    POLICY_NUMBER_FIELD,
    POLICY_STATUS_FIELD,
    REQUEST_ID_FIELD,
    SHOW_IN_TELEGRAM_FIELD,
)
from app.services.bitrix_deal_mapper import safe_deal_card
from app.utils.masking import mask_plate


def test_mask_plate_keeps_only_safe_edges():
    assert mask_plate("AM123AB") == "AM***AB"
    assert mask_plate("ABC123") == "AB***23"
    assert mask_plate("123AB") == "1***B"
    assert mask_plate("AB") == "***"
    assert mask_plate(None) is None


def test_safe_deal_card_masks_private_fields_and_maps_status():
    card = safe_deal_card(
        {
            "ID": "52581",
            "TITLE": "Internal title should not expose VIN",
            REQUEST_ID_FIELD: "GC-2026-000123",
            "DATE_CREATE": "2026-06-04T10:30:00",
            LICENSE_PLATE_FIELD: "AM123AB",
            "UF_CRM_1686152149204": "2026-06-15",
            "UF_CRM_1686152209741": "30",
            POLICY_STATUS_FIELD: "2607",
        }
    )

    assert card == {
        "deal_id": 52581,
        "request_number": "GC-2026-000123",
        "product_type": "Green Card",
        "vehicle_plate_masked": "AM***AB",
        "insurance_start_date": "2026-06-15",
        "insurance_period_days": 30,
        "vehicle_type": None,
        "public_status": "Действующий",
        "created_at": "2026-06-04T10:30:00",
        "actions": {
            "open": True,
            "contact_operator": True,
            "upload_payment": False,
            "get_policy": True,
            "repeat": False,
            "policy_status": True,
        },
    }


def test_bitrix_client_lists_only_safe_deal_fields_with_visibility_filter():
    from app.services.bitrix24_client import Bitrix24Client

    calls = []

    class Client(Bitrix24Client):
        def _post(self, method, payload):
            calls.append((method, payload))
            return {"result": [{"ID": "1"}, {"ID": "2"}]}

    deals = Client("https://example.test/rest").list_deals_by_contact_id(77, limit=1)

    assert deals == [{"ID": "1"}]
    assert calls[0][0] == "crm.deal.list"
    assert calls[0][1]["filter"] == {"CONTACT_ID": "77", SHOW_IN_TELEGRAM_FIELD: "1"}
    assert calls[0][1]["order"] == {"DATE_CREATE": "DESC", "ID": "DESC"}
    assert "VIN" not in calls[0][1]["select"]
    assert LICENSE_PLATE_FIELD in calls[0][1]["select"]


def test_repeat_mapper_builds_new_deal_from_old_deal_without_local_private_storage():
    from app.services.bitrix24_client import (
        DOCS_REUSE_REQUESTED_FIELD,
        REPEAT_FROM_DEAL_FIELD,
        REQUEST_ID_FIELD,
        SHOW_IN_TELEGRAM_FIELD,
        TELEGRAM_CHAT_ID_FIELD,
    )
    from app.services.repeat_deal_mapper import (
        BRAND_MODEL_FIELD,
        COUNTRY_FIELD,
        INSURANCE_PERIOD_FIELD,
        INSURANCE_START_FIELD,
        VEHICLE_TYPE_FIELD,
        VIN_FIELD,
        build_repeat_deal_payload,
        repeat_available,
    )

    old_deal = {
        "ID": "52581",
        "CONTACT_ID": "77",
        "COMPANY_ID": "88",
        SHOW_IN_TELEGRAM_FIELD: "1",
        COUNTRY_FIELD: "529",
        VEHICLE_TYPE_FIELD: "127",
        LICENSE_PLATE_FIELD: "AM123AB",
        VIN_FIELD: "WVWZZZ1JZXW000001",
        BRAND_MODEL_FIELD: "VW Golf",
    }

    assert repeat_available(old_deal) is True
    payload = build_repeat_deal_payload(
        old_deal=old_deal,
        request_id="rep-public-1",
        new_start_date="2026-07-20",
        new_period_days=30,
        docs_mode="reuse",
        telegram_chat_id=5982080132,
    )

    assert payload["CONTACT_ID"] == "77"
    assert payload["COMPANY_ID"] == "88"
    assert payload[REQUEST_ID_FIELD] == "rep-public-1"
    assert payload[SHOW_IN_TELEGRAM_FIELD] == "1"
    assert payload[REPEAT_FROM_DEAL_FIELD] == "52581"
    assert payload[DOCS_REUSE_REQUESTED_FIELD] == "1"
    assert payload[TELEGRAM_CHAT_ID_FIELD] == 5982080132
    assert payload[INSURANCE_START_FIELD] == "2026-07-20"
    assert payload[INSURANCE_PERIOD_FIELD] == 30
    assert payload[LICENSE_PLATE_FIELD] == "AM123AB"
    assert payload[VIN_FIELD] == "WVWZZZ1JZXW000001"
    assert "AM***AB" in payload["TITLE"]
    assert "Клиент просит использовать документы" in payload["COMMENTS"]


def test_repeat_mapper_blocks_hidden_and_cancelled_deals():
    from app.services.bitrix24_client import POLICY_STATUS_FIELD, SHOW_IN_TELEGRAM_FIELD
    from app.services.repeat_deal_mapper import COUNTRY_FIELD, VEHICLE_TYPE_FIELD, repeat_available

    base = {COUNTRY_FIELD: "529", VEHICLE_TYPE_FIELD: "127", LICENSE_PLATE_FIELD: "AM123AB"}
    assert repeat_available({**base, SHOW_IN_TELEGRAM_FIELD: "0"}) is False
    assert repeat_available({**base, POLICY_STATUS_FIELD: "2609"}) is False
    assert repeat_available({**base, "STAGE_ID": "LOSE"}) is False

def test_policy_status_ready_returns_get_policy_action():
    from app.services.policy_status_mapper import build_policy_client_message, policy_status_actions, public_policy_status

    deal = {POLICY_FILES_FIELD: [{"id": 1}], POLICY_NUMBER_FIELD: "PL123"}
    card = {"request_number": "GC-2026-000456"}

    assert public_policy_status("2607", True) == "Полис готов."
    assert "Полис готов" in build_policy_client_message(deal, card, "2607", True, False, type("T", (), {"created": False, "already_open": False})())
    assert policy_status_actions(deal, has_policy_file=True, is_delayed=False)["get_policy"] is True


def test_policy_status_delay_and_ticket_rules_without_policy_file():
    from datetime import datetime, timedelta, timezone

    from app.services.policy_status_mapper import detect_policy_delay, should_create_policy_ticket

    delayed_deal = {
        "DATE_CREATE": (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat(),
        "STAGE_ID": "ISSUING",
        POLICY_STATUS_FIELD: "2611",
    }
    waiting_payment_deal = {
        "DATE_CREATE": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "STAGE_ID": "WAITING_PAYMENT",
    }
    numbered_without_file = {POLICY_NUMBER_FIELD: "PL123"}

    assert detect_policy_delay(delayed_deal, has_policy_file=False) is True
    assert should_create_policy_ticket(delayed_deal, has_policy_file=False, is_delayed=True) is True
    assert detect_policy_delay(waiting_payment_deal, has_policy_file=False) is False
    assert should_create_policy_ticket(waiting_payment_deal, has_policy_file=False, is_delayed=False) is False
    assert should_create_policy_ticket(numbered_without_file, has_policy_file=False, is_delayed=False) is True
