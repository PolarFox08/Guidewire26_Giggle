"""Trigger API endpoints for zone state, simulation, and history."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit import AuditEvent
from app.models.claims import Claim
from app.models.trigger import TriggerEvent
from app.models.zone import ZoneCluster
from app.tasks.trigger_polling import initiate_zone_payouts, set_zone_suspended


router = APIRouter(prefix="/api/v1/trigger", tags=["trigger"])


ALLOWED_TRIGGER_TYPES = {
    "heavy_rain",
    "very_heavy_rain",
    "extreme_heavy_rain",
    "severe_heatwave",
    "severe_aqi",
    "platform_suspension",
}


class ZoneTriggerStateResponse(BaseModel):
    zone_cluster_id: int
    status: Literal["active", "recovering", "none"]
    trigger_event_id: UUID | None
    trigger_type: str | None
    composite_score: float | None
    triggered_at: datetime | None
    sources_confirmed: int


class SimulateTriggerRequest(BaseModel):
    zone_cluster_id: int = Field(..., ge=1)
    trigger_type: str = Field(...)
    duration_hours: float = Field(..., gt=0)


class SimulateTriggerResponse(BaseModel):
    trigger_event_id: UUID
    zone_cluster_id: int
    trigger_type: str
    duration_hours: float
    payout_task_enqueued: bool


class ActiveTriggerItem(BaseModel):
    trigger_event_id: UUID
    zone_cluster_id: int
    zone_centroid_lat: float | None
    zone_centroid_lon: float | None
    status: str
    trigger_type: str
    composite_score: float
    sources_confirmed: int
    triggered_at: datetime
    current_cascade_day: int


class ActiveTriggersResponse(BaseModel):
    items: list[ActiveTriggerItem]


class TriggerHistoryItem(BaseModel):
    trigger_event_id: UUID
    zone_cluster_id: int
    trigger_type: str
    status: str
    triggered_at: datetime
    composite_score: float
    sources_confirmed: int
    payout_count: int


class TriggerHistoryResponse(BaseModel):
    items: list[TriggerHistoryItem]


def _coerce_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _cascade_day(triggered_at: datetime) -> int:
    now = datetime.now(timezone.utc)
    normalized = _coerce_utc(triggered_at)
    if normalized is None:
        return 1
    return max(1, int((now - normalized).total_seconds() // 86400) + 1)


def _to_uuid(value: Any) -> UUID:
    return cast(UUID, value)


def _to_float(value: Any) -> float:
    return float(cast(float | Decimal | int, value))


def _to_int(value: Any) -> int:
    return int(cast(int | bool, value))


def _to_str(value: Any) -> str:
    return str(cast(str, value))


def _to_datetime(value: Any) -> datetime:
    typed = cast(datetime | None, value)
    return _coerce_utc(typed) or datetime.now(timezone.utc)


@router.get("/zone/{zone_cluster_id}", response_model=ZoneTriggerStateResponse)
def get_zone_trigger_state(
    zone_cluster_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ZoneTriggerStateResponse:
    zone = db.query(ZoneCluster).filter(ZoneCluster.id == zone_cluster_id).first()
    if zone is None:
        raise HTTPException(status_code=404, detail="zone_cluster_id not found")

    trigger = (
        db.query(TriggerEvent)
        .filter(TriggerEvent.zone_cluster_id == zone_cluster_id)
        .order_by(TriggerEvent.triggered_at.desc())
        .first()
    )

    if trigger is None:
        return ZoneTriggerStateResponse(
            zone_cluster_id=zone_cluster_id,
            status="none",
            trigger_event_id=None,
            trigger_type=None,
            composite_score=None,
            triggered_at=None,
            sources_confirmed=0,
        )

    status_value: Literal["active", "recovering", "none"]
    status_raw = _to_str(trigger.status)
    status_value = "none"
    if status_raw == "active":
        status_value = "active"
    elif status_raw == "recovering":
        status_value = "recovering"

    return ZoneTriggerStateResponse(
        zone_cluster_id=zone_cluster_id,
        status=status_value,
        trigger_event_id=_to_uuid(trigger.id),
        trigger_type=_to_str(trigger.trigger_type),
        composite_score=_to_float(trigger.composite_score),
        triggered_at=_coerce_utc(cast(datetime | None, trigger.triggered_at)),
        sources_confirmed=_to_int(trigger.corroboration_sources),
    )


@router.post("/simulate", response_model=SimulateTriggerResponse)
def simulate_trigger(
    payload: SimulateTriggerRequest,
    db: Session = Depends(get_db),
) -> SimulateTriggerResponse:
    trigger_type = payload.trigger_type.strip()
    if trigger_type not in ALLOWED_TRIGGER_TYPES:
        raise HTTPException(status_code=422, detail="invalid trigger_type")

    zone = db.query(ZoneCluster).filter(ZoneCluster.id == payload.zone_cluster_id).first()
    if zone is None:
        raise HTTPException(status_code=404, detail="zone_cluster_id not found")

    existing_active = (
        db.query(TriggerEvent)
        .filter(
            TriggerEvent.zone_cluster_id == payload.zone_cluster_id,
            TriggerEvent.status.in_(["active", "recovering"]),
        )
        .first()
    )
    if existing_active is not None:
        raise HTTPException(status_code=409, detail="active trigger already exists for zone")

    set_zone_suspended(payload.zone_cluster_id)

    trigger = TriggerEvent(
        zone_cluster_id=payload.zone_cluster_id,
        triggered_at=datetime.now(timezone.utc),
        trigger_type=trigger_type,
        composite_score=Decimal("1.000"),
        rain_signal_value=Decimal("64.5") if "rain" in trigger_type else Decimal("0"),
        aqi_signal_value=301 if trigger_type == "severe_aqi" else None,
        temp_signal_value=Decimal("45.0") if trigger_type == "severe_heatwave" else None,
        platform_suspended=True,
        gis_flood_activated="rain" in trigger_type,
        corroboration_sources=3,
        fast_path_used=True,
        status="active",
    )
    db.add(trigger)
    db.flush()

    db.add(
        AuditEvent(
            event_type="trigger_simulated",
            entity_id=trigger.id,
            entity_type="trigger_event",
            payload={
                "zone_cluster_id": payload.zone_cluster_id,
                "trigger_type": trigger_type,
                "duration_hours": payload.duration_hours,
            },
            actor="admin",
        )
    )
    db.commit()

    getattr(initiate_zone_payouts, "delay")(str(trigger.id), int(payload.zone_cluster_id), 1)

    return SimulateTriggerResponse(
        trigger_event_id=_to_uuid(trigger.id),
        zone_cluster_id=payload.zone_cluster_id,
        trigger_type=trigger_type,
        duration_hours=payload.duration_hours,
        payout_task_enqueued=True,
    )


@router.get("/active", response_model=ActiveTriggersResponse)
def get_active_triggers(db: Session = Depends(get_db)) -> ActiveTriggersResponse:
    rows = (
        db.query(TriggerEvent, ZoneCluster)
        .join(ZoneCluster, ZoneCluster.id == TriggerEvent.zone_cluster_id)
        .filter(TriggerEvent.status.in_(["active", "recovering"]))
        .order_by(TriggerEvent.triggered_at.desc())
        .all()
    )

    items = [
        ActiveTriggerItem(
            trigger_event_id=_to_uuid(trigger.id),
            zone_cluster_id=_to_int(trigger.zone_cluster_id),
            zone_centroid_lat=float(zone.centroid_lat) if zone.centroid_lat is not None else None,
            zone_centroid_lon=float(zone.centroid_lon) if zone.centroid_lon is not None else None,
            status=_to_str(trigger.status),
            trigger_type=_to_str(trigger.trigger_type),
            composite_score=_to_float(trigger.composite_score),
            sources_confirmed=_to_int(trigger.corroboration_sources),
            triggered_at=_to_datetime(trigger.triggered_at),
            current_cascade_day=_cascade_day(_to_datetime(trigger.triggered_at)),
        )
        for trigger, zone in rows
    ]

    return ActiveTriggersResponse(items=items)


@router.get("/history", response_model=TriggerHistoryResponse)
def get_trigger_history(db: Session = Depends(get_db)) -> TriggerHistoryResponse:
    rows = (
        db.query(
            TriggerEvent,
            func.count(Claim.id).label("payout_count"),
        )
        .outerjoin(Claim, Claim.trigger_event_id == TriggerEvent.id)
        .group_by(TriggerEvent.id)
        .order_by(TriggerEvent.triggered_at.desc())
        .limit(50)
        .all()
    )

    items: list[TriggerHistoryItem] = []
    for trigger, payout_count in rows:
        items.append(
            TriggerHistoryItem(
                trigger_event_id=_to_uuid(trigger.id),
                zone_cluster_id=_to_int(trigger.zone_cluster_id),
                trigger_type=_to_str(trigger.trigger_type),
                status=_to_str(trigger.status),
                triggered_at=_to_datetime(trigger.triggered_at),
                composite_score=_to_float(trigger.composite_score),
                sources_confirmed=_to_int(trigger.corroboration_sources),
                payout_count=int(cast(int | None, payout_count) or 0),
            )
        )

    return TriggerHistoryResponse(items=items)
