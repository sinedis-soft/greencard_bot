import json
import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.security import ensure_consents
from app.db.models import UploadedDocument, Vehicle
from app.db.session import SessionLocal
from app.schemas.application import ApplicationCreate
from app.services.analytics_service import AnalyticsService
from app.services.application_service import ApplicationService
from app.services.bitrix24_client import Bitrix24Client
from app.services.bitrix_file_service import BitrixFileService
from app.services.bitrix_sync_service import BitrixSyncService
from app.services.calculator_service import CalculatorService
from app.services.file_storage_service import FileStorageService, FileValidationError, MAX_FILES
from app.services.lead_service import LeadService
from app.services.telegram_auth_service import TelegramAuthError, TelegramAuthService
from app.workers.bitrix_retry_worker import enqueue_bitrix_job

router = APIRouter(prefix="/api/applications", tags=["applications"])
logger = logging.getLogger(__name__)


@router.post("")
async def create_application(application_json: str = Form(...), vehicle_docs: list[UploadFile] = File(default=[])) -> dict:
    payload = ApplicationCreate(**json.loads(application_json))
    analytics = AnalyticsService()
    analytics.track("application_submit_attempt", payload=payload.model_dump(mode="json"))
    analytics.track("miniapp_opened", telegram_user_id=None, payload={"source":"miniapp"})

    ensure_consents(payload.terms_accepted, payload.privacy_accepted)
    if len(vehicle_docs) > MAX_FILES:
        raise HTTPException(status_code=400, detail="too_many_files")

    try:
        tg = TelegramAuthService(__import__("os").getenv("BOT_TOKEN", "")).validate_init_data(payload.telegram_init_data)
    except TelegramAuthError as exc:
        analytics.track("application_submit_failed", payload={"error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    app_service = ApplicationService()
    local_app, is_duplicate = app_service.create_local(payload, tg.telegram_user_id, tg.username, tg.language_code)
    request_id = local_app.request_id
    logger.info("application_received request_id=%s", request_id)

    if is_duplicate:
        logger.info("application_duplicate request_id=%s", request_id)
        analytics.track("application_submitted", request_id=request_id, telegram_user_id=tg.telegram_user_id, payload={"duplicate": True})
        return {"success": True, "request_id": request_id, "deals": [], "duplicate": True}

    app_dir = Path(__file__).resolve().parents[2]
    CalculatorService(app_dir / "config" / "tariffs.yaml").estimate(payload.vehicles[0].vehicle_type, payload.vehicles[0].insurance_period_days)

    bitrix_client = Bitrix24Client(get_settings().bitrix24_webhook_url)
    lead_service = LeadService(bitrix_client, app_dir / "config" / "bitrix_mapping.yaml")
    bitrix = {"deals": []}
    sync = BitrixSyncService()
    try:
        logger.info("bitrix_create_contact_company_deal request_id=%s", request_id)
        bitrix = lead_service.create_application_leads(payload, tg.username, tg.telegram_user_id)
        app_service.mark_bitrix_created(request_id, bitrix.get("contact_id"), bitrix.get("company_id"), bitrix.get("deals", []))
    except Exception as exc:
        logger.exception("bitrix_error request_id=%s error=%s", request_id, exc)
        app_service.mark_bitrix_pending(request_id)
        jid = sync.create_job(request_id, "create_application_leads", {"application": payload.model_dump(mode="json"), "telegram_username": tg.username, "telegram_user_id": tg.telegram_user_id})
        enqueue_bitrix_job(jid)

    storage = FileStorageService()
    bitrix_file = BitrixFileService(bitrix_client)
    with SessionLocal() as db:
        vehicles = list(db.query(Vehicle).filter(Vehicle.application_id == local_app.id).order_by(Vehicle.id.asc()))
        target_vehicle = vehicles[0] if vehicles else None
        saved_docs: list[UploadedDocument] = []
        saved_paths: list[str] = []
        for f in vehicle_docs:
            data = await f.read()
            try:
                storage.validate(f.content_type or "", len(data))
            except FileValidationError as exc:
                analytics.track("application_submit_failed", request_id=request_id, telegram_user_id=tg.telegram_user_id, payload={"error": str(exc)})
                raise HTTPException(status_code=400, detail=str(exc))
            if not target_vehicle:
                continue
            saved = storage.save_file(request_id, target_vehicle.id, f.filename, data)
            logger.info("file_saved request_id=%s path=%s", request_id, saved)
            doc = UploadedDocument(request_id=request_id, vehicle_id=target_vehicle.id, original_filename=f.filename, mime_type=f.content_type or "", size_bytes=len(data), storage_path=str(saved), bitrix_file_id=None, status="new")
            db.add(doc)
            db.flush()
            saved_docs.append(doc)
            saved_paths.append(str(saved))

        if saved_docs and target_vehicle:
            try:
                deal_id = target_vehicle.bitrix_deal_id or (bitrix.get("deals") or [None])[0]
                if not deal_id:
                    raise RuntimeError("deal_id missing")
                file_ids = bitrix_file.upload_and_attach_files_to_deal(deal_id, saved_paths)
                for doc, file_id in zip(saved_docs, file_ids, strict=False):
                    doc.bitrix_file_id = file_id
                    doc.status = "bitrix_created"
                logger.info("bitrix_files_uploaded request_id=%s deal_id=%s count=%s", request_id, deal_id, len(saved_paths))
            except Exception as exc:
                logger.exception("bitrix_file_error request_id=%s error=%s", request_id, exc)
                for doc, saved_path in zip(saved_docs, saved_paths, strict=False):
                    doc.status = "bitrix_pending"
                    jid = sync.create_job(request_id, "upload_file", {"deal_id": target_vehicle.bitrix_deal_id, "local_path": saved_path})
                    enqueue_bitrix_job(jid)
        db.commit()

    analytics.track("application_submitted", request_id=request_id, telegram_user_id=tg.telegram_user_id, payload={"deals": bitrix.get("deals", [])})
    return {"success": True, "request_id": request_id, "deals": bitrix.get("deals", [])}
