from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import or_, select

from app.db.models import AnalyticsEvent, Application, BitrixSyncJob, OperatorActionLog, OperatorTicket
from app.db.session import SessionLocal
from app.services.storage_cleanup import remove_request_storage

APPLICATION_FILE_RETENTION = timedelta(hours=72)
OPERATIONAL_DATA_RETENTION = timedelta(days=90)


class DataRetentionService:
    def __init__(self, storage_base_path: Path | None = None) -> None:
        self.storage_base_path = storage_base_path or Path("storage/applications")

    def cleanup_transferred_application_files(self, now: datetime | None = None) -> int:
        cutoff = (now or datetime.utcnow()) - APPLICATION_FILE_RETENTION
        removed = 0
        with SessionLocal() as db:
            request_ids = list(
                db.scalars(
                    select(Application.request_id).where(
                        Application.status == "bitrix_created",
                        Application.updated_at <= cutoff,
                    )
                )
            )

        for request_id in request_ids:
            if remove_request_storage(self.storage_base_path, request_id):
                removed += 1
        return removed

    def cleanup_old_operational_data(self, now: datetime | None = None) -> dict[str, int]:
        cutoff = (now or datetime.utcnow()) - OPERATIONAL_DATA_RETENTION
        with SessionLocal() as db:
            operator_logs_anonymized = (
                db.query(OperatorActionLog)
                .filter(OperatorActionLog.created_at <= cutoff, OperatorActionLog.message != "")
                .update({OperatorActionLog.message: ""}, synchronize_session=False)
            )
            operator_tickets_deleted = db.query(OperatorTicket).filter(OperatorTicket.updated_at <= cutoff).delete(synchronize_session=False)
            analytics_deleted = db.query(AnalyticsEvent).filter(AnalyticsEvent.created_at <= cutoff).delete(synchronize_session=False)
            sync_jobs_deleted = (
                db.query(BitrixSyncJob)
                .filter(
                    BitrixSyncJob.updated_at <= cutoff,
                    BitrixSyncJob.status.in_(("bitrix_created", "failed")),
                )
                .delete(synchronize_session=False)
            )
            application_errors_cleared = (
                db.query(Application)
                .filter(
                    Application.updated_at <= cutoff,
                    Application.last_error.is_not(None),
                    or_(Application.status == "bitrix_created", Application.status == "failed"),
                )
                .update({Application.last_error: None}, synchronize_session=False)
            )
            db.commit()

        return {
            "operator_logs_anonymized": operator_logs_anonymized,
            "operator_tickets_deleted": operator_tickets_deleted,
            "analytics_deleted": analytics_deleted,
            "sync_jobs_deleted": sync_jobs_deleted,
            "application_errors_cleared": application_errors_cleared,
        }
