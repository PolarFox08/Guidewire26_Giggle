"""Cascade recovery Celery task for post-trigger continuation/closure."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from celery import shared_task

from app.core.database import get_db
from app.models.audit import AuditEvent
from app.models.trigger import TriggerEvent
from app.models.zone import ZoneCluster
from app.tasks.trigger_polling import initiate_zone_payouts, is_zone_suspended
from app.trigger.aqi_monitor import check_aqi_trigger
from app.trigger.imd_classifier import classify_rainfall
from app.trigger.open_meteo import query_three_points


MAX_CASCADE_DAYS = 5


def _get_db_session():
    db_candidate: Any = get_db()
    if hasattr(db_candidate, "__next__"):
        db_gen = db_candidate
        db = next(db_gen)
        return db, db_gen
    return db_candidate, None


def _run_async(coro: Any) -> Any:
    return asyncio.run(coro)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


@shared_task(name="app.tasks.cascade_recovery.check_recovering_zones")
def check_recovering_zones() -> dict[str, int]:
    """Close recovered/expired trigger events and continue payouts for ongoing disruptions."""
    db, db_gen = _get_db_session()
    now = datetime.now(timezone.utc)

    checked = 0
    closed = 0
    continued = 0

    try:
        triggers = (
            db.query(TriggerEvent)
            .filter(TriggerEvent.status.in_(["active", "recovering"]))
            .all()
        )

        for trigger in triggers:
            checked += 1

            triggered_at = trigger.triggered_at
            if triggered_at is not None and triggered_at.tzinfo is None:
                triggered_at = triggered_at.replace(tzinfo=timezone.utc)
            if triggered_at is None:
                triggered_at = now

            cascade_day = int((now - triggered_at).total_seconds() // 86400) + 1
            if cascade_day > MAX_CASCADE_DAYS:
                trigger.status = "closed"
                trigger.closed_at = now
                db.add(
                    AuditEvent(
                        event_type="trigger_closed",
                        entity_id=trigger.id,
                        entity_type="trigger_event",
                        payload={
                            "reason": "cascade_limit_exceeded",
                            "cascade_day": cascade_day,
                        },
                        actor="system",
                    )
                )
                closed += 1
                continue

            zone = db.query(ZoneCluster).filter(ZoneCluster.id == trigger.zone_cluster_id).first()
            if not zone:
                trigger.status = "closed"
                trigger.closed_at = now
                db.add(
                    AuditEvent(
                        event_type="trigger_closed",
                        entity_id=trigger.id,
                        entity_type="trigger_event",
                        payload={"reason": "zone_not_found"},
                        actor="system",
                    )
                )
                closed += 1
                continue

            weather = _run_async(
                query_three_points(
                    _to_float(getattr(zone, "centroid_lat", None), default=0.0),
                    _to_float(getattr(zone, "centroid_lon", None), default=0.0),
                )
            )

            rain_mm = _to_float(weather.get("max_precipitation_24h_mm", 0.0), default=0.0)
            rain_triggered = bool(classify_rainfall(rain_mm)["triggered"])
            platform_suspended = is_zone_suspended(_to_int(getattr(zone, "id", 0), default=0))
            aqi_triggered = bool(check_aqi_trigger(_to_int(getattr(zone, "id", 0), default=0))["triggered"])

            all_sources_clear = (not rain_triggered) and (not platform_suspended) and (not aqi_triggered)

            if all_sources_clear:
                trigger.status = "closed"
                trigger.closed_at = now
                db.add(
                    AuditEvent(
                        event_type="trigger_closed",
                        entity_id=trigger.id,
                        entity_type="trigger_event",
                        payload={
                            "reason": "all_sources_clear",
                            "cascade_day": cascade_day,
                        },
                        actor="system",
                    )
                )
                closed += 1
                continue

            trigger.status = "recovering"
            db.add(
                AuditEvent(
                    event_type="trigger_recovering",
                    entity_id=trigger.id,
                    entity_type="trigger_event",
                    payload={
                        "cascade_day": cascade_day,
                        "rain_triggered": rain_triggered,
                        "platform_suspended": platform_suspended,
                        "aqi_triggered": aqi_triggered,
                    },
                    actor="system",
                )
            )
            getattr(initiate_zone_payouts, "delay")(
                str(trigger.id),
                _to_int(getattr(trigger, "zone_cluster_id", 0), default=0),
                cascade_day,
            )
            continued += 1

        db.commit()
        return {
            "checked": checked,
            "closed": closed,
            "continued": continued,
        }
    finally:
        if db_gen is not None and hasattr(db_gen, "close"):
            db_gen.close()
