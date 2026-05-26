import json
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import Application, BitrixSyncJob
from app.db.session import SessionLocal

RETRY_DELAYS = [60, 300, 900]


class BitrixSyncService:
    def create_job(self, request_id: str, job_type: str, payload: dict) -> int:
        with SessionLocal() as db:
            job = BitrixSyncJob(request_id=request_id, job_type=job_type, payload_json=json.dumps(payload), status="bitrix_pending", attempts=0)
            db.add(job)
            app = db.scalar(select(Application).where(Application.request_id == request_id))
            if app:
                app.status = "bitrix_pending"
            db.commit()
            db.refresh(job)
            return job.id

    def mark_retrying(self, job_id: int, err: str, attempts: int):
        with SessionLocal() as db:
            job = db.get(BitrixSyncJob, job_id)
            if not job:
                return
            job.attempts = attempts
            job.last_error = err
            if attempts >= 3:
                job.status = "failed"
                job.next_retry_at = None
                app = db.scalar(select(Application).where(Application.request_id == job.request_id))
                if app:
                    app.status = "failed"
                    app.last_error = err
            else:
                job.status = "bitrix_retrying"
                job.next_retry_at = datetime.utcnow() + timedelta(seconds=RETRY_DELAYS[attempts - 1])
                app = db.scalar(select(Application).where(Application.request_id == job.request_id))
                if app:
                    app.status = "bitrix_retrying"
                    app.last_error = err
            db.commit()

    def mark_success(self, job_id: int):
        with SessionLocal() as db:
            job = db.get(BitrixSyncJob, job_id)
            if not job:
                return
            job.status = "bitrix_created"
            app = db.scalar(select(Application).where(Application.request_id == job.request_id))
            if app:
                app.status = "bitrix_created"
            db.commit()
