from fastapi import APIRouter

router = APIRouter(prefix="/api/miniapp", tags=["miniapp-auth"])


@router.get("/health")
def miniapp_health() -> dict:
    return {"status": "ok"}
