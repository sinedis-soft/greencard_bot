from pathlib import Path

import yaml

from app.schemas.application import ApplicationCreate, PolicyholderType
from app.services.bitrix24_client import Bitrix24Client, TELEGRAM_USERNAME_FIELD, TELEGRAM_USER_ID_FIELD


BITRIX_LANGUAGE_FIELD = "UF_CRM_1753957395750"
BITRIX_LANGUAGE_IDS = {
    "be": "3935",
    "by": "3935",
    "belarusian": "3935",
    "ru": "3937",
    "russian": "3937",
    "uk": "3939",
    "ua": "3939",
    "ukrainian": "3939",
    "ka": "3941",
    "ge": "3941",
    "georgian": "3941",
    "hy": "3943",
    "am": "3943",
    "armenian": "3943",
    "kk": "3945",
    "kz": "3945",
    "kazakh": "3945",
    "uz": "3947",
    "uzbek": "3947",
    "ky": "3949",
    "kg": "3949",
    "kyrgyz": "3949",
    "az": "3951",
    "azerbaijani": "3951",
    "en": "3953",
    "english": "3953",
    "pl": "3955",
    "polish": "3955",
    "tr": "3957",
    "turkish": "3957",
}


class LeadService:
    def __init__(self, bitrix_client: Bitrix24Client, mapping_file: Path):
        self.bitrix_client = bitrix_client
        self.mapping = yaml.safe_load(mapping_file.read_text(encoding="utf-8"))

    def create_application_leads(self, app_data: ApplicationCreate, telegram_username: str | None = None, telegram_user_id: int | None = None) -> dict:
        contact_payload = self._build_contact_payload(app_data, telegram_username, telegram_user_id)
        contact_id = self.bitrix_client.create_or_update_contact(contact_payload)

        company_id = None
        if app_data.policyholder_type == PolicyholderType.company and app_data.company:
            company_payload = self._build_company_payload(app_data)
            company_id = self.bitrix_client.create_or_update_company(company_payload)

        deals: list[int] = []
        for vehicle in app_data.vehicles:
            deal_payload = self._build_deal_payload(app_data, vehicle.model_dump(), contact_id, company_id)
            deals.append(self.bitrix_client.create_deal(deal_payload))
        return {"success": True, "contact_id": contact_id, "company_id": company_id, "deals": deals}

    def _build_contact_payload(self, app_data: ApplicationCreate, telegram_username: str | None = None, telegram_user_id: int | None = None) -> dict:
        field_map = self.mapping["contact"]
        data = app_data.model_dump()
        payload = {crm_key: data[local_key] for crm_key, local_key in field_map.items()}
        payload[BITRIX_LANGUAGE_FIELD] = self._bitrix_language_id(app_data.preferred_language)
        if telegram_username:
            payload[TELEGRAM_USERNAME_FIELD] = telegram_username
        if telegram_user_id:
            payload[TELEGRAM_USER_ID_FIELD] = telegram_user_id
        return payload

    def _build_company_payload(self, app_data: ApplicationCreate) -> dict:
        field_map = self.mapping["company"]
        company = app_data.company.model_dump() if app_data.company else {}
        data = {"company_title": self._company_title(app_data), "company_inn": company.get("company_inn", ""), "ceo_full_name": company.get("ceo_full_name", ""), "ceo_title": company.get("ceo_title", "")}
        return {crm_key: data.get(local_key, "") for crm_key, local_key in field_map.items()}

    def _build_deal_payload(self, app_data: ApplicationCreate, vehicle: dict, contact_id: int, company_id: int | None) -> dict:
        field_map = self.mapping["deal"]
        deal_data = {"deal_title": f"Lead {app_data.last_name} {app_data.first_name} {vehicle.get('license_plate', '')}".strip(), "contact_id": contact_id, "company_id": company_id, "comment": vehicle.get("comment", ""), **vehicle}
        payload = {crm_key: deal_data.get(local_key) for crm_key, local_key in field_map.items()}
        payload[BITRIX_LANGUAGE_FIELD] = self._bitrix_language_id(app_data.preferred_language)
        if vehicle.get("reuse_existing_vehicle_docs"):
            payload.pop("UF_CRM_1686154280439", None)
        payload.update(self.mapping.get("deal_defaults", {}))
        return payload

    def _bitrix_language_id(self, language: str) -> str:
        normalized = (language or "").strip().lower()
        return BITRIX_LANGUAGE_IDS.get(normalized, BITRIX_LANGUAGE_IDS["en"])

    def _company_title(self, app_data: ApplicationCreate) -> str:
        company_inn = (app_data.company.company_inn if app_data.company else "") or ""
        if company_inn:
            return f"Company {company_inn}"
        return f"Company {app_data.last_name} {app_data.first_name}"
