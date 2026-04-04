from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.claims import Claim
from app.models.policy import Policy
from app.models.trigger import TriggerEvent
from app.models.worker import WorkerProfile
from app.models.zone import ZoneCluster
from app.tasks import trigger_polling


class _FakeQuery:
    def __init__(self, db: _FakeDB, key):
        self.db = db
        self.key = key

    def filter(self, *args, **kwargs):
        _ = args
        _ = kwargs
        return self

    def join(self, *args, **kwargs):
        _ = args
        _ = kwargs
        return self

    def order_by(self, *args, **kwargs):
        _ = args
        _ = kwargs
        return self

    def limit(self, *args, **kwargs):
        _ = args
        _ = kwargs
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


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.flushes = 0
        self.all_results = {}
        self.first_results = {}
        self.count_results = {}
        self.scalar_results = {}

    def query(self, *entities):
        key = entities[0] if len(entities) == 1 else tuple(entities)
        return _FakeQuery(self, key)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushes += 1

    def commit(self):
        self.commits += 1


def test_poll_all_zones_calls_classify_and_composite_for_rainfall(monkeypatch):
    fake_db = _FakeDB()
    fake_zone = SimpleNamespace(
        id=1,
        centroid_lat=13.08,
        centroid_lon=80.27,
        flood_tier_numeric=3,
    )

    fake_db.all_results[ZoneCluster] = [fake_zone]
    fake_db.first_results[TriggerEvent] = None

    monkeypatch.setattr(trigger_polling, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))

    def fake_run_async(coro):
        coro.close()
        return {"max_precipitation_24h_mm": 80.0, "max_temperature_2m_c": 40.0}

    monkeypatch.setattr(trigger_polling, "_run_async", fake_run_async)

    captured = {}

    def fake_classify_rainfall(mm):
        captured["rain_mm"] = mm
        return {"triggered": True, "category": "heavy_rain", "signal_weight": 0.35}

    def fake_compute_composite_score(**kwargs):
        captured["composite_kwargs"] = kwargs
        return {
            "composite_score": 0.75,
            "sources_confirmed": 2,
            "decision": "trigger_corroborated",
            "fast_path_used": False,
        }

    monkeypatch.setattr(trigger_polling, "classify_rainfall", fake_classify_rainfall)
    monkeypatch.setattr(trigger_polling, "classify_heat", lambda *_: {"triggered": False, "signal_weight": 0.0})
    monkeypatch.setattr(trigger_polling, "check_aqi_trigger", lambda *_: {"triggered": False, "latest_aqi": None})
    monkeypatch.setattr(trigger_polling, "compute_composite_score", fake_compute_composite_score)

    called = {"delay": 0}
    monkeypatch.setattr(trigger_polling.initiate_zone_payouts, "delay", lambda *args, **kwargs: called.__setitem__("delay", called["delay"] + 1))

    result = trigger_polling.poll_all_zones()

    assert captured["rain_mm"] == 80.0
    assert captured["composite_kwargs"]["rainfall_triggered"] is True
    assert result["triggers_created"] == 1
    assert called["delay"] == 1


def test_poll_all_zones_does_not_create_trigger_when_score_below_threshold(monkeypatch):
    fake_db = _FakeDB()
    fake_zone = SimpleNamespace(
        id=2,
        centroid_lat=13.09,
        centroid_lon=80.28,
        flood_tier_numeric=2,
    )
    fake_db.all_results[ZoneCluster] = [fake_zone]

    monkeypatch.setattr(trigger_polling, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))

    def fake_run_async(coro):
        coro.close()
        return {"max_precipitation_24h_mm": 50.0, "max_temperature_2m_c": 35.0}

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

    called = {"delay": 0}
    monkeypatch.setattr(trigger_polling.initiate_zone_payouts, "delay", lambda *args, **kwargs: called.__setitem__("delay", called["delay"] + 1))

    result = trigger_polling.poll_all_zones()

    assert result["triggers_created"] == 0
    assert called["delay"] == 0
    assert not any(isinstance(obj, TriggerEvent) for obj in fake_db.added)


def test_initiate_zone_payouts_skips_worker_in_waiting_period(monkeypatch):
    now = datetime.now(timezone.utc)
    fake_db = _FakeDB()

    fake_trigger = SimpleNamespace(id="trigger-1", trigger_type="heavy_rain")
    fake_worker = SimpleNamespace(
        id="worker-1",
        zone_cluster_id=1,
        is_active=True,
        enrollment_date=now - timedelta(days=10),
        upi_vpa="worker@okaxis",
    )
    fake_policy = SimpleNamespace(id="policy-1", status="active")

    fake_db.first_results[TriggerEvent] = fake_trigger
    fake_db.all_results[(WorkerProfile, Policy)] = [(fake_worker, fake_policy)]

    monkeypatch.setattr(trigger_polling, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))
    monkeypatch.setattr(trigger_polling, "compute_payout", lambda **_: {"eligible_for_payout": True})

    result = trigger_polling.initiate_zone_payouts("trigger-1", 1, cascade_day=1)

    assert result["claims_created"] == 0
    assert not any(isinstance(obj, Claim) for obj in fake_db.added)


def test_initiate_zone_payouts_creates_claim_and_payout_for_auto_approve(monkeypatch):
    now = datetime.now(timezone.utc)
    fake_db = _FakeDB()

    fake_trigger = SimpleNamespace(id="trigger-2", trigger_type="heavy_rain")
    fake_worker = SimpleNamespace(
        id="worker-2",
        zone_cluster_id=1,
        is_active=True,
        enrollment_date=now - timedelta(days=40),
        upi_vpa="worker@okaxis",
    )
    fake_policy = SimpleNamespace(id="policy-2", status="active")

    fake_db.first_results[TriggerEvent] = fake_trigger
    fake_db.all_results[(WorkerProfile, Policy)] = [(fake_worker, fake_policy)]
    fake_db.count_results[Claim] = 0

    monkeypatch.setattr(trigger_polling, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))
    monkeypatch.setattr(
        trigger_polling,
        "compute_payout",
        lambda **_: {
            "eligible_for_payout": True,
            "base_loss": 100.0,
            "slab_delta": 72.0,
            "monthly_proximity": 0.0,
            "peak_multiplier_applied": True,
            "total_payout": 172.0,
        },
    )
    monkeypatch.setattr(trigger_polling, "_compute_activity_signal", lambda *_, **__: 1.0)
    monkeypatch.setattr(trigger_polling, "_compute_zone_claim_match", lambda *_, **__: True)
    monkeypatch.setattr(trigger_polling, "compute_fraud_score", lambda **_: 0.2)
    monkeypatch.setattr(trigger_polling, "route_claim", lambda *_: "auto_approve")

    payout_calls = {}

    def fake_initiate_upi_payout(vpa, amount, claim_id):
        payout_calls["vpa"] = vpa
        payout_calls["amount"] = amount
        payout_calls["claim_id"] = claim_id
        return {"success": True, "payout_id": "pout_123", "status": "processing"}

    monkeypatch.setattr(trigger_polling, "initiate_upi_payout", fake_initiate_upi_payout)

    result = trigger_polling.initiate_zone_payouts("trigger-2", 1, cascade_day=1)

    assert result["claims_created"] == 1
    assert payout_calls["vpa"] == "worker@okaxis"
    assert payout_calls["amount"] == 172.0
    assert any(isinstance(obj, Claim) for obj in fake_db.added)


def test_initiate_zone_payouts_hold_route_does_not_call_razorpay(monkeypatch):
    now = datetime.now(timezone.utc)
    fake_db = _FakeDB()

    fake_trigger = SimpleNamespace(id="trigger-3", trigger_type="heavy_rain")
    fake_worker = SimpleNamespace(
        id="worker-3",
        zone_cluster_id=1,
        is_active=True,
        enrollment_date=now - timedelta(days=40),
        upi_vpa="worker@okaxis",
    )
    fake_policy = SimpleNamespace(id="policy-3", status="active")

    fake_db.first_results[TriggerEvent] = fake_trigger
    fake_db.all_results[(WorkerProfile, Policy)] = [(fake_worker, fake_policy)]
    fake_db.count_results[Claim] = 5

    monkeypatch.setattr(trigger_polling, "_get_db_session", lambda: (fake_db, SimpleNamespace(close=lambda: None)))
    monkeypatch.setattr(
        trigger_polling,
        "compute_payout",
        lambda **_: {
            "eligible_for_payout": True,
            "base_loss": 100.0,
            "slab_delta": 50.0,
            "monthly_proximity": 0.0,
            "peak_multiplier_applied": False,
            "total_payout": 150.0,
        },
    )
    monkeypatch.setattr(trigger_polling, "_compute_activity_signal", lambda *_, **__: 0.3)
    monkeypatch.setattr(trigger_polling, "_compute_zone_claim_match", lambda *_, **__: False)
    monkeypatch.setattr(trigger_polling, "compute_fraud_score", lambda **_: 0.8)
    monkeypatch.setattr(trigger_polling, "route_claim", lambda *_: "hold")

    called = {"count": 0}

    def fake_initiate_upi_payout(*args, **kwargs):
        called["count"] += 1
        return {"success": True, "payout_id": "pout_123", "status": "processing"}

    monkeypatch.setattr(trigger_polling, "initiate_upi_payout", fake_initiate_upi_payout)

    result = trigger_polling.initiate_zone_payouts("trigger-3", 1, cascade_day=1)

    assert result["claims_created"] == 1
    assert called["count"] == 0


