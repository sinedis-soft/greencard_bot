from app.services.bitrix24_client import Bitrix24Client


class BitrixFileService:
    def __init__(self, bitrix_client: Bitrix24Client):
        self.bitrix_client = bitrix_client

    def upload_and_attach_to_deal(self, deal_id: int, local_path: str) -> str:
        bitrix_file_id = self.bitrix_client.upload_file(local_path)
        self.bitrix_client.add_timeline_comment("deal", deal_id, f"File attached {bitrix_file_id}")
        return bitrix_file_id
