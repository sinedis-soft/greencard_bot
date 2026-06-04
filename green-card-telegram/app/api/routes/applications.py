import json
import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.db.models import UploadedDocument, Vehicle
from app.db.session import SessionLocal
from app.schemas.application import ApplicationCreate
from app.services.analytics_service import AnalyticsService
from app.services.application_guard_service import ApplicationGuardService
from app.services.application_service import ApplicationService
from app.services.bitrix24_client import Bitrix24Client
from app.services.bitrix_file_service import BitrixFileService
from app.services.bitrix_sync_service import BitrixSyncService
from app.services.calculator_service import CalculatorService
from app.services.file_storage_service import FileStorageService, FileValidationError, MAX_FILES
from app.services.lead_service import LeadService
from app.services.notification_service import NotificationService
from app.services.reminder_service import ReminderService
from app.services.telegram_auth_service import TelegramAuthError, TelegramAuthService
from app.services.consent_service import ConsentService
from app.workers.bitrix_retry_worker import enqueue_bitrix_job

router = APIRouter(prefix="/api/applications", tags=["applications"])
logger = logging.getLogger(__name__)


@router.post("")
async def create_application(application_json: str = Form(...), vehicle_docs: list[UploadFile] = File(default=[])) -> dict:
    payload = ApplicationCreate(**json.loads(application_json))
    analytics = AnalyticsService()
    analytics.track("application_submit_attempt", payload={"vehicle_count": len(payload.vehicles), "preferred_language": payload.preferred_language})
    analytics.track("miniapp_opened", telegram_user_id=None, payload={"source":"miniapp"})

    if len(vehicle_docs) > MAX_FILES:
        raise HTTPException(status_code=400, detail="too_many_files")

    try:
        tg = TelegramAuthService(__import__("os").getenv("BOT_TOKEN", "")).validate_init_data(payload.telegram_init_data)
    except TelegramAuthError as exc:
        analytics.track("application_submit_failed", payload={"error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    guard = ApplicationGuardService()
    guard_result = guard.check_before_create(payload, tg.telegram_user_id, len(vehicle_docs))
    if not guard_result.allowed:
        analytics.track("application_submit_failed", telegram_user_id=tg.telegram_user_id, payload=guard_result.to_dict())
        raise HTTPException(status_code=409 if guard_result.severity in {"soft", "medium"} else 400, detail=guard_result.to_dict())

    app_service = ApplicationService()
    local_app, is_duplicate = app_service.create_local(payload, tg.telegram_user_id, tg.username, tg.language_code)
    request_id = local_app.request_id
    accepted_consents = ConsentService().validate_required(payload)
    ConsentService().save_consents(local_app.id, tg.telegram_user_id, payload.preferred_language, accepted_consents)
    guard.record_application(local_app.id, tg.telegram_user_id, payload, status="submitted")
    logger.info("application_received request_id=%s", request_id)
    NotificationService().send(
        event_key="application_accepted",
        recipient_type="client",
        recipient_id=str(tg.telegram_chat_id or tg.telegram_user_id),
        channel="client_telegram",
        language=payload.preferred_language,
        context={"request_id": request_id, "public_status": "документы переданы на проверку"},
        dedupe_key=f"application_accepted:{request_id}",
    )
    try:
        reminder_service = ReminderService()
        reminder_service.mark_calculator_converted(tg.telegram_user_id)
        reminder_service.complete_active_drafts(tg.telegram_user_id)
    except Exception as exc:
        logger.exception("application_reminder_cleanup_failed user_id=%s error=%s", tg.telegram_user_id, exc)

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
        bitrix = lead_service.create_application_leads(payload, tg.username, tg.telegram_user_id, tg.telegram_chat_id, request_id)
        app_service.mark_bitrix_created(request_id, bitrix.get("contact_id"), bitrix.get("company_id"), bitrix.get("deals", []))
        guard.update_application_status(local_app.id, "bitrix_created", (bitrix.get("deals") or [None])[0])
    except Exception as exc:
        logger.exception("bitrix_error request_id=%s error=%s", request_id, exc)
        app_service.mark_bitrix_pending(request_id)
        guard.update_application_status(local_app.id, "bitrix_pending")
        jid = sync.create_job(request_id, "create_application_leads", {"application": payload.model_dump(mode="json"), "telegram_username": tg.username, "telegram_user_id": tg.telegram_user_id, "telegram_chat_id": tg.telegram_chat_id, "request_id": request_id})
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
    if bitrix.get("deals"):
        app_service.purge_sensitive_data_after_success(request_id)
    return {"success": True, "request_id": request_id, "deals": bitrix.get("deals", [])}
