"""Trigger polling and payout initiation Celery tasks."""

from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, cast

from celery import shared_task
from sqlalchemy import func

from app.core.database import get_db
from app.models.audit import AuditEvent
from app.models.claims import Claim
from app.models.delivery import DeliveryHistory
from app.models.payout import PayoutEvent
from app.models.policy import Policy
from app.models.trigger import TriggerEvent
from app.models.worker import WorkerProfile
from app.models.zone import ZoneCluster
from app.payout.calculator import compute_payout
from app.payout.razorpay_client import initiate_upi_payout
from app.trigger.aqi_monitor import check_aqi_trigger
from app.trigger.composite_scorer import compute_composite_score
from app.trigger.imd_classifier import classify_heat, classify_rainfall
from app.trigger.open_meteo import query_three_points

try:
    _fraud_behavioral = importlib.import_module("app.fraud.behavioral")
    _fraud_scorer = importlib.import_module("app.fraud.scorer")

    compute_activity_7d_score = _fraud_behavioral.compute_activity_7d_score
    compute_fraud_score = _fraud_scorer.compute_fraud_score
    route_claim = _fraud_scorer.route_claim
except ImportError:
    # MOCK_REMOVE_BEFORE_MERGE: Person 1 fraud module may not exist yet on this branch.
    def compute_activity_7d_score(deliveries_7d: int, avg_daily_30d: float) -> float:
        if avg_daily_30d <= 0:
            return 0.5
        return min(1.5, max(0.0, deliveries_7d / (avg_daily_30d * 7)))

    # MOCK_REMOVE_BEFORE_MERGE: fallback scorer for local branch integration.
    def compute_fraud_score(
        zone_claim_match: int,
        activity_7d_score: float,
        claim_to_enrollment_days: int,
        event_claim_frequency: int,
    ) -> float:
        score = 0.0
        if zone_claim_match == 0:
            score += 0.5
        if activity_7d_score < 0.6:
            score += 0.2
        if claim_to_enrollment_days < 28:
            score += 0.2
        if event_claim_frequency > 4:
            score += 0.2
        return max(0.0, min(1.0, score))

    # MOCK_REMOVE_BEFORE_MERGE: fallback routing based on Section 1.6 thresholds.
    def route_claim(fraud_score: float) -> str:
        if fraud_score < 0.3:
            return "auto_approve"
        if fraud_score <= 0.7:
            return "partial_review"
        return "hold"


WAITING_PERIOD_DAYS = 28

_suspended_zones: set[int] = set()


def set_zone_suspended(zone_cluster_id: int) -> None:
    """Mark zone as suspended in mock operational state."""
    _suspended_zones.add(int(zone_cluster_id))


def set_zone_resumed(zone_cluster_id: int) -> None:
    """Remove zone from mock suspended operational state."""
    _suspended_zones.discard(int(zone_cluster_id))


def is_zone_suspended(zone_cluster_id: int) -> bool:
    """Return mock suspension state for zone."""
    return int(zone_cluster_id) in _suspended_zones


def _run_async(coro: Any) -> Any:
    return asyncio.run(coro)


def _get_db_session():
    db_candidate: Any = get_db()
    if hasattr(db_candidate, "__next__"):
        db_gen = cast(Any, db_candidate)
        db = next(db_gen)
        return db, db_gen

    return db_candidate, None


def _zone_tier_from_numeric(value: Any) -> str:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return "low"
    if numeric >= 3:
        return "high"
    if numeric == 2:
        return "medium"
    return "low"


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


def _to_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _compute_activity_signal(db: Any, worker_id: Any, as_of: datetime) -> float:
    last_7_days_start = as_of - timedelta(days=7)
    last_30_days_start = as_of - timedelta(days=30)

    deliveries_7d = (
        db.query(func.coalesce(func.sum(DeliveryHistory.deliveries_count), 0))
        .filter(
            DeliveryHistory.worker_id == worker_id,
            DeliveryHistory.recorded_at >= last_7_days_start,
            DeliveryHistory.recorded_at <= as_of,
        )
        .scalar()
    )

    daily_avg_30d = (
        db.query(func.avg(DeliveryHistory.deliveries_count))
        .filter(
            DeliveryHistory.worker_id == worker_id,
            DeliveryHistory.recorded_at >= last_30_days_start,
            DeliveryHistory.recorded_at <= as_of,
        )
        .scalar()
    )

    return float(
        compute_activity_7d_score(
            int(deliveries_7d or 0),
            float(daily_avg_30d or 0.0),
        )
    )


def _compute_zone_claim_match(db: Any, worker_id: Any) -> bool:
    # MOCK_REMOVE_BEFORE_MERGE: PostGIS ST_Within requires GIS polygon wiring from Person 1.
    recent_count = (
        db.query(DeliveryHistory)
        .filter(DeliveryHistory.worker_id == worker_id)
        .order_by(DeliveryHistory.recorded_at.desc())
        .limit(5)
        .count()
    )
    return bool(recent_count > 0)


@shared_task(name="app.tasks.trigger_polling.poll_all_zones")
def poll_all_zones() -> dict[str, int]:
    """Poll all zones and fire new trigger events when corroboration conditions pass."""
    db, db_gen = _get_db_session()
    created_count = 0

    try:
        zones = db.query(ZoneCluster).all()

        for zone in zones:
            zone_id = _to_int(getattr(zone, "id", 0), default=0)
            centroid_lat = _to_float(getattr(zone, "centroid_lat", None), default=0.0)
            centroid_lon = _to_float(getattr(zone, "centroid_lon", None), default=0.0)
            zone_tier_numeric = _to_int(getattr(zone, "flood_tier_numeric", 1), default=1)

            weather = _run_async(
                query_three_points(centroid_lat, centroid_lon)
            )
            rain_mm = float(weather.get("max_precipitation_24h_mm", 0.0))
            max_temp_c = float(weather.get("max_temperature_2m_c", 0.0))

            rain_result = classify_rainfall(rain_mm)
            heat_result = classify_heat(max_temp_c)
            aqi_result = check_aqi_trigger(zone_id)

            zone_tier = _zone_tier_from_numeric(zone_tier_numeric)
            gis_active = rain_result["triggered"] and zone_tier in {"high", "medium"}

            composite = compute_composite_score(
                platform_suspended=is_zone_suspended(zone_id),
                rainfall_triggered=bool(rain_result["triggered"]),
                gis_flood_active=gis_active,
                aqi_triggered=bool(aqi_result.get("triggered", False)),
                heat_triggered=bool(heat_result["triggered"]),
                zone_flood_tier=zone_tier,
            )

            if composite["decision"] not in {"trigger_corroborated", "trigger_fast_path"}:
                continue

            existing_active = (
                db.query(TriggerEvent)
                .filter(
                    TriggerEvent.zone_cluster_id == zone_id,
                    TriggerEvent.status.in_(["active", "recovering"]),
                )
                .first()
            )
            if existing_active:
                continue

            trigger_type = rain_result["category"] or (
                "severe_heatwave" if heat_result["triggered"] else "severe_aqi"
            )
            if is_zone_suspended(zone_id):
                trigger_type = "platform_suspension"

            trigger = TriggerEvent(
                zone_cluster_id=zone_id,
                triggered_at=datetime.now(timezone.utc),
                trigger_type=trigger_type,
                composite_score=Decimal(str(composite["composite_score"])),
                rain_signal_value=Decimal(str(rain_mm)),
                aqi_signal_value=(
                    int(aqi_result["latest_aqi"])
                    if aqi_result.get("latest_aqi") is not None
                    else None
                ),
                temp_signal_value=Decimal(str(max_temp_c)),
                platform_suspended=is_zone_suspended(zone_id),
                gis_flood_activated=gis_active,
                corroboration_sources=int(composite["sources_confirmed"]),
                fast_path_used=bool(composite["fast_path_used"]),
                status="active",
            )
            db.add(trigger)
            db.flush()

            db.add(
                AuditEvent(
                    event_type="trigger_fired",
                    entity_id=trigger.id,
                    entity_type="trigger_event",
                    payload={
                        "zone_cluster_id": zone_id,
                        "composite_score": composite["composite_score"],
                        "trigger_type": trigger_type,
                        "rain_mm_24h": rain_mm,
                    },
                    actor="system",
                )
            )

            db.commit()
            created_count += 1
            getattr(initiate_zone_payouts, "delay")(_to_str(trigger.id), zone_id, 1)

        return {"zones_checked": len(zones), "triggers_created": created_count}
    finally:
        if db_gen is not None and hasattr(db_gen, "close"):
            db_gen.close()


@shared_task(name="app.tasks.trigger_polling.initiate_zone_payouts")
def initiate_zone_payouts(
    trigger_event_id: str,
    zone_cluster_id: int,
    cascade_day: int = 1,
) -> dict[str, int]:
    """Create claim and payout records for active workers in a triggered zone."""
    db, db_gen = _get_db_session()
    processed = 0

    try:
        trigger_event = db.query(TriggerEvent).filter(TriggerEvent.id == trigger_event_id).first()
        if not trigger_event:
            return {"workers_processed": 0, "claims_created": 0}

        active_pairs = (
            db.query(WorkerProfile, Policy)
            .join(Policy, Policy.worker_id == WorkerProfile.id)
            .filter(
                WorkerProfile.zone_cluster_id == int(zone_cluster_id),
                WorkerProfile.is_active.is_(True),
                Policy.status == "active",
            )
            .all()
        )

        claims_created = 0
        now = datetime.now(timezone.utc)

        for worker, policy in active_pairs:
            enrollment_date = worker.enrollment_date
            if enrollment_date is None:
                continue
            if enrollment_date.tzinfo is None:
                enrollment_date = enrollment_date.replace(tzinfo=timezone.utc)

            if (now - enrollment_date).days < WAITING_PERIOD_DAYS:
                continue

            payout_breakdown = compute_payout(
                worker=worker,
                policy=policy,
                deliveries_completed_today=0,
                disruption_duration_hours=1.0,
                cascade_day=cascade_day,
                trigger_type=_to_str(getattr(trigger_event, "trigger_type", ""), default=""),
                db=db,
            )

            if not payout_breakdown.get("eligible_for_payout", True):
                continue

            activity_7d_score = _compute_activity_signal(db, worker.id, now)
            zone_claim_match_bool = _compute_zone_claim_match(db, worker.id)

            event_claim_frequency = (
                db.query(Claim)
                .filter(
                    Claim.worker_id == worker.id,
                    Claim.claim_date >= now - timedelta(days=90),
                )
                .count()
            )

            claim_to_enrollment_days = max(0, (now - enrollment_date).days)
            fraud_score = float(
                compute_fraud_score(
                    zone_claim_match=1 if zone_claim_match_bool else 0,
                    activity_7d_score=activity_7d_score,
                    claim_to_enrollment_days=claim_to_enrollment_days,
                    event_claim_frequency=event_claim_frequency,
                )
            )
            fraud_routing = route_claim(fraud_score)

            claim_status = {
                "auto_approve": "approved",
                "partial_review": "partial",
                "hold": "held",
            }[fraud_routing]

            claim = Claim(
                worker_id=worker.id,
                trigger_event_id=trigger_event.id,
                policy_id=policy.id,
                cascade_day=int(cascade_day),
                deliveries_completed=0,
                base_loss_amount=Decimal(str(payout_breakdown["base_loss"])),
                slab_delta_amount=Decimal(str(payout_breakdown["slab_delta"])),
                monthly_proximity_amount=Decimal(str(payout_breakdown["monthly_proximity"])),
                peak_multiplier_applied=bool(payout_breakdown["peak_multiplier_applied"]),
                total_payout_amount=Decimal(str(payout_breakdown["total_payout"])),
                fraud_score=Decimal(str(round(fraud_score, 3))),
                fraud_routing=fraud_routing,
                zone_claim_match=zone_claim_match_bool,
                activity_7d_score=Decimal(str(round(activity_7d_score, 3))),
                status=claim_status,
            )
            db.add(claim)
            db.flush()

            payout_amount = float(payout_breakdown["total_payout"])
            payout_status = "held"
            payout_id = None
            payout_error = None

            if fraud_routing != "hold":
                if fraud_routing == "partial_review":
                    payout_amount = round(payout_amount * 0.5, 2)

                payout_result = initiate_upi_payout(worker.upi_vpa, payout_amount, str(claim.id))
                payout_status = (
                    payout_result.get("status", "processing")
                    if payout_result.get("success")
                    else "failed"
                )
                payout_id = payout_result.get("payout_id")
                payout_error = payout_result.get("error")

            payout_event = PayoutEvent(
                claim_id=claim.id,
                worker_id=worker.id,
                razorpay_payout_id=payout_id,
                amount=Decimal(str(round(max(0.0, payout_amount), 2))),
                upi_vpa=worker.upi_vpa,
                status=payout_status,
                failure_reason=payout_error,
            )
            db.add(payout_event)

            db.add(
                AuditEvent(
                    event_type="payout_initiated",
                    entity_id=claim.id,
                    entity_type="claim",
                    payload={
                        "worker_id": str(worker.id),
                        "trigger_event_id": str(trigger_event.id),
                        "fraud_score": round(fraud_score, 3),
                        "fraud_routing": fraud_routing,
                        "payout_amount": payout_amount,
                        "payout_status": payout_status,
                    },
                    actor="system",
                )
            )

            db.commit()
            processed += 1
            claims_created += 1

        return {"workers_processed": processed, "claims_created": claims_created}
    finally:
        if db_gen is not None and hasattr(db_gen, "close"):
            db_gen.close()
