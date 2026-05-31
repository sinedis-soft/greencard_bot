from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.validation import is_latin_name, is_passport_number, normalize_passport

from app.schemas.vehicle import VehicleData


class PolicyholderType(str, Enum):
    individual = "individual"
    company = "company"


class VehicleType(str, Enum):
    car = "car"
    truck = "truck"
    bus = "bus"
    moto = "moto"
    trailer = "trailer"
    special = "special"


class EngineType(str, Enum):
    petrol = "petrol"
    diesel = "diesel"
    gas = "gas"
    gasoline = "gasoline"
    electric = "electric"
    hybrid = "hybrid"


class PowerUnit(str, Enum):
    hp = "hp"
    kw = "kw"


class CompanyData(BaseModel):
    company_name: str
    company_inn: Optional[str] = None
    company_country: str
    company_legal_address: str
    ceo_full_name: str
    ceo_title: str


class ApplicationCreate(BaseModel):
    @field_validator("first_name", "last_name")
    @classmethod
    def validate_latin_name(cls, value: str) -> str:
        normalized = value.strip()
        if not is_latin_name(normalized):
            raise ValueError("must contain only Latin letters, spaces and hyphens")
        return normalized

    @field_validator("passport_series_number")
    @classmethod
    def validate_passport_series_number(cls, value: str) -> str:
        normalized = normalize_passport(value)
        if not is_passport_number(normalized):
            raise ValueError("must contain only Latin letters and digits")
        return normalized

    first_name: str
    last_name: str
    phone: str
    email: EmailStr
    preferred_language: str
    policyholder_type: PolicyholderType
    birth_date: date
    registration_address: str
    passport_series_number: str
    vehicles: list[VehicleData] = Field(min_length=1)
    terms_accepted: bool
    privacy_accepted: bool
    company: Optional[CompanyData] = None
    telegram_init_data: str
