import json

from rq import Queue, Retry
from redis import Redis

from app.core.config import app_root
from app.schemas.application import ApplicationCreate
from app.services.application_service import ApplicationService
from app.services.bitrix24_client import Bitrix24Client
from app.services.bitrix_file_service import BitrixFileService
from app.services.bitrix_sync_service import BitrixSyncService
from app.services.lead_service import LeadService

redis_conn = Redis.from_url(__import__('os').getenv('REDIS_URL', 'redis://localhost:6379/0'))
queue = Queue('bitrix_sync', connection=redis_conn)


def process_bitrix_job(job_id: int):
    svc = BitrixSyncService()
    # find from DB each run
    from app.db.session import SessionLocal
    from app.db.models import BitrixSyncJob
    with SessionLocal() as db:
        job = db.get(BitrixSyncJob, job_id)
        if not job:
            return
        payload = json.loads(job.payload_json)
        try:
            client = Bitrix24Client(__import__('os').getenv('BITRIX24_WEBHOOK_URL', 'https://example.bitrix24.com/rest'))
            if job.job_type == 'create_application_leads':
                application_payload = payload.get('application', payload)
                bitrix = LeadService(client, app_root() / 'config' / 'bitrix_mapping.yaml').create_application_leads(
                    ApplicationCreate(**application_payload),
                    payload.get('telegram_username'),
                    payload.get('telegram_user_id'),
                )
                ApplicationService().mark_bitrix_created(
                    job.request_id,
                    bitrix.get('contact_id'),
                    bitrix.get('company_id'),
                    bitrix.get('deals', []),
                )
            elif job.job_type == 'create_contact':
                client.create_or_update_contact(payload)
            elif job.job_type == 'create_company':
                client.create_or_update_company(payload)
            elif job.job_type == 'create_deal':
                client.create_deal(payload)
            elif job.job_type == 'upload_file':
                BitrixFileService(client).upload_and_attach_to_deal(payload['deal_id'], payload['local_path'])
            elif job.job_type == 'timeline_comment':
                client.add_timeline_comment(payload['entity_type'], payload['entity_id'], payload['comment'])
            svc.mark_success(job_id)
        except Exception as exc:
            svc.mark_retrying(job_id, str(exc), job.attempts + 1)
            raise


def enqueue_bitrix_job(job_id: int):
    return queue.enqueue(process_bitrix_job, job_id, retry=Retry(max=3, interval=[60, 300, 900]))
