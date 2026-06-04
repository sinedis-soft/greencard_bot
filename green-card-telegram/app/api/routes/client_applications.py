from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query

from app.core.config import get_settings
from app.services.bitrix24_client import Bitrix24Client
from app.services.bitrix_deal_mapper import safe_deal_card
from app.services.client_application_service import ClientApplicationService
from app.services.data_deletion_request_service import DataDeletionRequestService
from app.services.repeat_application_service import RepeatApplicationError, RepeatApplicationService
from app.services.policy_status_service import PolicyStatusError, PolicyStatusService

router = APIRouter(prefix="/api/client", tags=["client-applications"])


def _bitrix_client() -> Bitrix24Client:
    return Bitrix24Client(get_settings().bitrix24_webhook_url)


def _service() -> ClientApplicationService:
    return ClientApplicationService(_bitrix_client())


def _repeat_service() -> RepeatApplicationService:
    return RepeatApplicationService(_bitrix_client())


def _policy_status_service() -> PolicyStatusService:
    return PolicyStatusService(_service())


def _repeat_error(exc: RepeatApplicationError) -> HTTPException:
    detail = str(exc) or "repeat_error"
    status = 404 if detail in {"application_not_found", "repeat_draft_not_found"} else 400
    return HTTPException(status_code=status, detail=detail)


@router.get("/my-applications")
def my_applications(
    telegram_user_id: int = Query(...),
    telegram_chat_id: int | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=10),
) -> dict:
    return _service().list_my_applications(
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        limit=limit,
    )


@router.get("/my-applications/{deal_id}")
def my_application(
    deal_id: int,
    telegram_user_id: int = Query(...),
    telegram_chat_id: int | None = Query(default=None),
) -> dict:
    deal = _service().get_client_deal(
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        deal_id=deal_id,
    )
    if not deal:
        raise HTTPException(status_code=404, detail="application_not_found")
    return safe_deal_card(deal)

@router.post("/repeat/start")
def repeat_start(payload: dict = Body(...)) -> dict:
    try:
        return _repeat_service().start(
            telegram_user_id=int(payload["telegram_user_id"]),
            telegram_chat_id=payload.get("telegram_chat_id"),
            old_deal_id=int(payload["old_deal_id"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid_payload") from exc
    except RepeatApplicationError as exc:
        raise _repeat_error(exc) from exc


@router.post("/repeat/{draft_id}/update")
def repeat_update(draft_id: str, payload: dict = Body(...)) -> dict:
    try:
        return _repeat_service().update(
            draft_id=draft_id,
            telegram_user_id=int(payload["telegram_user_id"]),
            new_start_date=payload.get("new_start_date"),
            new_period_days=payload.get("new_period_days"),
            docs_mode=payload.get("docs_mode"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid_payload") from exc
    except RepeatApplicationError as exc:
        raise _repeat_error(exc) from exc


@router.get("/repeat/{draft_id}/preview")
def repeat_preview(draft_id: str, telegram_user_id: int = Query(...)) -> dict:
    try:
        return _repeat_service().preview(draft_id=draft_id, telegram_user_id=telegram_user_id)
    except RepeatApplicationError as exc:
        raise _repeat_error(exc) from exc


@router.post("/repeat/{draft_id}/confirm")
def repeat_confirm(draft_id: str, payload: dict = Body(...)) -> dict:
    try:
        result = _repeat_service().confirm(
            draft_id=draft_id,
            telegram_user_id=int(payload["telegram_user_id"]),
            telegram_chat_id=payload.get("telegram_chat_id"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid_payload") from exc
    except RepeatApplicationError as exc:
        raise _repeat_error(exc) from exc
    return {
        "request_id": result.request_id,
        "bitrix_deal_id": result.bitrix_deal_id,
        "public_status": result.public_status,
    }

@router.post("/policy-status/check")
def policy_status_check(payload: dict = Body(...)) -> dict:
    try:
        return _policy_status_service().check(
            telegram_user_id=int(payload["telegram_user_id"]),
            telegram_chat_id=payload.get("telegram_chat_id"),
            deal_id=int(payload["deal_id"]),
            preferred_language=str(payload.get("preferred_language") or "ru"),
            client_name=str(payload.get("client_name") or ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid_payload") from exc
    except PolicyStatusError as exc:
        detail = str(exc) or "policy_status_error"
        status = 404 if detail == "application_not_found" else 400
        raise HTTPException(status_code=status, detail=detail) from exc

@router.post("/data-deletion/request")
def data_deletion_request(payload: dict = Body(...)) -> dict:
    try:
        request = DataDeletionRequestService().create_request(
            telegram_user_id=int(payload["telegram_user_id"]),
            telegram_chat_id=payload.get("telegram_chat_id"),
            bitrix_contact_id=payload.get("bitrix_contact_id"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid_payload") from exc
    return {
        "request_id": request.request_id,
        "status": request.status,
        "message": "Запрос на удаление данных создан. Администратор проверит юридические основания хранения и свяжется с вами.",
    }
