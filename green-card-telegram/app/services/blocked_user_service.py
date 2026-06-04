from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.db.models import BlockedTelegramUser
from app.db.session import SessionLocal


class BlockedUserService:
    def get_active_block(self, telegram_user_id: int) -> BlockedTelegramUser | None:
        now = datetime.utcnow()
        with SessionLocal() as db:
            block = db.scalar(
                select(BlockedTelegramUser).where(
                    BlockedTelegramUser.telegram_user_id == telegram_user_id,
                    (BlockedTelegramUser.blocked_until.is_(None)) | (BlockedTelegramUser.blocked_until > now),
                )
            )
            if block:
                db.expunge(block)
            return block

    def is_blocked(self, telegram_user_id: int) -> bool:
        return self.get_active_block(telegram_user_id) is not None

    def block_user(
        self,
        telegram_user_id: int,
        reason: str,
        blocked_until: datetime | None = None,
        blocked_by_operator_id: int | None = None,
    ) -> None:
        with SessionLocal() as db:
            existing = db.scalar(select(BlockedTelegramUser).where(BlockedTelegramUser.telegram_user_id == telegram_user_id))
            if existing:
                existing.reason = reason
                existing.blocked_until = blocked_until
                existing.blocked_by_operator_id = blocked_by_operator_id
            else:
                db.add(
                    BlockedTelegramUser(
                        telegram_user_id=telegram_user_id,
                        reason=reason,
                        blocked_until=blocked_until,
                        blocked_by_operator_id=blocked_by_operator_id,
                    )
                )
            db.commit()
