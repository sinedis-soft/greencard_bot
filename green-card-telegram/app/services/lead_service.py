from pathlib import Path

import yaml

from app.schemas.application import ApplicationCreate, PolicyholderType
from app.services.bitrix24_client import Bitrix24Client


class LeadService:
    def __init__(self, bitrix_client: Bitrix24Client, mapping_file: Path):
        self.bitrix_client = bitrix_client
        self.mapping = yaml.safe_load(mapping_file.read_text(encoding="utf-8"))

    def create_application_leads(self, app_data: ApplicationCreate) -> dict:
        contact_payload = self._build_contact_payload(app_data)
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

    def _build_contact_payload(self, app_data: ApplicationCreate) -> dict:
        field_map = self.mapping["contact"]
        data = app_data.model_dump()
        return {crm_key: data[local_key] for crm_key, local_key in field_map.items()}

    def _build_company_payload(self, app_data: ApplicationCreate) -> dict:
        field_map = self.mapping["company"]
        company = app_data.company.model_dump() if app_data.company else {}
        data = {"company_title": self._company_title(app_data), "company_inn": company.get("company_inn", ""), "ceo_full_name": company.get("ceo_full_name", ""), "ceo_title": company.get("ceo_title", "")}
        return {crm_key: data.get(local_key, "") for crm_key, local_key in field_map.items()}

    def _build_deal_payload(self, app_data: ApplicationCreate, vehicle: dict, contact_id: int, company_id: int | None) -> dict:
        field_map = self.mapping["deal"]
        deal_data = {"deal_title": f"Lead {app_data.last_name} {app_data.first_name} {vehicle.get('license_plate', '')}".strip(), "contact_id": contact_id, "company_id": company_id, "comment": vehicle.get("comment", ""), **vehicle}
        payload = {crm_key: deal_data.get(local_key) for crm_key, local_key in field_map.items()}
        if vehicle.get("reuse_existing_vehicle_docs"):
            payload.pop("UF_CRM_1686154280439", None)
        payload.update(self.mapping.get("deal_defaults", {}))
        return payload

    def _company_title(self, app_data: ApplicationCreate) -> str:
        company_inn = (app_data.company.company_inn if app_data.company else "") or ""
        if company_inn:
            return f"Company {company_inn}"
        return f"Company {app_data.last_name} {app_data.first_name}"
