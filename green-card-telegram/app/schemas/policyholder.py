from pydantic import BaseModel


class PolicyholderData(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: str
    preferred_language: str
    birth_date: str
    registration_address: str
    passport_series_number: str
