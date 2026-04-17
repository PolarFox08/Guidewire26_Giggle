"""Payout calculator for parametric claim settlements."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import and_, case, extract, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.delivery import DeliveryHistory
from app.models.policy import Policy
from app.models.slab import SlabConfig
from app.models.worker import WorkerProfile
from app.models.zone import ZoneCluster

DEFAULT_SLAB_PROBABILITY = 0.30
PEAK_MULTIPLIER = 1.20
PEAK_RATIO_THRESHOLD = 1.20
MONTHLY_TARGET_DELIVERIES = 200
MONTHLY_PROXIMITY_WINDOW = 30
WAITING_PERIOD_DAYS = 28


@runtime_checkable
class WorkerLike(Protocol):
    id: Any
    platform: Any
    zone_cluster_id: Any
    enrollment_date: Any


@runtime_checkable
class PolicyLike(Protocol):
    id: Any
    income_baseline_weekly: Any


@dataclass(frozen=True)
class TimeSlotWindow:
    """Represents a day-part window used by payout logic."""

    label: str
    start_hour: int
    end_hour_exclusive: int


def _current_time() -> datetime:
    return datetime.now(timezone.utc)


def _get_time_slot(now: datetime) -> TimeSlotWindow:
    hour = now.hour
    if hour < 12:
        return TimeSlotWindow(label="morning", start_hour=0, end_hour_exclusive=12)
    if hour < 17:
        return TimeSlotWindow(label="afternoon", start_hour=12, end_hour_exclusive=17)
    return TimeSlotWindow(label="evening", start_hour=17, end_hour_exclusive=24)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _cascade_multiplier(cascade_day: int) -> float:
    mapping = {
        1: 1.0,
        2: 0.8,
        3: 0.6,
        4: 0.4,
        5: 0.4,
    }
    return mapping.get(cascade_day, 0.0)


def _waiting_period_complete(worker: WorkerLike, as_of: datetime) -> bool:
    enrollment_date = getattr(worker, "enrollment_date", None)
    if enrollment_date is None:
        return False

    if enrollment_date.tzinfo is None:
        enrollment_date = enrollment_date.replace(tzinfo=timezone.utc)

    elapsed_days = (as_of - enrollment_date).days
    return elapsed_days >= WAITING_PERIOD_DAYS


def _zone_rate_mid(db: Session, zone_cluster_id: int) -> float:
    stmt = select(ZoneCluster.zone_rate_mid).where(ZoneCluster.id == zone_cluster_id)
    value = db.execute(stmt).scalar_one_or_none()
    return _safe_float(value, default=0.0)


def _avg_hourly_deliveries(
    db: Session,
    worker_id: Any,
    as_of: datetime,
    day_of_week: int,
    time_slot: TimeSlotWindow,
) -> float:
    start_at = as_of - timedelta(days=30)
    stmt = (
        select(func.avg(DeliveryHistory.deliveries_count))
        .where(
            DeliveryHistory.worker_id == worker_id,
            DeliveryHistory.recorded_at >= start_at,
            DeliveryHistory.recorded_at <= as_of,
            extract("dow", DeliveryHistory.recorded_at) == day_of_week,
            extract("hour", DeliveryHistory.recorded_at) >= time_slot.start_hour,
            extract("hour", DeliveryHistory.recorded_at) < time_slot.end_hour_exclusive,
        )
    )
    return max(0.0, _safe_float(db.execute(stmt).scalar_one_or_none(), default=0.0))


def _declared_per_order_rate(
    db: Session,
    worker_id: Any,
    as_of: datetime,
    zone_rate_mid: float,
) -> float:
    start_at = as_of - timedelta(days=30)

    ratio_stmt = (
        select(
            func.sum(DeliveryHistory.earnings_declared),
            func.sum(DeliveryHistory.deliveries_count),
        )
        .where(
            DeliveryHistory.worker_id == worker_id,
            DeliveryHistory.recorded_at >= start_at,
            DeliveryHistory.recorded_at <= as_of,
            DeliveryHistory.earnings_declared.is_not(None),
            DeliveryHistory.deliveries_count > 0,
        )
    )

    row = db.execute(ratio_stmt).first()
    earnings_sum = _safe_float(row[0] if row else None, default=0.0)
    deliveries_sum = _safe_float(row[1] if row else None, default=0.0)

    if deliveries_sum <= 0:
        base_rate = zone_rate_mid
    else:
        base_rate = earnings_sum / deliveries_sum

    capped_rate = min(base_rate, zone_rate_mid * 1.5 if zone_rate_mid > 0 else base_rate)
    return max(0.0, capped_rate)


def _next_slab(db: Session, platform: str, deliveries_completed_today: int) -> tuple[int, float] | None:
    stmt = (
        select(SlabConfig.deliveries_threshold, SlabConfig.bonus_amount)
        .where(
            SlabConfig.platform == platform,
            SlabConfig.is_active.is_(True),
            SlabConfig.deliveries_threshold > deliveries_completed_today,
        )
        .order_by(SlabConfig.deliveries_threshold.asc())
        .limit(1)
    )
    row = db.execute(stmt).first()
    if not row:
        return None
    return int(row[0]), _safe_float(row[1], default=0.0)


def _slab_reach_probability(
    db: Session,
    worker_id: Any,
    as_of: datetime,
    day_of_week: int,
    time_slot: TimeSlotWindow,
    deliveries_completed_today: int,
    next_threshold: int,
) -> dict[str, float]:
    """Estimate P(slab_missed) from the worker's last 30-day history."""

    start_at = as_of - timedelta(days=30)
    day_key = func.date(DeliveryHistory.recorded_at)

    trigger_slot_total = func.sum(
        case(
            (
                and_(
                    extract("hour", DeliveryHistory.recorded_at) >= time_slot.start_hour,
                    extract("hour", DeliveryHistory.recorded_at) < time_slot.end_hour_exclusive,
                ),
                DeliveryHistory.deliveries_count,
            ),
            else_=0,
        )
    )

    daily_agg_subq = (
        select(
            day_key.label("delivery_day"),
            func.sum(DeliveryHistory.deliveries_count).label("daily_total"),
            trigger_slot_total.label("trigger_slot_total"),
        )
        .where(
            DeliveryHistory.worker_id == worker_id,
            DeliveryHistory.recorded_at >= start_at,
            DeliveryHistory.recorded_at <= as_of,
            extract("dow", DeliveryHistory.recorded_at) == day_of_week,
        )
        .group_by(day_key)
        .subquery()
    )

    stats_stmt = select(
        func.count().label("matched_days"),
        func.sum(
            case(
                (daily_agg_subq.c.daily_total >= next_threshold, 1),
                else_=0,
            )
        ).label("reached_days"),
    ).where(
        daily_agg_subq.c.trigger_slot_total.between(
            deliveries_completed_today - 1, deliveries_completed_today + 1
        )
    )

    row = db.execute(stats_stmt).first()
    matched_days = int(_safe_float(row[0] if row else 0, default=0.0))
    reached_days = int(_safe_float(row[1] if row else 0, default=0.0))

    if matched_days < 5:
        return {
            "probability": DEFAULT_SLAB_PROBABILITY,
            "matched_days": float(matched_days),
            "reached_days": float(reached_days),
            "fallback_used": 1.0,
        }

    probability = reached_days / matched_days if matched_days > 0 else DEFAULT_SLAB_PROBABILITY
    probability = max(0.0, min(1.0, probability))
    return {
        "probability": probability,
        "matched_days": float(matched_days),
        "reached_days": float(reached_days),
        "fallback_used": 0.0,
    }


def _compute_slab_delta(
    db: Session,
    worker: WorkerLike,
    deliveries_completed_today: int,
    as_of: datetime,
    day_of_week: int,
    time_slot: TimeSlotWindow,
) -> dict[str, float]:
    platform = str(getattr(worker, "platform", ""))
    slab = _next_slab(db, platform, deliveries_completed_today)
    if slab is None:
        return {
            "next_threshold": 0.0,
            "next_bonus_amount": 0.0,
            "probability": 0.0,
            "matched_days": 0.0,
            "reached_days": 0.0,
            "fallback_used": 0.0,
            "slab_delta": 0.0,
        }

    next_threshold, bonus_amount = slab
    probability_stats = _slab_reach_probability(
        db=db,
        worker_id=worker.id,
        as_of=as_of,
        day_of_week=day_of_week,
        time_slot=time_slot,
        deliveries_completed_today=deliveries_completed_today,
        next_threshold=next_threshold,
    )
    slab_delta = probability_stats["probability"] * bonus_amount

    return {
        "next_threshold": float(next_threshold),
        "next_bonus_amount": bonus_amount,
        "probability": probability_stats["probability"],
        "matched_days": probability_stats["matched_days"],
        "reached_days": probability_stats["reached_days"],
        "fallback_used": probability_stats["fallback_used"],
        "slab_delta": max(0.0, slab_delta),
    }


def _monthly_proximity(
    db: Session,
    worker_id: Any,
    as_of: datetime,
) -> dict[str, float]:
    _, days_in_month = calendar.monthrange(as_of.year, as_of.month)
    remaining_days = days_in_month - as_of.day + 1

    if remaining_days > 7:
        return {
            "monthly_proximity": 0.0,
            "cumulative_monthly_deliveries": 0.0,
            "deliveries_needed": 0.0,
            "remaining_days": float(remaining_days),
            "typical_daily_rate": 0.0,
            "probability_would_hit_200": 0.0,
            "activated": 0.0,
        }

    month_start = datetime(as_of.year, as_of.month, 1, tzinfo=as_of.tzinfo)
    cumulative_stmt = select(func.sum(DeliveryHistory.deliveries_count)).where(
        DeliveryHistory.worker_id == worker_id,
        DeliveryHistory.recorded_at >= month_start,
        DeliveryHistory.recorded_at <= as_of,
    )
    cumulative_monthly_deliveries = max(
        0.0, _safe_float(db.execute(cumulative_stmt).scalar_one_or_none(), default=0.0)
    )

    deliveries_needed = MONTHLY_TARGET_DELIVERIES - cumulative_monthly_deliveries
    if deliveries_needed <= 0 or deliveries_needed > MONTHLY_PROXIMITY_WINDOW:
        return {
            "monthly_proximity": 0.0,
            "cumulative_monthly_deliveries": cumulative_monthly_deliveries,
            "deliveries_needed": deliveries_needed,
            "remaining_days": float(remaining_days),
            "typical_daily_rate": 0.0,
            "probability_would_hit_200": 0.0,
            "activated": 0.0,
        }

    last_30d_start = as_of - timedelta(days=30)
    daily_subq = (
        select(
            func.date(DeliveryHistory.recorded_at).label("delivery_day"),
            func.sum(DeliveryHistory.deliveries_count).label("daily_total"),
        )
        .where(
            DeliveryHistory.worker_id == worker_id,
            DeliveryHistory.recorded_at >= last_30d_start,
            DeliveryHistory.recorded_at <= as_of,
        )
        .group_by(func.date(DeliveryHistory.recorded_at))
        .subquery()
    )
    typical_daily_rate_stmt = select(func.avg(daily_subq.c.daily_total))
    typical_daily_rate = max(
        0.0, _safe_float(db.execute(typical_daily_rate_stmt).scalar_one_or_none(), default=0.0)
    )

    if typical_daily_rate <= 0:
        probability = 0.0
    else:
        probability = min(
            1.0, (typical_daily_rate * remaining_days) / float(deliveries_needed)
        )

    monthly_proximity = max(0.0, probability * 2000.0)
    return {
        "monthly_proximity": monthly_proximity,
        "cumulative_monthly_deliveries": cumulative_monthly_deliveries,
        "deliveries_needed": deliveries_needed,
        "remaining_days": float(remaining_days),
        "typical_daily_rate": typical_daily_rate,
        "probability_would_hit_200": probability,
        "activated": 1.0,
    }


def _zone_order_volume_ratio(db: Session, zone_cluster_id: int, as_of: datetime) -> float:
    last_hour_start = as_of - timedelta(hours=1)
    lookback_start = as_of - timedelta(days=28)

    last_hour_stmt = (
        select(func.count())
        .select_from(DeliveryHistory)
        .join(WorkerProfile, WorkerProfile.id == DeliveryHistory.worker_id)
        .where(
            WorkerProfile.zone_cluster_id == zone_cluster_id,
            DeliveryHistory.recorded_at >= last_hour_start,
            DeliveryHistory.recorded_at <= as_of,
        )
    )
    last_hour_count = _safe_float(db.execute(last_hour_stmt).scalar_one_or_none(), default=0.0)

    historical_hour_stmt = (
        select(func.count())
        .select_from(DeliveryHistory)
        .join(WorkerProfile, WorkerProfile.id == DeliveryHistory.worker_id)
        .where(
            WorkerProfile.zone_cluster_id == zone_cluster_id,
            DeliveryHistory.recorded_at >= lookback_start,
            DeliveryHistory.recorded_at < last_hour_start,
            extract("hour", DeliveryHistory.recorded_at) == as_of.hour,
        )
    )
    historical_same_hour_count = _safe_float(
        db.execute(historical_hour_stmt).scalar_one_or_none(), default=0.0
    )

    if historical_same_hour_count <= 0:
        return 1.0

    rolling_average = historical_same_hour_count / 28.0
    if rolling_average <= 0:
        return 1.0

    return last_hour_count / rolling_average


def _weekly_baseline_from_history(
    db: Session,
    worker_id: Any,
    as_of: datetime,
    zone_rate_mid: float,
) -> float:
    start_at = as_of - timedelta(days=30)

    daily_totals_subq = (
        select(
            func.date(DeliveryHistory.recorded_at).label("delivery_day"),
            func.sum(DeliveryHistory.deliveries_count).label("daily_total"),
        )
        .where(
            DeliveryHistory.worker_id == worker_id,
            DeliveryHistory.recorded_at >= start_at,
            DeliveryHistory.recorded_at <= as_of,
        )
        .group_by(func.date(DeliveryHistory.recorded_at))
        .subquery()
    )

    avg_daily_stmt = select(func.avg(daily_totals_subq.c.daily_total))
    avg_daily_deliveries = _safe_float(db.execute(avg_daily_stmt).scalar_one_or_none(), default=0.0)

    if avg_daily_deliveries <= 0 or zone_rate_mid <= 0:
        return 0.0

    return avg_daily_deliveries * zone_rate_mid * 7.0


def compute_payout(
    worker: WorkerLike,
    policy: PolicyLike,
    deliveries_completed_today: int,
    disruption_duration_hours: float,
    cascade_day: int,
    trigger_type: str,
    db: Session,
) -> dict[str, Any]:
    """Compute payout components and final payable amount for a triggered worker claim."""

    _ = get_db  # Explicit import usage for compatibility with dependency wiring.

    if worker is None:
        raise ValueError("worker is required")
    if policy is None:
        raise ValueError("policy is required")
    if db is None:
        raise ValueError("db session is required")
    if deliveries_completed_today < 0:
        raise ValueError("deliveries_completed_today must be >= 0")
    if disruption_duration_hours < 0:
        raise ValueError("disruption_duration_hours must be >= 0")
    if cascade_day < 1:
        raise ValueError("cascade_day must be >= 1")

    as_of = _current_time()
    day_of_week = int(as_of.strftime("%w"))
    time_slot = _get_time_slot(as_of)

    if not _waiting_period_complete(worker, as_of):
        breakdown_json = {
            "eligibility": {
                "waiting_period_complete": False,
                "waiting_period_days": WAITING_PERIOD_DAYS,
            }
        }
        return {
            "eligible_for_payout": False,
            "base_loss": 0.0,
            "slab_delta": 0.0,
            "monthly_proximity": 0.0,
            "peak_multiplier_applied": False,
            "peak_context_multiplier": 1.0,
            "zone_order_volume_ratio": 1.0,
            "cascade_day": cascade_day,
            "cascade_multiplier": _cascade_multiplier(cascade_day),
            "total_before_cap": 0.0,
            "weekly_baseline_cap": 0.0,
            "total_payout": 0.0,
            "breakdown_json": breakdown_json,
        }

    worker_platform = str(getattr(worker, "platform", ""))
    worker_zone_cluster_id = int(_safe_float(getattr(worker, "zone_cluster_id", 0), default=0.0))

    zone_rate_mid = _zone_rate_mid(db, worker_zone_cluster_id)

    avg_hourly = _avg_hourly_deliveries(
        db=db,
        worker_id=worker.id,
        as_of=as_of,
        day_of_week=day_of_week,
        time_slot=time_slot,
    )
    missed_deliveries = max(0.0, avg_hourly * disruption_duration_hours)

    per_order_rate = _declared_per_order_rate(
        db=db,
        worker_id=worker.id,
        as_of=as_of,
        zone_rate_mid=zone_rate_mid,
    )
    base_loss = max(0.0, missed_deliveries * per_order_rate)

    slab_stats = _compute_slab_delta(
        db=db,
        worker=worker,
        deliveries_completed_today=deliveries_completed_today,
        as_of=as_of,
        day_of_week=day_of_week,
        time_slot=time_slot,
    )
    slab_delta = max(0.0, slab_stats["slab_delta"])

    monthly_stats = _monthly_proximity(db=db, worker_id=worker.id, as_of=as_of)
    monthly_proximity = max(0.0, monthly_stats["monthly_proximity"])

    zone_ratio = _zone_order_volume_ratio(
        db=db,
        zone_cluster_id=worker_zone_cluster_id,
        as_of=as_of,
    )
    peak_multiplier_applied = trigger_type == "heavy_rain" and zone_ratio > PEAK_RATIO_THRESHOLD
    peak_context_multiplier = PEAK_MULTIPLIER if peak_multiplier_applied else 1.0

    cascade_multiplier = _cascade_multiplier(cascade_day)

    subtotal_before_peak = base_loss + slab_delta + monthly_proximity
    total_before_cap = subtotal_before_peak * peak_context_multiplier * cascade_multiplier

    policy_baseline = _safe_float(getattr(policy, "income_baseline_weekly", None), default=0.0)
    weekly_baseline = (
        policy_baseline
        if policy_baseline > 0
        else _weekly_baseline_from_history(
            db=db,
            worker_id=worker.id,
            as_of=as_of,
            zone_rate_mid=zone_rate_mid,
        )
    )

    if weekly_baseline > 0:
        final_payout = min(total_before_cap, weekly_baseline)
    else:
        final_payout = total_before_cap
    final_payout = max(0.0, final_payout)

    breakdown_json = {
        "inputs": {
            "worker_id": str(worker.id),
            "policy_id": str(policy.id),
            "deliveries_completed_today": deliveries_completed_today,
            "disruption_duration_hours": disruption_duration_hours,
            "cascade_day": cascade_day,
            "trigger_type": trigger_type,
            "calculation_time": as_of.isoformat(),
            "day_of_week": day_of_week,
            "time_slot": time_slot.label,
        },
        "base_loss": {
            "zone_rate_mid": zone_rate_mid,
            "worker_platform": worker_platform,
            "worker_zone_cluster_id": worker_zone_cluster_id,
            "avg_hourly_deliveries": avg_hourly,
            "missed_deliveries": missed_deliveries,
            "per_order_rate": per_order_rate,
            "base_loss": base_loss,
        },
        "slab_delta": slab_stats,
        "monthly_proximity": monthly_stats,
        "peak_context": {
            "zone_order_volume_ratio": zone_ratio,
            "threshold": PEAK_RATIO_THRESHOLD,
            "peak_multiplier_applied": peak_multiplier_applied,
            "peak_context_multiplier": peak_context_multiplier,
        },
        "cascade": {
            "cascade_multiplier": cascade_multiplier,
        },
        "cap": {
            "weekly_baseline_cap": weekly_baseline,
            "total_before_cap": total_before_cap,
            "final_payout": final_payout,
        },
    }

    return {
        "eligible_for_payout": True,
        "base_loss": round(base_loss, 2),
        "slab_delta": round(slab_delta, 2),
        "monthly_proximity": round(monthly_proximity, 2),
        "peak_multiplier_applied": peak_multiplier_applied,
        "peak_context_multiplier": round(peak_context_multiplier, 3),
        "zone_order_volume_ratio": round(zone_ratio, 3),
        "cascade_day": cascade_day,
        "cascade_multiplier": round(cascade_multiplier, 3),
        "total_before_cap": round(max(0.0, total_before_cap), 2),
        "weekly_baseline_cap": round(max(0.0, weekly_baseline), 2),
        "total_payout": round(final_payout, 2),
        "breakdown_json": breakdown_json,
    }


__all__ = ["compute_payout", "_cascade_multiplier", "_compute_slab_delta", "_monthly_proximity"]
