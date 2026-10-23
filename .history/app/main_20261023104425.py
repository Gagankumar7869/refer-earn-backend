from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Backend API for Refer & Earn system with idempotent ledger rewards, milestones, and reconciliation.",
)

register_exception_handlers(app)

app.include_router(auth_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}