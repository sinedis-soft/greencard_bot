from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import ApplicationDuplicateIndex
from app.db.session import SessionLocal
from app.services.pii_hashing import hash_optional, normalize_email, normalize_phone, normalize_plate, normalize_vin

ACTIVE_DUPLICATE_STATUSES = ("draft", "submitted", "bitrix_pending", "bitrix_created", "waiting_payment", "in_progress")


@dataclass(frozen=True)
class DuplicateHashes:
    phone_hash: str | None
    email_hash: str | None
    plate_hash: str | None
    vin_hash: str | None


@dataclass(frozen=True)
class DuplicateCheckResult:
    level: str
    reason: str | None = None
    duplicate: ApplicationDuplicateIndex | None = None

    @property
    def found(self) -> bool:
        return self.level != "none"

    @property
    def hard_block(self) -> bool:
        return self.level == "hard"


def build_duplicate_hashes(payload, secret: str | None = None) -> DuplicateHashes:
    first_vehicle = (getattr(payload, "vehicles", None) or [None])[0]
    return DuplicateHashes(
        phone_hash=hash_optional(getattr(payload, "phone", None), normalize_phone, secret),
        email_hash=hash_optional(str(getattr(payload, "email", "") or ""), normalize_email, secret),
        plate_hash=hash_optional(getattr(first_vehicle, "license_plate", None), normalize_plate, secret),
        vin_hash=hash_optional(getattr(first_vehicle, "vin", None), normalize_vin, secret),
    )


class DuplicateCheckService:
    def __init__(self, secret: str | None = None) -> None:
        self.secret = secret

    def build_hashes(self, payload) -> DuplicateHashes:
        return build_duplicate_hashes(payload, self.secret)

    def check_local(self, telegram_user_id: int, hashes: DuplicateHashes, window_hours: int = 24) -> DuplicateCheckResult:
        window_from = datetime.utcnow() - timedelta(hours=window_hours)
        with SessionLocal() as db:
            base = (
                select(ApplicationDuplicateIndex)
                .where(
                    ApplicationDuplicateIndex.created_at >= window_from,
                    ApplicationDuplicateIndex.status.in_(ACTIVE_DUPLICATE_STATUSES),
                )
                .order_by(ApplicationDuplicateIndex.created_at.desc())
            )
            if hashes.vin_hash:
                item = db.scalar(base.where(ApplicationDuplicateIndex.vin_hash == hashes.vin_hash))
                if item:
                    db.expunge(item)
                    return DuplicateCheckResult("hard", "duplicate_vin", item)
            if hashes.plate_hash:
                item = db.scalar(base.where(ApplicationDuplicateIndex.plate_hash == hashes.plate_hash))
                if item:
                    db.expunge(item)
                    return DuplicateCheckResult("medium", "duplicate_plate", item)
            item = db.scalar(base.where(ApplicationDuplicateIndex.telegram_user_id == telegram_user_id))
            if item:
                db.expunge(item)
                return DuplicateCheckResult("soft", "active_application", item)
        return DuplicateCheckResult("none")

    def index_application(
        self,
        application_id: int | None,
        telegram_user_id: int,
        payload,
        status: str = "submitted",
        bitrix_deal_id: int | None = None,
        ttl_hours: int = 72,
    ) -> None:
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        base_hashes = self.build_hashes(payload)
        vehicles = getattr(payload, "vehicles", None) or [None]
        with SessionLocal() as db:
            for vehicle in vehicles:
                hashes = DuplicateHashes(
                    phone_hash=base_hashes.phone_hash,
                    email_hash=base_hashes.email_hash,
                    plate_hash=hash_optional(getattr(vehicle, "license_plate", None), normalize_plate, self.secret),
                    vin_hash=hash_optional(getattr(vehicle, "vin", None), normalize_vin, self.secret),
                )
                db.add(
                    ApplicationDuplicateIndex(
                        application_id=application_id,
                        telegram_user_id=telegram_user_id,
                        phone_hash=hashes.phone_hash,
                        email_hash=hashes.email_hash,
                        plate_hash=hashes.plate_hash,
                        vin_hash=hashes.vin_hash,
                        bitrix_deal_id=bitrix_deal_id,
                        status=status,
                        expires_at=expires_at,
                    )
                )
            db.commit()

    def update_application_status(self, application_id: int | None, status: str, bitrix_deal_id: int | None = None) -> None:
        if application_id is None:
            return
        with SessionLocal() as db:
            items = list(db.scalars(select(ApplicationDuplicateIndex).where(ApplicationDuplicateIndex.application_id == application_id)))
            for item in items:
                item.status = status
                if bitrix_deal_id is not None:
                    item.bitrix_deal_id = bitrix_deal_id
            db.commit()
