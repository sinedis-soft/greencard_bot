from pathlib import Path

import yaml

from app.services.tariff_admin_service import TariffAdminService


class CalculatorService:
    def __init__(self, tariffs_file: Path):
        self._tariffs = yaml.safe_load(tariffs_file.read_text(encoding="utf-8"))

    def estimate(self, vehicle_type: str, insurance_period_days: int) -> dict:
        db_tariff = self._estimate_from_db(vehicle_type, insurance_period_days)
        if db_tariff:
            return db_tariff

        tariffs = self._tariffs.get("tariffs", {})
        vehicle_tariffs = tariffs.get(vehicle_type, {})
        key = str(insurance_period_days)
        estimated_price = vehicle_tariffs.get(key)
        if estimated_price is None:
            estimated_price = vehicle_tariffs.get("default", 0)

        return {
            "estimated_price": self._available_price(estimated_price),
            "currency": self._tariffs.get("currency", "USD"),
            "currency_symbol": self._tariffs.get("currency_symbol", ""),
            "disclaimer": self._tariffs.get("disclaimer", ""),
        }

    def _estimate_from_db(self, vehicle_type: str, insurance_period_days: int) -> dict | None:
        try:
            tariff = TariffAdminService().find_active(
                product_type="border_insurance",
                vehicle_type=vehicle_type,
                insurance_period_days=insurance_period_days,
            )
        except Exception:
            tariff = None
        if not tariff:
            return None
        return {
            "estimated_price": self._available_price(tariff["price"]),
            "currency": tariff["currency"],
            "currency_symbol": self._tariffs.get("currency_symbol", ""),
            "disclaimer": self._tariffs.get("disclaimer", ""),
        }

    def _available_price(self, value) -> float | int | None:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if numeric <= 0:
            return None
        return value
