"""Weekly renewal Celery task for policy lifecycle and premium refresh."""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from typing import Any

from celery import shared_task
from sqlalchemy import func

from app.core.database import get_db
from app.models.audit import AuditEvent
from app.models.delivery import DeliveryHistory
from app.models.policy import Policy
from app.models.worker import WorkerProfile
from app.models.zone import ZoneCluster

try:
    _premium_inference = importlib.import_module("app.ml.inference")
    calculate_premium = _premium_inference.calculate_premium
except ImportError:
    # MOCK_REMOVE_BEFORE_MERGE: Person 2 premium module may not exist yet on this branch.
    def calculate_premium(*args: Any, **kwargs: Any) -> dict[str, Any]:
        _ = args, kwargs
        return {
            "premium_amount": 79.0,
            "model_used": "stub",
            "recency_multiplier": 1.0,
            "shap_top3": [],
            "affordability_capped": False,
        }


WAITING_PERIOD_DAYS = 28


def _get_db_session():
    db_candidate: Any = get_db()
    if hasattr(db_candidate, "__next__"):
        db_gen = db_candidate
        db = next(db_gen)
        return db, db_gen
    return db_candidate, None


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


def get_current_season(now: datetime) -> str:
    month = now.month
    if 6 <= month <= 9:
        return "SW_monsoon"
    if 10 <= month <= 12:
        return "NE_monsoon"
    if 3 <= month <= 5:
        return "heat"
    return "dry"


def _next_sunday_midnight(now: datetime) -> datetime:
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    next_sunday = now + timedelta(days=days_until_sunday)
    return next_sunday.replace(hour=0, minute=0, second=0, microsecond=0)


def _estimate_delivery_baseline_30d(db: Any, worker_id: Any, now: datetime) -> float:
    start_at = now - timedelta(days=30)
    total = (
        db.query(func.coalesce(func.sum(DeliveryHistory.deliveries_count), 0))
        .filter(
            DeliveryHistory.worker_id == worker_id,
            DeliveryHistory.recorded_at >= start_at,
            DeliveryHistory.recorded_at <= now,
        )
        .scalar()
    )
    return max(0.0, _to_float(total, default=0.0))


def _estimate_income_baseline_weekly(db: Any, worker: WorkerProfile, now: datetime) -> float:
    delivery_baseline_30d = _estimate_delivery_baseline_30d(db, worker.id, now)
    zone = db.query(ZoneCluster).filter(ZoneCluster.id == worker.zone_cluster_id).first()
    zone_rate_mid = _to_float(getattr(zone, "zone_rate_mid", None), default=18.0)
    if delivery_baseline_30d <= 0:
        return 0.0
    return (delivery_baseline_30d / 30.0) * zone_rate_mid * 7.0


@shared_task(name="app.tasks.weekly_renewal.renew_all_policies")
def renew_all_policies() -> dict[str, int]:
    """Renew active/waiting policies, graduate waiting users, and refresh premiums."""
    db, db_gen = _get_db_session()
    now = datetime.now(timezone.utc)

    renewed = 0
    graduated = 0

    try:
        policies = (
            db.query(Policy)
            .filter(Policy.status.in_(["active", "waiting"]))
            .all()
        )

        for policy in policies:
            policy.coverage_week_number = _to_int(getattr(policy, "coverage_week_number", 0), default=0) + 1

            worker = db.query(WorkerProfile).filter(WorkerProfile.id == policy.worker_id).first()
            if not worker:
                continue

            enrollment_date = worker.enrollment_date
            if enrollment_date and enrollment_date.tzinfo is None:
                enrollment_date = enrollment_date.replace(tzinfo=timezone.utc)

            if (
                policy.status == "waiting"
                and enrollment_date is not None
                and (now - enrollment_date).days >= WAITING_PERIOD_DAYS
            ):
                policy.status = "active"
                policy.coverage_start_date = now
                graduated += 1

            premium_result: dict[str, Any] | None = None
            if policy.status == "active":
                income_baseline_weekly = _estimate_income_baseline_weekly(db, worker, now)
                premium_result = calculate_premium(
                    enrollment_week=_to_int(getattr(worker, "enrollment_week", 1), default=1),
                    flood_hazard_zone_tier=getattr(worker, "flood_hazard_tier", "low"),
                    zone_cluster_id=_to_int(getattr(worker, "zone_cluster_id", 1), default=1),
                    platform=getattr(worker, "platform", "zomato"),
                    season_flag=get_current_season(now),
                    delivery_baseline_30d=_estimate_delivery_baseline_30d(db, worker.id, now),
                    income_baseline_weekly=income_baseline_weekly,
                    open_meteo_7d_precip_probability=0.3,
                    activity_consistency_score=0.5,
                    tenure_discount_factor=1.0,
                    historical_claim_rate_zone=0.1,
                    language=getattr(worker, "language_preference", "ta"),
                )

                policy.weekly_premium_amount = _to_float(
                    premium_result.get("premium_amount", 79.0), default=79.0
                )
                policy.model_used = str(premium_result.get("model_used", "stub"))
                policy.shap_explanation_json = premium_result.get("shap_top3", [])
                policy.last_premium_paid_at = now

            policy.next_renewal_at = _next_sunday_midnight(now)

            worker.enrollment_week = _to_int(getattr(worker, "enrollment_week", 1), default=1) + 1

            db.add(
                AuditEvent(
                    event_type="policy_renewed",
                    entity_id=policy.id,
                    entity_type="policy",
                    payload={
                        "worker_id": str(worker.id),
                        "policy_status": policy.status,
                        "coverage_week_number": policy.coverage_week_number,
                        "premium_amount": (
                            float(policy.weekly_premium_amount)
                            if getattr(policy, "weekly_premium_amount", None) is not None
                            else None
                        ),
                        "model_used": getattr(policy, "model_used", None),
                    },
                    actor="system",
                )
            )

            renewed += 1

        db.commit()
        return {
            "processed": len(policies),
            "renewed": renewed,
            "graduated": graduated,
        }
    finally:
        if db_gen is not None and hasattr(db_gen, "close"):
            db_gen.close()
