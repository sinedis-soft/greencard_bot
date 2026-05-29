from pathlib import Path

import yaml

from app.schemas.application import ApplicationCreate, PolicyholderType
from app.services.bitrix24_client import Bitrix24Client, TELEGRAM_USERNAME_FIELD, TELEGRAM_USER_ID_FIELD


BITRIX_LANGUAGE_FIELD = "UF_CRM_1753957395750"

BITRIX_COUNTRY_REGISTRATION_IDS = {
    "529": "529",
    "armenia": "529",
    "армения": "529",
    "am": "529",
    "531": "531",
    "azerbaijan": "531",
    "азербайджан": "531",
    "az": "531",
    "123": "123",
    "belarus": "123",
    "беларусь": "123",
    "by": "123",
    "517": "517",
    "estonia": "517",
    "эстония": "517",
    "ee": "517",
    "523": "523",
    "georgia": "523",
    "грузия": "523",
    "ge": "523",
    "385": "385",
    "kazakhstan": "385",
    "казахстан": "385",
    "kz": "385",
    "527": "527",
    "kyrgyzstan": "527",
    "кыргызстан": "527",
    "kg": "527",
    "515": "515",
    "latvia": "515",
    "латвия": "515",
    "lv": "515",
    "513": "513",
    "lithuania": "513",
    "литва": "513",
    "lt": "513",
    "521": "521",
    "moldova": "521",
    "молдова": "521",
    "md": "521",
    "383": "383",
    "mongolia": "383",
    "монголия": "383",
    "mn": "383",
    "247": "247",
    "poland": "247",
    "польша": "247",
    "pl": "247",
    "125": "125",
    "russia": "125",
    "россия": "125",
    "ru": "125",
    "1103": "1103",
    "czech": "1103",
    "czechia": "1103",
    "чехия": "1103",
    "cz": "1103",
    "2253": "2253",
    "turkey": "2253",
    "турция": "2253",
    "tr": "2253",
    "519": "519",
    "ukraine": "519",
    "украина": "519",
    "ua": "519",
    "525": "525",
    "uzbekistan": "525",
    "узбекистан": "525",
    "uz": "525",
    "411": "411",
    "other country": "411",
    "другая страна": "411",
    "сша": "411",
    "usa": "411",
    "united states": "411",
    "великобритания": "411",
    "united kingdom": "411",
}

BITRIX_VEHICLE_TYPE_IDS = {
    "127": "127",
    "car": "127",
    "passenger car": "127",
    "легковой": "127",
    "легковой автомобиль": "127",
    "129": "129",
    "trailer": "129",
    "passenger car trailer": "129",
    "прицеп": "129",
    "прицеп к легковому автомобилю": "129",
    "131": "131",
    "bus": "131",
    "автобус": "131",
    "217": "217",
    "moto": "217",
    "motorbike": "217",
    "motorcycle": "217",
    "мотоцикл": "217",
    "249": "249",
    "truck tractor": "249",
    "тягач": "249",
    "251": "251",
    "cargo semi-trailer": "251",
    "грузовой полуприцеп": "251",
    "457": "457",
    "special": "457",
    "special motor vehicles": "457",
    "спецтехника": "457",
    "453": "453",
    "truck": "453",
    "грузовой": "453",
    "грузовой автомобиль": "453",
    "1203": "1203",
    "camper": "1203",
    "кемпер": "1203",
}

BITRIX_ENGINE_TYPE_IDS = {
    "133": "133",
    "petrol": "133",
    "бензин": "133",
    "135": "135",
    "diesel": "135",
    "дизель": "135",
    "137": "137",
    "gas": "137",
    "gasoline": "137",
    "газ / бензин": "137",
    "газ/бензин": "137",
    "139": "139",
    "electric": "139",
    "электро": "139",
    "141": "141",
    "hybrid": "141",
    "гибрид": "141",
}

BITRIX_POWER_UNIT_IDS = {
    "145": "145",
    "kw": "145",
    "киловат": "145",
    "киловатты": "145",
    "147": "147",
    "hp": "147",
    "лошадиные силы": "147",
}

BITRIX_ENUM_FIELDS = {
    "UF_CRM_1686152306664": BITRIX_COUNTRY_REGISTRATION_IDS,
    "UF_CRM_1686152567597": BITRIX_VEHICLE_TYPE_IDS,
    "UF_CRM_1686152745455": BITRIX_ENGINE_TYPE_IDS,
    "UF_CRM_1686152902186": BITRIX_POWER_UNIT_IDS,
}

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
        payload = {crm_key: self._normalize_deal_field(crm_key, deal_data.get(local_key)) for crm_key, local_key in field_map.items()}
        payload[BITRIX_LANGUAGE_FIELD] = self._bitrix_language_id(app_data.preferred_language)
        # Vehicle documents are Bitrix file fields. They are uploaded after deal creation
        # via BitrixFileService, so do not send textual Telegram/API metadata here.
        payload.pop("UF_CRM_1686154280439", None)
        payload.update(self.mapping.get("deal_defaults", {}))
        return payload

    def _normalize_deal_field(self, crm_key: str, value: object) -> object:
        enum_map = BITRIX_ENUM_FIELDS.get(crm_key)
        if not enum_map or value in (None, ""):
            return value
        normalized = str(value).strip().lower()
        candidates = [normalized]
        if "(" in normalized:
            candidates.append(normalized.split("(", 1)[0].strip())
            if ")" in normalized:
                candidates.append(normalized.split("(", 1)[1].split(")", 1)[0].strip())
        if "," in normalized:
            candidates.extend(part.strip() for part in normalized.split(","))
        for candidate in candidates:
            if candidate in enum_map:
                return enum_map[candidate]
        return value

    def _bitrix_language_id(self, language: str) -> str:
        normalized = (language or "").strip().lower()
        return BITRIX_LANGUAGE_IDS.get(normalized, BITRIX_LANGUAGE_IDS["en"])

    def _company_title(self, app_data: ApplicationCreate) -> str:
        company_inn = (app_data.company.company_inn if app_data.company else "") or ""
        if company_inn:
            return f"Company {company_inn}"
        return f"Company {app_data.last_name} {app_data.first_name}"
