from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import trigger as trigger_api
from app.models.trigger import TriggerEvent
from app.models.zone import ZoneCluster


class _FakeQuery:
    def __init__(self, db: _FakeDB, key):
        self.db = db
        self.key = key

    def filter(self, *args, **kwargs):
        _ = args
        _ = kwargs
        return self

    def order_by(self, *args, **kwargs):
        _ = args
        _ = kwargs
        return self

    def join(self, *args, **kwargs):
        _ = args
        _ = kwargs
        return self

    def outerjoin(self, *args, **kwargs):
        _ = args
        _ = kwargs
        return self

    def group_by(self, *args, **kwargs):
        _ = args
        _ = kwargs
        return self

    def limit(self, *args, **kwargs):
        _ = args
        _ = kwargs
        return self

    def first(self):
        if self.key in self.db.first_results:
            return self.db.first_results[self.key]
        if isinstance(self.key, tuple) and self.key and self.key[0] in self.db.first_results:
            return self.db.first_results[self.key[0]]
        return None

    def all(self):
        if self.key in self.db.all_results:
            return self.db.all_results[self.key]
        if isinstance(self.key, tuple) and self.key and self.key[0] in self.db.all_results:
            return self.db.all_results[self.key[0]]
        if isinstance(self.key, tuple) and self.key and self.key[0] is TriggerEvent:
            return self.db.all_results.get("trigger_history", [])
        return []


class _FakeDB:
    def __init__(self):
        self.first_results = {}
        self.all_results = {}
        self.added = []
        self.flush_called = 0
        self.commit_called = 0

    def query(self, *entities):
        key = entities[0] if len(entities) == 1 else tuple(entities)
        return _FakeQuery(self, key)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            setattr(obj, "id", uuid4())
        self.added.append(obj)

    def flush(self):
        self.flush_called += 1

    def commit(self):
        self.commit_called += 1


def _client_with_db(fake_db: _FakeDB) -> TestClient:
    app = FastAPI()
    app.include_router(trigger_api.router)
    app.dependency_overrides[trigger_api.get_db] = lambda: fake_db
    return TestClient(app)


def test_get_zone_state_returns_none_when_no_trigger():
    fake_db = _FakeDB()
    fake_db.first_results[ZoneCluster] = SimpleNamespace(id=1)
    fake_db.first_results[TriggerEvent] = None

    client = _client_with_db(fake_db)
    response = client.get("/api/v1/trigger/zone/1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "none"
    assert payload["sources_confirmed"] == 0


def test_get_zone_state_returns_404_for_unknown_zone():
    fake_db = _FakeDB()
    fake_db.first_results[ZoneCluster] = None

    client = _client_with_db(fake_db)
    response = client.get("/api/v1/trigger/zone/999")

    assert response.status_code == 404


def test_post_simulate_creates_event_sets_suspension_and_enqueues_task(monkeypatch):
    fake_db = _FakeDB()
    fake_db.first_results[ZoneCluster] = SimpleNamespace(id=3)
    fake_db.first_results[TriggerEvent] = None

    suspended: dict[str, int | None] = {"zone": None}
    delayed: dict[str, tuple[object, ...] | None] = {"args": None}

    monkeypatch.setattr(trigger_api, "set_zone_suspended", lambda zone_id: suspended.__setitem__("zone", zone_id))
    monkeypatch.setattr(
        trigger_api.initiate_zone_payouts,
        "delay",
        lambda *args: delayed.__setitem__("args", args),
    )

    client = _client_with_db(fake_db)
    response = client.post(
        "/api/v1/trigger/simulate",
        json={"zone_cluster_id": 3, "trigger_type": "heavy_rain", "duration_hours": 2.0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["zone_cluster_id"] == 3
    assert payload["payout_task_enqueued"] is True
    assert suspended["zone"] == 3
    assert delayed["args"] is not None
    assert delayed["args"][1] == 3
    assert fake_db.flush_called == 1
    assert fake_db.commit_called == 1


def test_post_simulate_returns_409_when_active_trigger_exists():
    fake_db = _FakeDB()
    fake_db.first_results[ZoneCluster] = SimpleNamespace(id=1)
    fake_db.first_results[TriggerEvent] = SimpleNamespace(id=uuid4(), status="active")

    client = _client_with_db(fake_db)
    response = client.post(
        "/api/v1/trigger/simulate",
        json={"zone_cluster_id": 1, "trigger_type": "heavy_rain", "duration_hours": 1.0},
    )

    assert response.status_code == 409


def test_post_simulate_rejects_invalid_trigger_type():
    fake_db = _FakeDB()
    fake_db.first_results[ZoneCluster] = SimpleNamespace(id=1)
    fake_db.first_results[TriggerEvent] = None

    client = _client_with_db(fake_db)
    response = client.post(
        "/api/v1/trigger/simulate",
        json={"zone_cluster_id": 1, "trigger_type": "invalid_type", "duration_hours": 1.0},
    )

    assert response.status_code == 422


def test_post_simulate_returns_404_for_unknown_zone():
    fake_db = _FakeDB()
    fake_db.first_results[ZoneCluster] = None

    client = _client_with_db(fake_db)
    response = client.post(
        "/api/v1/trigger/simulate",
        json={"zone_cluster_id": 1, "trigger_type": "heavy_rain", "duration_hours": 1.0},
    )

    assert response.status_code == 404


def test_get_active_returns_cascade_day_and_zone_info():
    fake_db = _FakeDB()
    triggered_at = datetime.now(timezone.utc) - timedelta(days=1, hours=2)

    fake_db.all_results[(TriggerEvent, ZoneCluster)] = [
        (
            SimpleNamespace(
                id=uuid4(),
                zone_cluster_id=7,
                status="active",
                trigger_type="heavy_rain",
                composite_score=0.75,
                corroboration_sources=2,
                triggered_at=triggered_at,
            ),
            SimpleNamespace(centroid_lat=13.01, centroid_lon=80.22),
        )
    ]

    client = _client_with_db(fake_db)
    response = client.get("/api/v1/trigger/active")

    assert response.status_code == 200
    payload = response.json()["items"]
    assert len(payload) == 1
    assert payload[0]["zone_cluster_id"] == 7
    assert payload[0]["current_cascade_day"] >= 2


def test_get_zone_state_normalizes_closed_to_none():
    fake_db = _FakeDB()
    fake_db.first_results[ZoneCluster] = SimpleNamespace(id=2)
    fake_db.first_results[TriggerEvent] = SimpleNamespace(
        id=uuid4(),
        status="closed",
        trigger_type="heavy_rain",
        composite_score=0.5,
        triggered_at=datetime.now(timezone.utc),
        corroboration_sources=2,
    )

    client = _client_with_db(fake_db)
    response = client.get("/api/v1/trigger/zone/2")

    assert response.status_code == 200
    assert response.json()["status"] == "none"


def test_get_history_returns_last_events_with_payout_count():
    fake_db = _FakeDB()
    trigger_id = uuid4()
    fake_db.all_results["trigger_history"] = [
        (
            SimpleNamespace(
                id=trigger_id,
                zone_cluster_id=4,
                trigger_type="severe_aqi",
                status="closed",
                triggered_at=datetime.now(timezone.utc),
                composite_score=0.55,
                corroboration_sources=2,
            ),
            3,
        )
    ]

    client = _client_with_db(fake_db)
    response = client.get("/api/v1/trigger/history")

    assert response.status_code == 200
    payload = response.json()["items"]
    assert len(payload) == 1
    assert payload[0]["payout_count"] == 3
    assert payload[0]["zone_cluster_id"] == 4
