from fastapi import FastAPI

from app.api.routes.applications import router as applications_router
from app.api.routes.miniapp_auth import router as miniapp_router
from app.api.routes.admin import router as admin_router
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(applications_router)
app.include_router(miniapp_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
