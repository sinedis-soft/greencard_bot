from __future__ import annotations

import base64
from pathlib import Path

from app.services.bitrix24_client import Bitrix24Client


BITRIX_DEAL_VEHICLE_DOCS_FIELD = "UF_CRM_1686154280439"


class BitrixFileService:
    def __init__(self, bitrix_client: Bitrix24Client):
        self.bitrix_client = bitrix_client

    def upload_and_attach_to_deal(self, deal_id: int, local_path: str) -> str:
        self.upload_and_attach_files_to_deal(deal_id, [local_path])
        return f"deal:{deal_id}:{Path(local_path).name}"

    def upload_and_attach_files_to_deal(self, deal_id: int, local_paths: list[str]) -> list[str]:
        files = [self._deal_file_payload(Path(local_path)) for local_path in local_paths]
        if not files:
            return []
        self.bitrix_client._post(
            "crm.deal.update",
            {
                "id": deal_id,
                "fields": {
                    BITRIX_DEAL_VEHICLE_DOCS_FIELD: files,
                },
            },
        )
        return [f"deal:{deal_id}:{Path(local_path).name}" for local_path in local_paths]

    def _deal_file_payload(self, path: Path) -> dict[str, list[str]]:
        return {"fileData": [path.name, base64.b64encode(path.read_bytes()).decode("ascii")]}
