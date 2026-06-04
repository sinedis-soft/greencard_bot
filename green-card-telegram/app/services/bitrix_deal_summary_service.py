from __future__ import annotations

from app.core.config import get_settings
from app.services.bitrix24_client import Bitrix24Client
from app.services.bitrix_deal_mapper import safe_deal_card


class BitrixDealSummaryService:
    def __init__(self, bitrix_client: Bitrix24Client | None = None):
        self.bitrix_client = bitrix_client or Bitrix24Client(get_settings().bitrix24_webhook_url)

    def get_safe_summary(self, deal_id: int | str | None) -> dict:
        if not deal_id:
            return {}
        try:
            deal = self.bitrix_client.get_deal(deal_id)
        except RuntimeError:
            return {}
        return safe_deal_card(deal) if deal else {}

    def deal_url(self, deal_id: int | str | None) -> str:
        if not deal_id:
            return ""
        return self.bitrix_client.deal_url(deal_id)
