from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.validation import is_license_plate, is_vin, normalize_license_plate, normalize_vin


class VehicleData(BaseModel):
    @field_validator("license_plate")
    @classmethod
    def validate_license_plate(cls, value: str) -> str:
        normalized = normalize_license_plate(value)
        if not is_license_plate(normalized):
            raise ValueError("must contain 3-8 Latin letters or digits")
        return normalized

    @field_validator("vin", mode="before")
    @classmethod
    def validate_vin(cls, value: object) -> str:
        normalized = normalize_vin(value)
        if not is_vin(normalized):
            raise ValueError("must contain exactly 17 Latin letters or digits excluding I, O and Q")
        return normalized

    vehicle_country_registration: str
    vehicle_type: str
    insurance_period_days: int = Field(gt=0)
    insurance_start_date: date
    license_plate: str
    vin: Optional[str] = None
    brand_model: str
    manufacture_year: int = Field(ge=1900)
    engine_type: str
    engine_capacity_cc: Optional[int] = Field(default=None, ge=0)
    engine_power: Optional[float] = Field(default=None, ge=0)
    power_unit: str
    vehicle_docs: Optional[str] = None
    reuse_existing_vehicle_docs: bool = False
