from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.api.fraud import router
from app.core.database import get_db
from app.models.claims import Claim
from app.models.delivery import DeliveryHistory
from app.models.worker import WorkerProfile
from app.models.zone import ZoneCluster


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters = {}

    def filter_by(self, **kwargs):
        self._filters.update(kwargs)
        return self

    def first(self):
        for row in self.all():
            return row
        return None

    def all(self):
        filtered = []
        for row in self._rows:
            if all(getattr(row, key, None) == value for key, value in self._filters.items()):
                filtered.append(row)
        return filtered


class _FakeDB:
    def __init__(self, workers, deliveries, zones, claims=None):
        self._workers = workers
        self._deliveries = deliveries
        self._zones = zones
        self._claims = claims or []

    def query(self, model):
        if model is WorkerProfile:
            return _FakeQuery(self._workers)
        if model is DeliveryHistory:
            return _FakeQuery(self._deliveries)
        if model is ZoneCluster:
            return _FakeQuery(self._zones)
        if model is Claim:
            return _FakeQuery(self._claims)
        return _FakeQuery([])


def _build_client(db: _FakeDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_post_fraud_score_gps_spoofer_profile_returns_high_score(monkeypatch):
    worker_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)

    worker = SimpleNamespace(
        id=worker_id,
        flood_hazard_tier="low",
        zone_cluster_id=1,
        enrollment_week=2,
    )
    deliveries = [
        SimpleNamespace(worker_id=worker_id, deliveries_count=5, recorded_at=now_utc - timedelta(days=1)),
        SimpleNamespace(worker_id=worker_id, deliveries_count=7, recorded_at=now_utc - timedelta(days=3)),
    ]
    zone = SimpleNamespace(id=1)

    db = _FakeDB(workers=[worker], deliveries=deliveries, zones=[zone])
    client = _build_client(db)

    monkeypatch.setattr(
        "app.api.fraud.compute_fraud_score",
        lambda zone_claim_match, activity_7d_score, claim_to_enrollment_days, event_claim_frequency: 0.81,
    )

    response = client.post(
        "/api/v1/fraud/score",
        json={
            "worker_id": str(worker_id),
            "zone_claim_match": 0,
            "claim_to_enrollment_days": 10,
            "event_claim_frequency": 8,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fraud_score"] > 0.5
    assert body["routing"] == "hold"


def test_post_fraud_score_clean_profile_returns_auto_approve(monkeypatch):
    worker_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)

    worker = SimpleNamespace(
        id=worker_id,
        flood_hazard_tier="high",
        zone_cluster_id=2,
        enrollment_week=20,
    )
    deliveries = [
        SimpleNamespace(worker_id=worker_id, deliveries_count=12, recorded_at=now_utc - timedelta(days=1)),
        SimpleNamespace(worker_id=worker_id, deliveries_count=10, recorded_at=now_utc - timedelta(days=2)),
        SimpleNamespace(worker_id=worker_id, deliveries_count=8, recorded_at=now_utc - timedelta(days=8)),
    ]
    zone = SimpleNamespace(id=2)

    db = _FakeDB(workers=[worker], deliveries=deliveries, zones=[zone])
    client = _build_client(db)

    monkeypatch.setattr(
        "app.api.fraud.compute_fraud_score",
        lambda zone_claim_match, activity_7d_score, claim_to_enrollment_days, event_claim_frequency: 0.12,
    )

    response = client.post(
        "/api/v1/fraud/score",
        json={
            "worker_id": str(worker_id),
            "zone_claim_match": 1,
            "claim_to_enrollment_days": 180,
            "event_claim_frequency": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fraud_score"] < 0.3
    assert body["routing"] == "auto_approve"


def test_get_fraud_queue_without_admin_key_returns_403(monkeypatch):
    monkeypatch.setattr("app.api.fraud.settings.admin_key", "secret-admin")

    db = _FakeDB(workers=[], deliveries=[], zones=[], claims=[])
    client = _build_client(db)

    response = client.get("/api/v1/fraud/queue")

    assert response.status_code == 403


def test_get_fraud_queue_with_admin_key_returns_only_held_or_partial(monkeypatch):
    monkeypatch.setattr("app.api.fraud.settings.admin_key", "secret-admin")

    now_utc = datetime.now(timezone.utc)
    claim_held = SimpleNamespace(
        worker_id=uuid.uuid4(),
        claim_date=now_utc,
        fraud_score=0.82,
        fraud_routing="hold",
        zone_claim_match=False,
        activity_7d_score=0.4,
        status="held",
    )
    claim_partial = SimpleNamespace(
        worker_id=uuid.uuid4(),
        claim_date=now_utc - timedelta(hours=1),
        fraud_score=0.45,
        fraud_routing="partial_review",
        zone_claim_match=True,
        activity_7d_score=0.95,
        status="pending",
    )
    claim_approved = SimpleNamespace(
        worker_id=uuid.uuid4(),
        claim_date=now_utc - timedelta(hours=2),
        fraud_score=0.12,
        fraud_routing="auto_approve",
        zone_claim_match=True,
        activity_7d_score=1.05,
        status="approved",
    )

    db = _FakeDB(
        workers=[],
        deliveries=[],
        zones=[],
        claims=[claim_approved, claim_partial, claim_held],
    )
    client = _build_client(db)

    response = client.get(
        "/api/v1/fraud/queue",
        headers={"X-Admin-Key": "secret-admin"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["status"] == "held"
    assert body[1]["fraud_routing"] == "partial_review"


def test_get_worker_signals_unknown_worker_returns_404(monkeypatch):
    monkeypatch.setattr("app.api.fraud.detect_ring_registrations", lambda db: [])

    db = _FakeDB(workers=[], deliveries=[], zones=[], claims=[])
    client = _build_client(db)

    response = client.get(f"/api/v1/fraud/worker/{uuid.uuid4()}/signals")

    assert response.status_code == 404


def test_get_worker_signals_sets_ring_registration_flag_true_when_worker_in_ring(monkeypatch):
    worker_id = uuid.uuid4()
    other_worker_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)

    worker = SimpleNamespace(
        id=worker_id,
        enrollment_week=3,
    )
    claim_new = SimpleNamespace(
        worker_id=worker_id,
        claim_date=now_utc,
        fraud_score=0.6,
        zone_claim_match=True,
    )
    claim_old = SimpleNamespace(
        worker_id=worker_id,
        claim_date=now_utc - timedelta(hours=2),
        fraud_score=0.2,
        zone_claim_match=False,
    )
    unrelated_claim = SimpleNamespace(
        worker_id=other_worker_id,
        claim_date=now_utc - timedelta(hours=1),
        fraud_score=0.9,
        zone_claim_match=False,
    )

    monkeypatch.setattr(
        "app.api.fraud.detect_ring_registrations",
        lambda db: [[str(worker_id), str(other_worker_id)]],
    )

    db = _FakeDB(
        workers=[worker],
        deliveries=[],
        zones=[],
        claims=[claim_old, unrelated_claim, claim_new],
    )
    client = _build_client(db)

    response = client.get(f"/api/v1/fraud/worker/{worker_id}/signals")

    assert response.status_code == 200
    body = response.json()
    assert body["total_claim_count"] == 2
    assert body["ring_registration_flag"] is True
    assert body["zone_claim_match_history"] == [True, False]
