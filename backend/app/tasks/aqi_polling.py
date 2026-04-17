"""AQI polling Celery task wrapper."""

from __future__ import annotations

import asyncio
from typing import Any

from celery import shared_task

from app.core.database import get_db
from app.models.zone import ZoneCluster
from app.trigger.aqi_monitor import poll_aqi_all_zones


def _get_db_session():
    db_candidate: Any = get_db()
    if hasattr(db_candidate, "__next__"):
        db_gen = db_candidate
        db = next(db_gen)
        return db, db_gen
    return db_candidate, None


def _run_async(coro: Any) -> Any:
    return asyncio.run(coro)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


@shared_task(name="app.tasks.aqi_polling.poll_aqi_zones")
def poll_aqi_zones() -> dict[str, int]:
    """Poll AQI status for all zones and return aggregate task metrics."""
    db, db_gen = _get_db_session()
    try:
        zones = db.query(ZoneCluster).all()
        zone_payload = [
            {
                "id": _to_int(getattr(zone, "id", 0), default=0),
                "centroid_lat": _to_float(getattr(zone, "centroid_lat", None), default=0.0),
                "centroid_lon": _to_float(getattr(zone, "centroid_lon", None), default=0.0),
            }
            for zone in zones
        ]

        results = _run_async(poll_aqi_all_zones(zone_payload))
        triggered = sum(1 for value in results.values() if value.get("triggered"))

        return {
            "zones_polled": len(zone_payload),
            "zones_triggered": int(triggered),
        }
    finally:
        if db_gen is not None and hasattr(db_gen, "close"):
            db_gen.close()
