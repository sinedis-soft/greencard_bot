from pathlib import Path

import yaml


class CalculatorService:
    def __init__(self, tariffs_file: Path):
        self._tariffs = yaml.safe_load(tariffs_file.read_text(encoding="utf-8"))

    def estimate(self, vehicle_type: str, insurance_period_days: int) -> dict:
        tariffs = self._tariffs.get("tariffs", {})
        vehicle_tariffs = tariffs.get(vehicle_type, {})
        key = str(insurance_period_days)
        estimated_price = vehicle_tariffs.get(key)
        if estimated_price is None:
            estimated_price = vehicle_tariffs.get("default", 0)

        return {
            "estimated_price": estimated_price,
            "currency": self._tariffs.get("currency", "USD"),
            "disclaimer": self._tariffs.get("disclaimer", ""),
        }
