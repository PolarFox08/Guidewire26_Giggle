from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

try:
    import redis
except ModuleNotFoundError:  # pragma: no cover - optional test dependency
    redis = None

from app.api.fraud import router as fraud_router
from app.api.admin import router as admin_router
from app.api.claims import router as claims_router
from app.api.onboarding import router as onboarding_router
from app.api.payout import router as payout_router
from app.api.policy import router as policy_router
from app.api.premium import router as premium_router
from app.api.trigger import router as trigger_router
from app.core.config import settings
from app.core.database import engine
from app.fraud import scorer as fraud_scorer

logger = logging.getLogger(__name__)

app = FastAPI(
    title="GigShield API",
    description="Parametric income insurance for gig workers",
    version="0.2.0",
)


app.include_router(onboarding_router)
app.include_router(policy_router)
app.include_router(fraud_router)
app.include_router(admin_router)
app.include_router(premium_router, prefix="/api/v1/premium")
app.include_router(trigger_router)
app.include_router(claims_router)
app.include_router(payout_router)


@app.on_event("startup")
def startup_event() -> None:
    from app.core import gis

    logger.info("GIS module loaded successfully.")
    logger.info("GIS module loaded — flood tier and zone cluster functions ready.")

    if fraud_scorer.IF_LOADED and fraud_scorer.CBLOF_LOADED:
        logger.info("Fraud models loaded successfully.")
    else:
        logger.warning("Fraud models were not found at startup.")

    logger.info("GigShield API started. All routers registered.")


def _check_database() -> str:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        logger.exception("Database health check failed.")
        return "error"


def _check_redis() -> str:
    try:
        if redis is None:
            return "error"
        client = redis.from_url(settings.redis_url)
        try:
            client.ping()
        finally:
            client.close()
        return "ok"
    except Exception:
        logger.exception("Redis health check failed.")
        return "error"


def _check_fraud_models() -> str:
    return "loaded" if fraud_scorer.IF_LOADED and fraud_scorer.CBLOF_LOADED else "missing"


@app.get("/api/v1/health")
def health() -> JSONResponse:
    database_status = _check_database()
    redis_status = _check_redis()
    fraud_models_status = _check_fraud_models()

    response = {
        "status": "healthy"
        if database_status == "ok" and redis_status == "ok" and fraud_models_status == "loaded"
        else "degraded",
        "database": database_status,
        "redis": redis_status,
        "fraud_models": fraud_models_status,
        "version": "0.2.0",
    }
    return JSONResponse(status_code=200, content=response)
