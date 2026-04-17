from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.policy import Policy
from app.models.trigger import TriggerEvent
from app.models.worker import WorkerProfile
from app.models.zone import ZoneCluster
from app.tasks import aqi_polling, cascade_recovery, trigger_polling, weekly_renewal


class FakeQuery:
    def __init__(self, db: FakeDB, key):
        self.db = db
        self.key = key

    def filter(self, *args, **kwargs):
        _ = args, kwargs
        return self

    def join(self, *args, **kwargs):
        _ = args, kwargs
        return self

    def order_by(self, *args, **kwargs):
        _ = args, kwargs
        return self

    def limit(self, *args, **kwargs):
        _ = args, kwargs
        return self

    def all(self):
        return self.db.all_results.get(self.key, [])

    def first(self):
        return self.db.first_results.get(self.key)

    def count(self):
        return self.db.count_results.get(self.key, 0)

    def scalar(self):
        values = self.db.scalar_results.get(self.key, [])
        if values:
            return values.pop(0)
        return None


class FakeDB:
    def __init__(self):
        self.all_results = {}
        self.first_results = {}
        self.count_results = {}
        self.scalar_results = {}
        self.added = []
        self.commits = 0

    def query(self, *entities):
        key = entities[0] if len(entities) == 1 else tuple(entities)
        return FakeQuery(self, key)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        return None

    def commit(self):
        self.commits += 1


def test_trigger_polling_calls_composite_with_rainfall_inputs(monkeypatch):
    fake_db = FakeDB()
    fake_zone = SimpleNamespace(id=1, centroid_lat=13.08, centroid_lon=80.27, flood_tier_numeric=3)
    fake_db.all_results[ZoneCluster] = [fake_zone]
    fake_db.first_results[TriggerEvent] = None

    monkeypatch.setattr(trigger_polling, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))

    def fake_run_async(coro):
        coro.close()
        return {"max_precipitation_24h_mm": 80.0, "max_temperature_2m_c": 40.0}

    monkeypatch.setattr(trigger_polling, "_run_async", fake_run_async)
    monkeypatch.setattr(trigger_polling, "classify_heat", lambda *_: {"triggered": False, "signal_weight": 0.0})
    monkeypatch.setattr(trigger_polling, "check_aqi_trigger", lambda *_: {"triggered": False, "latest_aqi": None})

    captured = {}

    def fake_classify_rainfall(mm):
        captured["rain_mm"] = mm
        return {"triggered": True, "category": "heavy_rain", "signal_weight": 0.35}

    def fake_composite(**kwargs):
        captured["kwargs"] = kwargs
        return {
            "composite_score": 0.75,
            "sources_confirmed": 2,
            "decision": "trigger_corroborated",
            "fast_path_used": False,
        }

    monkeypatch.setattr(trigger_polling, "classify_rainfall", fake_classify_rainfall)
    monkeypatch.setattr(trigger_polling, "compute_composite_score", fake_composite)
    monkeypatch.setattr(trigger_polling.initiate_zone_payouts, "delay", lambda *args, **kwargs: None)

    result = trigger_polling.poll_all_zones()

    assert captured["rain_mm"] == 80.0
    assert captured["kwargs"]["rainfall_triggered"] is True
    assert result["triggers_created"] == 1


def test_trigger_polling_below_threshold_creates_no_trigger(monkeypatch):
    fake_db = FakeDB()
    fake_zone = SimpleNamespace(id=2, centroid_lat=13.08, centroid_lon=80.27, flood_tier_numeric=2)
    fake_db.all_results[ZoneCluster] = [fake_zone]

    monkeypatch.setattr(trigger_polling, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))

    def fake_run_async(coro):
        coro.close()
        return {"max_precipitation_24h_mm": 20.0, "max_temperature_2m_c": 35.0}

    monkeypatch.setattr(trigger_polling, "_run_async", fake_run_async)
    monkeypatch.setattr(trigger_polling, "classify_rainfall", lambda *_: {"triggered": False, "category": None, "signal_weight": 0.0})
    monkeypatch.setattr(trigger_polling, "classify_heat", lambda *_: {"triggered": False, "signal_weight": 0.0})
    monkeypatch.setattr(trigger_polling, "check_aqi_trigger", lambda *_: {"triggered": False, "latest_aqi": None})
    monkeypatch.setattr(
        trigger_polling,
        "compute_composite_score",
        lambda **_: {
            "composite_score": 0.4,
            "sources_confirmed": 1,
            "decision": "no_trigger",
            "fast_path_used": False,
        },
    )

    result = trigger_polling.poll_all_zones()

    assert result["triggers_created"] == 0
    assert not any(isinstance(obj, TriggerEvent) for obj in fake_db.added)


def test_weekly_renewal_waiting_worker_stays_waiting(monkeypatch):
    now = datetime.now(timezone.utc)
    fake_db = FakeDB()

    policy = SimpleNamespace(
        id="policy-1",
        worker_id="worker-1",
        status="waiting",
        coverage_week_number=1,
        weekly_premium_amount=79.0,
        model_used=None,
        shap_explanation_json=None,
        next_renewal_at=None,
    )
    worker = SimpleNamespace(
        id="worker-1",
        enrollment_date=now - timedelta(days=10),
        enrollment_week=1,
        zone_cluster_id=1,
        flood_hazard_tier="medium",
        platform="zomato",
        language_preference="ta",
    )

    fake_db.all_results[Policy] = [policy]
    fake_db.first_results[WorkerProfile] = worker

    monkeypatch.setattr(weekly_renewal, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))

    result = weekly_renewal.renew_all_policies()

    assert result["graduated"] == 0
    assert policy.status == "waiting"


def test_weekly_renewal_worker_at_28_days_becomes_active(monkeypatch):
    now = datetime.now(timezone.utc)
    fake_db = FakeDB()

    policy = SimpleNamespace(
        id="policy-2",
        worker_id="worker-2",
        status="waiting",
        coverage_week_number=1,
        weekly_premium_amount=79.0,
        model_used=None,
        shap_explanation_json=None,
        next_renewal_at=None,
        coverage_start_date=None,
        last_premium_paid_at=None,
    )
    worker = SimpleNamespace(
        id="worker-2",
        enrollment_date=now - timedelta(days=28),
        enrollment_week=1,
        zone_cluster_id=1,
        flood_hazard_tier="high",
        platform="zomato",
        language_preference="ta",
    )
    zone = SimpleNamespace(id=1, zone_rate_mid=20.0)

    fake_db.all_results[Policy] = [policy]
    fake_db.first_results[WorkerProfile] = worker
    fake_db.first_results[ZoneCluster] = zone
    fake_db.scalar_results[(weekly_renewal.func.coalesce(weekly_renewal.func.sum(weekly_renewal.DeliveryHistory.deliveries_count), 0),)] = [300]

    monkeypatch.setattr(weekly_renewal, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))
    monkeypatch.setattr(
        weekly_renewal,
        "calculate_premium",
        lambda **_: {
            "premium_amount": 90.0,
            "model_used": "stub",
            "recency_multiplier": 1.0,
            "shap_top3": [],
            "affordability_capped": False,
        },
    )
    monkeypatch.setattr(weekly_renewal, "_estimate_delivery_baseline_30d", lambda *_, **__: 300.0)
    monkeypatch.setattr(weekly_renewal, "_estimate_income_baseline_weekly", lambda *_, **__: 1400.0)

    result = weekly_renewal.renew_all_policies()

    assert result["graduated"] == 1
    assert policy.status == "active"
    assert policy.weekly_premium_amount == 90.0


def test_cascade_recovery_closes_when_all_sources_clear(monkeypatch):
    now = datetime.now(timezone.utc)
    fake_db = FakeDB()

    trigger = SimpleNamespace(
        id="trig-1",
        status="active",
        zone_cluster_id=1,
        triggered_at=now - timedelta(days=1),
        closed_at=None,
    )
    zone = SimpleNamespace(id=1, centroid_lat=13.08, centroid_lon=80.27)

    fake_db.all_results[TriggerEvent] = [trigger]
    fake_db.first_results[ZoneCluster] = zone

    monkeypatch.setattr(cascade_recovery, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))

    def fake_run_async(coro):
        coro.close()
        return {"max_precipitation_24h_mm": 10.0}

    monkeypatch.setattr(cascade_recovery, "_run_async", fake_run_async)
    monkeypatch.setattr(cascade_recovery, "classify_rainfall", lambda *_: {"triggered": False})
    monkeypatch.setattr(cascade_recovery, "is_zone_suspended", lambda *_: False)
    monkeypatch.setattr(cascade_recovery, "check_aqi_trigger", lambda *_: {"triggered": False})

    result = cascade_recovery.check_recovering_zones()

    assert result["closed"] == 1
    assert trigger.status == "closed"


def test_cascade_recovery_closes_when_cascade_day_greater_than_5(monkeypatch):
    now = datetime.now(timezone.utc)
    fake_db = FakeDB()

    trigger = SimpleNamespace(
        id="trig-2",
        status="recovering",
        zone_cluster_id=1,
        triggered_at=now - timedelta(days=6),
        closed_at=None,
    )

    fake_db.all_results[TriggerEvent] = [trigger]

    monkeypatch.setattr(cascade_recovery, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))

    result = cascade_recovery.check_recovering_zones()

    assert result["closed"] == 1
    assert trigger.status == "closed"


def test_aqi_polling_calls_poll_aqi_all_zones(monkeypatch):
    fake_db = FakeDB()
    fake_db.all_results[ZoneCluster] = [
        SimpleNamespace(id=1, centroid_lat=13.08, centroid_lon=80.27),
        SimpleNamespace(id=2, centroid_lat=13.10, centroid_lon=80.29),
    ]

    monkeypatch.setattr(aqi_polling, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))

    captured = {}

    def fake_run_async(coro):
        coro.close()
        return {1: {"triggered": False}, 2: {"triggered": True}}

    monkeypatch.setattr(aqi_polling, "_run_async", fake_run_async)

    def fake_poll_aqi_all_zones(payload):
        captured["payload"] = payload

        async def _dummy():
            return {1: {"triggered": False}, 2: {"triggered": True}}

        return _dummy()

    monkeypatch.setattr(aqi_polling, "poll_aqi_all_zones", fake_poll_aqi_all_zones)

    result = aqi_polling.poll_aqi_zones()

    assert len(captured["payload"]) == 2
    assert result == {"zones_polled": 2, "zones_triggered": 1}


def test_aqi_polling_helpers_handle_invalid_values():
    assert aqi_polling._to_float(None, default=1.5) == 1.5
    assert aqi_polling._to_float("x", default=2.5) == 2.5
    assert aqi_polling._to_int(None, default=7) == 7
    assert aqi_polling._to_int("x", default=9) == 9


def test_weekly_renewal_get_current_season_all_buckets():
    assert weekly_renewal.get_current_season(datetime(2026, 7, 1, tzinfo=timezone.utc)) == "SW_monsoon"
    assert weekly_renewal.get_current_season(datetime(2026, 11, 1, tzinfo=timezone.utc)) == "NE_monsoon"
    assert weekly_renewal.get_current_season(datetime(2026, 4, 1, tzinfo=timezone.utc)) == "heat"
    assert weekly_renewal.get_current_season(datetime(2026, 1, 1, tzinfo=timezone.utc)) == "dry"


def test_weekly_renewal_next_sunday_midnight_rolls_forward_week():
    sunday_noon = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc)
    out = weekly_renewal._next_sunday_midnight(sunday_noon)
    assert out.weekday() == 6
    assert out.hour == 0 and out.minute == 0
    assert out.date() == datetime(2026, 4, 12, tzinfo=timezone.utc).date()


def test_weekly_renewal_helpers_coerce_with_defaults():
    assert weekly_renewal._to_float(None, default=3.2) == 3.2
    assert weekly_renewal._to_float("bad", default=4.2) == 4.2
    assert weekly_renewal._to_int(None, default=5) == 5
    assert weekly_renewal._to_int("bad", default=6) == 6


def test_weekly_renewal_estimate_income_zero_when_no_delivery_baseline(monkeypatch):
    fake_db = FakeDB()
    worker = SimpleNamespace(id="worker", zone_cluster_id=1)
    monkeypatch.setattr(weekly_renewal, "_estimate_delivery_baseline_30d", lambda *_, **__: 0.0)
    value = weekly_renewal._estimate_income_baseline_weekly(fake_db, worker, datetime.now(timezone.utc))
    assert value == 0.0


def test_weekly_renewal_estimate_income_uses_default_zone_rate_when_missing(monkeypatch):
    fake_db = FakeDB()
    worker = SimpleNamespace(id="worker", zone_cluster_id=99)
    monkeypatch.setattr(weekly_renewal, "_estimate_delivery_baseline_30d", lambda *_, **__: 300.0)
    value = weekly_renewal._estimate_income_baseline_weekly(fake_db, worker, datetime.now(timezone.utc))
    assert value == pytest.approx((300.0 / 30.0) * 18.0 * 7.0)


def test_aqi_polling_get_db_session_supports_generator(monkeypatch):
    sentinel_db = object()

    def _gen():
        yield sentinel_db

    monkeypatch.setattr(aqi_polling, "get_db", _gen)

    db, db_gen = aqi_polling._get_db_session()
    assert db is sentinel_db
    assert db_gen is not None


def test_aqi_polling_get_db_session_supports_direct_session(monkeypatch):
    sentinel_db = object()
    monkeypatch.setattr(aqi_polling, "get_db", lambda: sentinel_db)

    db, db_gen = aqi_polling._get_db_session()
    assert db is sentinel_db
    assert db_gen is None


def test_aqi_polling_run_async_executes_coroutine():
    async def _coro():
        return {"ok": True}

    assert aqi_polling._run_async(_coro()) == {"ok": True}
