from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.payout import calculator


def _make_worker(
    *,
    worker_id: str = "worker-1",
    platform: str = "zomato",
    zone_cluster_id: int = 1,
    enrollment_date: datetime | None = None,
) -> Any:
    return SimpleNamespace(
        id=worker_id,
        platform=platform,
        zone_cluster_id=zone_cluster_id,
        enrollment_date=enrollment_date or (datetime.now(timezone.utc) - timedelta(days=40)),
    )


def _make_policy(policy_id: str = "policy-1", income_baseline_weekly: float | None = None) -> Any:
    return SimpleNamespace(id=policy_id, income_baseline_weekly=income_baseline_weekly)


@pytest.mark.parametrize(
    ("cascade_day", "expected_multiplier"),
    [(1, 1.0), (2, 0.8), (3, 0.6), (4, 0.4), (5, 0.4)],
)
def test_compute_payout_applies_expected_cascade_multiplier(
    monkeypatch, cascade_day, expected_multiplier
):
    fixed_now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(calculator, "_current_time", lambda: fixed_now)
    monkeypatch.setattr(calculator, "_zone_rate_mid", lambda *_: 20.0)
    monkeypatch.setattr(calculator, "_avg_hourly_deliveries", lambda **_: 10.0)
    monkeypatch.setattr(calculator, "_declared_per_order_rate", lambda **_: 1.0)
    monkeypatch.setattr(
        calculator,
        "_compute_slab_delta",
        lambda **_: {
            "next_threshold": 0.0,
            "next_bonus_amount": 0.0,
            "probability": 0.0,
            "matched_days": 0.0,
            "reached_days": 0.0,
            "fallback_used": 0.0,
            "slab_delta": 0.0,
        },
    )
    monkeypatch.setattr(
        calculator,
        "_monthly_proximity",
        lambda **_: {
            "monthly_proximity": 0.0,
            "cumulative_monthly_deliveries": 0.0,
            "deliveries_needed": 0.0,
            "remaining_days": 0.0,
            "typical_daily_rate": 0.0,
            "probability_would_hit_200": 0.0,
            "activated": 0.0,
        },
    )
    monkeypatch.setattr(calculator, "_zone_order_volume_ratio", lambda **_: 1.0)

    result = calculator.compute_payout(
        worker=_make_worker(enrollment_date=fixed_now - timedelta(days=40)),
        policy=_make_policy(income_baseline_weekly=10000.0),
        deliveries_completed_today=10,
        disruption_duration_hours=1.0,
        cascade_day=cascade_day,
        trigger_type="heavy_rain",
        db=MagicMock(),
    )

    assert result["cascade_multiplier"] == expected_multiplier
    assert result["total_payout"] == round(10.0 * expected_multiplier, 2)


def test_compute_payout_caps_at_weekly_baseline(monkeypatch):
    fixed_now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(calculator, "_current_time", lambda: fixed_now)
    monkeypatch.setattr(calculator, "_zone_rate_mid", lambda *_: 20.0)
    monkeypatch.setattr(calculator, "_avg_hourly_deliveries", lambda **_: 100.0)
    monkeypatch.setattr(calculator, "_declared_per_order_rate", lambda **_: 2.0)
    monkeypatch.setattr(
        calculator,
        "_compute_slab_delta",
        lambda **_: {
            "next_threshold": 12.0,
            "next_bonus_amount": 120.0,
            "probability": 0.6,
            "matched_days": 10.0,
            "reached_days": 6.0,
            "fallback_used": 0.0,
            "slab_delta": 72.0,
        },
    )
    monkeypatch.setattr(
        calculator,
        "_monthly_proximity",
        lambda **_: {
            "monthly_proximity": 100.0,
            "cumulative_monthly_deliveries": 180.0,
            "deliveries_needed": 20.0,
            "remaining_days": 3.0,
            "typical_daily_rate": 10.0,
            "probability_would_hit_200": 1.0,
            "activated": 1.0,
        },
    )
    monkeypatch.setattr(calculator, "_zone_order_volume_ratio", lambda **_: 1.0)

    result = calculator.compute_payout(
        worker=_make_worker(enrollment_date=fixed_now - timedelta(days=45)),
        policy=_make_policy(income_baseline_weekly=80.0),
        deliveries_completed_today=10,
        disruption_duration_hours=1.0,
        cascade_day=1,
        trigger_type="heavy_rain",
        db=MagicMock(),
    )

    assert result["total_before_cap"] > 80.0
    assert result["total_payout"] == 80.0


def test_compute_slab_delta_for_probability_point_six_returns_72(monkeypatch):
    fixed_now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    worker = _make_worker(enrollment_date=fixed_now - timedelta(days=45))

    monkeypatch.setattr(calculator, "_next_slab", lambda *_: (12, 120.0))
    monkeypatch.setattr(
        calculator,
        "_slab_reach_probability",
        lambda **_: {
            "probability": 0.6,
            "matched_days": 10.0,
            "reached_days": 6.0,
            "fallback_used": 0.0,
        },
    )

    result = calculator._compute_slab_delta(
        db=MagicMock(),
        worker=worker,
        deliveries_completed_today=10,
        as_of=fixed_now,
        day_of_week=6,
        time_slot=calculator.TimeSlotWindow(label="morning", start_hour=0, end_hour_exclusive=12),
    )

    assert result["next_threshold"] == 12.0
    assert result["probability"] == 0.6
    assert result["slab_delta"] == 72.0


def test_monthly_proximity_is_zero_outside_final_7_days():
    fake_db = MagicMock()

    result = calculator._monthly_proximity(
        db=fake_db,
        worker_id="worker-1",
        as_of=datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc),
    )

    assert result["monthly_proximity"] == 0.0
    assert result["activated"] == 0.0
    fake_db.execute.assert_not_called()


def test_monthly_proximity_is_positive_in_final_7_days_within_window():
    fake_db = MagicMock()

    class _ScalarResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    fake_db.execute.side_effect = [_ScalarResult(180), _ScalarResult(15)]

    result = calculator._monthly_proximity(
        db=fake_db,
        worker_id="worker-1",
        as_of=datetime(2026, 4, 29, 10, 0, tzinfo=timezone.utc),
    )

    assert result["activated"] == 1.0
    assert result["monthly_proximity"] > 0.0


def test_compute_payout_marks_waiting_period_ineligible(monkeypatch):
    fixed_now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(calculator, "_current_time", lambda: fixed_now)

    fake_db = MagicMock()
    result = calculator.compute_payout(
        worker=_make_worker(enrollment_date=fixed_now - timedelta(days=10)),
        policy=_make_policy(income_baseline_weekly=1000.0),
        deliveries_completed_today=8,
        disruption_duration_hours=2.0,
        cascade_day=1,
        trigger_type="heavy_rain",
        db=fake_db,
    )

    assert result["eligible_for_payout"] is False
    assert result["total_payout"] == 0.0
    fake_db.execute.assert_not_called()


def test_compute_payout_validation_errors(monkeypatch):
    fixed_now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(calculator, "_current_time", lambda: fixed_now)

    with pytest.raises(ValueError):
        calculator.compute_payout(
            worker=None,  # type: ignore[arg-type]
            policy=_make_policy(income_baseline_weekly=1000.0),
            deliveries_completed_today=1,
            disruption_duration_hours=1.0,
            cascade_day=1,
            trigger_type="heavy_rain",
            db=MagicMock(),
        )

    with pytest.raises(ValueError):
        calculator.compute_payout(
            worker=_make_worker(enrollment_date=fixed_now - timedelta(days=40)),
            policy=None,  # type: ignore[arg-type]
            deliveries_completed_today=1,
            disruption_duration_hours=1.0,
            cascade_day=1,
            trigger_type="heavy_rain",
            db=MagicMock(),
        )

    with pytest.raises(ValueError):
        calculator.compute_payout(
            worker=_make_worker(enrollment_date=fixed_now - timedelta(days=40)),
            policy=_make_policy(income_baseline_weekly=1000.0),
            deliveries_completed_today=-1,
            disruption_duration_hours=1.0,
            cascade_day=1,
            trigger_type="heavy_rain",
            db=MagicMock(),
        )


def test_compute_payout_applies_peak_multiplier_when_rain_and_ratio_high(monkeypatch):
    fixed_now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(calculator, "_current_time", lambda: fixed_now)
    monkeypatch.setattr(calculator, "_zone_rate_mid", lambda *_: 20.0)
    monkeypatch.setattr(calculator, "_avg_hourly_deliveries", lambda **_: 10.0)
    monkeypatch.setattr(calculator, "_declared_per_order_rate", lambda **_: 1.0)
    monkeypatch.setattr(
        calculator,
        "_compute_slab_delta",
        lambda **_: {
            "next_threshold": 0.0,
            "next_bonus_amount": 0.0,
            "probability": 0.0,
            "matched_days": 0.0,
            "reached_days": 0.0,
            "fallback_used": 0.0,
            "slab_delta": 0.0,
        },
    )
    monkeypatch.setattr(
        calculator,
        "_monthly_proximity",
        lambda **_: {
            "monthly_proximity": 0.0,
            "cumulative_monthly_deliveries": 0.0,
            "deliveries_needed": 0.0,
            "remaining_days": 0.0,
            "typical_daily_rate": 0.0,
            "probability_would_hit_200": 0.0,
            "activated": 0.0,
        },
    )
    monkeypatch.setattr(calculator, "_zone_order_volume_ratio", lambda **_: 1.21)

    result = calculator.compute_payout(
        worker=_make_worker(enrollment_date=fixed_now - timedelta(days=40)),
        policy=_make_policy(income_baseline_weekly=10000.0),
        deliveries_completed_today=0,
        disruption_duration_hours=1.0,
        cascade_day=1,
        trigger_type="heavy_rain",
        db=MagicMock(),
    )

    assert result["peak_multiplier_applied"] is True
    assert result["peak_context_multiplier"] == 1.2
    assert result["total_payout"] == 12.0


def test_compute_payout_uses_history_baseline_when_policy_baseline_missing(monkeypatch):
    fixed_now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(calculator, "_current_time", lambda: fixed_now)
    monkeypatch.setattr(calculator, "_zone_rate_mid", lambda *_: 20.0)
    monkeypatch.setattr(calculator, "_avg_hourly_deliveries", lambda **_: 10.0)
    monkeypatch.setattr(calculator, "_declared_per_order_rate", lambda **_: 1.0)
    monkeypatch.setattr(
        calculator,
        "_compute_slab_delta",
        lambda **_: {
            "next_threshold": 0.0,
            "next_bonus_amount": 0.0,
            "probability": 0.0,
            "matched_days": 0.0,
            "reached_days": 0.0,
            "fallback_used": 0.0,
            "slab_delta": 0.0,
        },
    )
    monkeypatch.setattr(
        calculator,
        "_monthly_proximity",
        lambda **_: {
            "monthly_proximity": 0.0,
            "cumulative_monthly_deliveries": 0.0,
            "deliveries_needed": 0.0,
            "remaining_days": 0.0,
            "typical_daily_rate": 0.0,
            "probability_would_hit_200": 0.0,
            "activated": 0.0,
        },
    )
    monkeypatch.setattr(calculator, "_zone_order_volume_ratio", lambda **_: 1.0)
    monkeypatch.setattr(calculator, "_weekly_baseline_from_history", lambda **_: 8.0)

    result = calculator.compute_payout(
        worker=_make_worker(enrollment_date=fixed_now - timedelta(days=40)),
        policy=_make_policy(income_baseline_weekly=None),
        deliveries_completed_today=0,
        disruption_duration_hours=1.0,
        cascade_day=1,
        trigger_type="heavy_rain",
        db=MagicMock(),
    )

    assert result["weekly_baseline_cap"] == 8.0
    assert result["total_payout"] == 8.0
