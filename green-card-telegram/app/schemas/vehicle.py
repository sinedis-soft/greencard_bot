from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class VehicleData(BaseModel):
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
