from __future__ import annotations

import hashlib
import hmac
import os


def normalize_phone(phone: str | None) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def normalize_plate(plate: str | None) -> str:
    return (plate or "").replace(" ", "").replace("-", "").upper()


def normalize_vin(vin: str | None) -> str:
    return (vin or "").replace(" ", "").upper()


def pii_hash(value: str, secret: str | None = None) -> str:
    secret_value = secret or os.getenv("PII_HASH_SECRET") or os.getenv("APP_SECRET") or "dev-insecure-pii-hash-secret"
    return hmac.new(secret_value.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_optional(value: str | None, normalizer, secret: str | None = None) -> str | None:
    normalized = normalizer(value)
    if not normalized:
        return None
    return pii_hash(normalized, secret)
