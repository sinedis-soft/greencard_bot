import hashlib
import hmac
import json
from urllib.parse import urlencode


def build_init_data(bot_token: str, user: dict) -> str:
    data = {"auth_date": "1710000000", "query_id": "AAEAAAE", "user": json.dumps(user, separators=(",", ":"))}
    dcs = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_models_exist():
    from app.db.models import Application, Vehicle, Policyholder, OperatorTicket, OperatorActionLog, UploadedDocument
    assert Application and Vehicle and Policyholder and OperatorTicket and OperatorActionLog and UploadedDocument


def test_multi_vehicle_payload_shape():
    from app.schemas.application import ApplicationCreate
    payload = ApplicationCreate(**{
        "first_name":"A","last_name":"B","phone":"+12345678901","email":"a@b.com","preferred_language":"ru","policyholder_type":"individual","birth_date":"1990-01-01","registration_address":"x","passport_series_number":"pp","terms_accepted":True,"privacy_accepted":True,
        "telegram_init_data":"x",
        "vehicles":[
            {"vehicle_country_registration":"GE","vehicle_type":"car","insurance_period_days":30,"insurance_start_date":"2026-01-01","license_plate":"AA","vin":"WVWZZZ1JZXW000001","brand_model":"m","manufacture_year":2020,"engine_type":"petrol","power_unit":"hp"},
            {"vehicle_country_registration":"GE","vehicle_type":"truck","insurance_period_days":60,"insurance_start_date":"2026-01-02","license_plate":"BB","vin":"WVWZZZ1JZXW000002","brand_model":"m2","manufacture_year":2021,"engine_type":"diesel","power_unit":"kw"}
        ]
    })
    assert len(payload.vehicles) == 2
