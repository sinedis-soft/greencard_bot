import hashlib
import hmac
import json
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from app.main import app


def build_init_data(bot_token: str, user: dict) -> str:
    data = {
        "auth_date": "1710000000",
        "query_id": "AAEAAAE",
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode(data)


def payload_template():
    return {
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
                "vehicle_docs": "meta",
            }
        ],
        "terms_accepted": True,
        "privacy_accepted": True,
    }


def test_reject_without_telegram_init_data(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    client = TestClient(app)
    payload = payload_template()
    response = client.post("/api/applications", json=payload)
    assert response.status_code == 422


def test_reject_with_invalid_signature(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    client = TestClient(app)
    payload = payload_template()
    payload["telegram_init_data"] = "user=%7B%22id%22%3A1%7D&hash=bad"
    response = client.post("/api/applications", json=payload)
    assert response.status_code == 400


def test_accept_with_valid_signature_and_no_telegram_to_bitrix(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "test-token")

    captured = {}

    def fake_create_or_update_contact(self, payload):
        captured["contact"] = payload
        return 11

    def fake_create_deal(self, payload):
        captured["deal"] = payload
        return 22

    monkeypatch.setattr("app.services.bitrix24_client.Bitrix24Client.create_or_update_contact", fake_create_or_update_contact)
    monkeypatch.setattr("app.services.bitrix24_client.Bitrix24Client.create_deal", fake_create_deal)

    client = TestClient(app)
    payload = payload_template()
    payload["telegram_init_data"] = build_init_data(
        "test-token",
        {"id": 12345, "username": "john", "language_code": "ru"},
    )
    response = client.post("/api/applications", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] is True

    serialized = json.dumps(captured)
    assert "telegram_user_id" not in serialized
    assert "username\"" not in serialized
