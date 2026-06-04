from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.db.models import Tariff, TariffChangeLog
from app.db.session import SessionLocal


def _parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _tariff_to_dict(tariff: Tariff) -> dict[str, Any]:
    return {
        "id": tariff.id,
        "product_type": tariff.product_type,
        "vehicle_type": tariff.vehicle_type,
        "insurance_period_days": tariff.insurance_period_days,
        "price": float(tariff.price),
        "currency": tariff.currency,
        "valid_from": tariff.valid_from.isoformat(),
        "valid_to": tariff.valid_to.isoformat() if tariff.valid_to else None,
        "is_active": tariff.is_active,
        "created_at": tariff.created_at.isoformat() if tariff.created_at else None,
        "updated_at": tariff.updated_at.isoformat() if tariff.updated_at else None,
    }


class TariffAdminService:
    def list_tariffs(self, active_only: bool = False) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(Tariff).order_by(Tariff.product_type, Tariff.vehicle_type, Tariff.insurance_period_days, Tariff.valid_from.desc())
            if active_only:
                stmt = stmt.where(Tariff.is_active == True)
            return [_tariff_to_dict(item) for item in db.scalars(stmt)]

    def find_active(self, product_type: str, vehicle_type: str, insurance_period_days: int, on_date: date | None = None) -> dict[str, Any] | None:
        today = on_date or date.today()
        with SessionLocal() as db:
            tariff = db.scalar(
                select(Tariff)
                .where(
                    Tariff.product_type == product_type,
                    Tariff.vehicle_type == vehicle_type,
                    Tariff.insurance_period_days == insurance_period_days,
                    Tariff.is_active == True,
                    Tariff.valid_from <= today,
                    (Tariff.valid_to.is_(None)) | (Tariff.valid_to >= today),
                )
                .order_by(Tariff.valid_from.desc())
            )
            return _tariff_to_dict(tariff) if tariff else None

    def create_tariff(self, data: dict, admin_user_id: int | None = None) -> dict[str, Any]:
        with SessionLocal() as db:
            tariff = Tariff(
                product_type=str(data.get("product_type") or "green_card"),
                vehicle_type=str(data["vehicle_type"]),
                insurance_period_days=int(data["insurance_period_days"]),
                price=Decimal(str(data["price"])),
                currency=str(data.get("currency") or "EUR"),
                valid_from=_parse_date(data["valid_from"]),
                valid_to=_parse_date(data.get("valid_to")),
                is_active=bool(data.get("is_active", True)),
            )
            db.add(tariff)
            db.flush()
            db.add(TariffChangeLog(tariff_id=tariff.id, admin_user_id=admin_user_id, old_value_json=None, new_value_json=json.dumps(_tariff_to_dict(tariff), ensure_ascii=False)))
            db.commit()
            db.refresh(tariff)
            return _tariff_to_dict(tariff)

    def update_tariff(self, tariff_id: int, data: dict, admin_user_id: int | None = None) -> dict[str, Any] | None:
        with SessionLocal() as db:
            tariff = db.get(Tariff, tariff_id)
            if not tariff:
                return None
            old = _tariff_to_dict(tariff)
            for key in ("product_type", "vehicle_type", "currency"):
                if key in data:
                    setattr(tariff, key, str(data[key]))
            if "insurance_period_days" in data:
                tariff.insurance_period_days = int(data["insurance_period_days"])
            if "price" in data:
                tariff.price = Decimal(str(data["price"]))
            if "valid_from" in data:
                tariff.valid_from = _parse_date(data["valid_from"])
            if "valid_to" in data:
                tariff.valid_to = _parse_date(data.get("valid_to"))
            if "is_active" in data:
                tariff.is_active = bool(data["is_active"])
            tariff.updated_at = datetime.utcnow()
            db.flush()
            db.add(TariffChangeLog(tariff_id=tariff.id, admin_user_id=admin_user_id, old_value_json=json.dumps(old, ensure_ascii=False), new_value_json=json.dumps(_tariff_to_dict(tariff), ensure_ascii=False)))
            db.commit()
            db.refresh(tariff)
            return _tariff_to_dict(tariff)

    def set_active(self, tariff_id: int, is_active: bool, admin_user_id: int | None = None) -> dict[str, Any] | None:
        return self.update_tariff(tariff_id, {"is_active": is_active}, admin_user_id)
