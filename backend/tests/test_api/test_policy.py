import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.api.policy import router
from app.core.config import settings
from app.core.database import get_db
from app.models.audit import AuditEvent
from app.models.policy import Policy
from app.models.worker import WorkerProfile


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters = {}

    def filter_by(self, **kwargs):
        self._filters.update(kwargs)
        return self

    def first(self):
        for row in self._rows:
            if all(getattr(row, key, None) == value for key, value in self._filters.items()):
                return row
        return None


class _FakeDB:
    def __init__(self, workers=None, policies=None):
        self.workers = workers or []
        self.policies = policies or []
        self.audit_events = []

    def query(self, model):
        if model is WorkerProfile:
            return _FakeQuery(self.workers)
        if model is Policy:
            return _FakeQuery(self.policies)
        if model is AuditEvent:
            return _FakeQuery(self.audit_events)
        return _FakeQuery([])

    def add(self, obj):
        if isinstance(obj, AuditEvent):
            self.audit_events.append(obj)

    def commit(self):
        return None


def _build_client(db: _FakeDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_get_policy_unknown_worker_returns_404():
    db = _FakeDB()
    client = _build_client(db)

    response = client.get(f"/api/v1/policy/{uuid.uuid4()}")

    assert response.status_code == 404


def test_get_policy_enrolled_today_returns_28_days_until_eligible():
    worker_id = uuid.uuid4()
    policy_id = uuid.uuid4()

    worker = SimpleNamespace(
        id=worker_id,
        enrollment_date=datetime.now(timezone.utc),
        enrollment_week=1,
    )
    policy = SimpleNamespace(
        id=policy_id,
        worker_id=worker_id,
        status="waiting",
        weekly_premium_amount=75.0,
        coverage_start_date=None,
        coverage_week_number=1,
        model_used="glm",
        shap_explanation_json=[],
    )

    db = _FakeDB(workers=[worker], policies=[policy])
    client = _build_client(db)

    response = client.get(f"/api/v1/policy/{worker_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["policy_id"] == str(policy_id)
    assert body["days_until_claim_eligible"] == 28
    assert body["enrollment_week"] == 1


def test_get_policy_enrolled_28_days_ago_returns_0_days_until_eligible():
    worker_id = uuid.uuid4()
    policy_id = uuid.uuid4()

    worker = SimpleNamespace(
        id=worker_id,
        enrollment_date=datetime.now(timezone.utc) - timedelta(days=28),
        enrollment_week=5,
    )
    policy = SimpleNamespace(
        id=policy_id,
        worker_id=worker_id,
        status="active",
        weekly_premium_amount=82.0,
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=1),
        coverage_week_number=5,
        model_used="lgbm",
        shap_explanation_json=["x", "y", "z"],
    )

    db = _FakeDB(workers=[worker], policies=[policy])
    client = _build_client(db)

    response = client.get(f"/api/v1/policy/{worker_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["days_until_claim_eligible"] == 0


def test_get_policy_coverage_unknown_worker_returns_404():
    db = _FakeDB()
    client = _build_client(db)

    response = client.get(f"/api/v1/policy/{uuid.uuid4()}/coverage")

    assert response.status_code == 404


def test_get_policy_coverage_active_worker_after_28_days_returns_true():
    worker_id = uuid.uuid4()
    policy_id = uuid.uuid4()

    worker = SimpleNamespace(
        id=worker_id,
        enrollment_date=datetime.now(timezone.utc) - timedelta(days=28),
        enrollment_week=5,
        language_preference="en",
    )
    policy = SimpleNamespace(
        id=policy_id,
        worker_id=worker_id,
        status="active",
        weekly_premium_amount=90.0,
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=1),
        coverage_week_number=6,
        next_renewal_at=datetime.now(timezone.utc) + timedelta(days=2),
        model_used="lgbm",
        shap_explanation_json=[
            {"feature": "rain_forecast", "direction": "positive"},
            {"feature": "flood_tier", "direction": "positive"},
            {"feature": "tenure_discount", "direction": "negative"},
        ],
    )

    db = _FakeDB(workers=[worker], policies=[policy])
    client = _build_client(db)

    response = client.get(f"/api/v1/policy/{worker_id}/coverage")

    assert response.status_code == 200
    body = response.json()
    assert body["is_coverage_active"] is True
    assert body["current_week_number"] == 6
    assert body["weekly_premium_amount"] == 90.0
    assert len(body["shap_top3"]) == 3
    assert body["shap_top3"][0] == "rain_forecast: positive impact"


def test_get_policy_coverage_waiting_period_worker_returns_false():
    worker_id = uuid.uuid4()
    policy_id = uuid.uuid4()

    worker = SimpleNamespace(
        id=worker_id,
        enrollment_date=datetime.now(timezone.utc) - timedelta(days=10),
        enrollment_week=2,
        language_preference="ta",
    )
    policy = SimpleNamespace(
        id=policy_id,
        worker_id=worker_id,
        status="active",
        weekly_premium_amount=80.0,
        coverage_start_date=None,
        coverage_week_number=2,
        next_renewal_at=datetime.now(timezone.utc) + timedelta(days=3),
        model_used="glm",
        shap_explanation_json=[
            {"feature": "open_meteo_7d_precip_probability", "direction": "positive"},
            {"feature": "zone", "direction": "positive"},
            {"feature": "tenure", "direction": "negative"},
        ],
    )

    db = _FakeDB(workers=[worker], policies=[policy])
    client = _build_client(db)

    response = client.get(f"/api/v1/policy/{worker_id}/coverage")

    assert response.status_code == 200
    body = response.json()
    assert body["is_coverage_active"] is False
    assert len(body["shap_top3"]) == 3
    assert body["shap_top3"][0] == "open_meteo_7d_precip_probability: positive பாதிக்கிறது"


def test_get_policy_coverage_suspended_worker_returns_false():
    worker_id = uuid.uuid4()
    policy_id = uuid.uuid4()

    worker = SimpleNamespace(
        id=worker_id,
        enrollment_date=datetime.now(timezone.utc) - timedelta(days=35),
        enrollment_week=6,
        language_preference="en",
    )
    policy = SimpleNamespace(
        id=policy_id,
        worker_id=worker_id,
        status="suspended",
        weekly_premium_amount=88.0,
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=7),
        coverage_week_number=7,
        next_renewal_at=datetime.now(timezone.utc) + timedelta(days=1),
        model_used="lgbm",
        shap_explanation_json=[],
    )

    db = _FakeDB(workers=[worker], policies=[policy])
    client = _build_client(db)

    response = client.get(f"/api/v1/policy/{worker_id}/coverage")

    assert response.status_code == 200
    body = response.json()
    assert body["is_coverage_active"] is False


def test_suspend_unknown_worker_returns_404_with_valid_admin_key(monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "secret-admin-key", raising=False)

    db = _FakeDB()
    client = _build_client(db)

    response = client.put(
        f"/api/v1/policy/{uuid.uuid4()}/suspend",
        headers={"X-Admin-Key": "secret-admin-key"},
    )

    assert response.status_code == 404


def test_suspend_without_admin_key_returns_403(monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "secret-admin-key", raising=False)

    worker_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    worker = SimpleNamespace(
        id=worker_id,
        enrollment_date=datetime.now(timezone.utc) - timedelta(days=5),
        enrollment_week=1,
        language_preference="en",
    )
    policy = SimpleNamespace(
        id=policy_id,
        worker_id=worker_id,
        status="active",
        weekly_premium_amount=75.0,
        coverage_start_date=None,
        coverage_week_number=1,
        model_used="glm",
        shap_explanation_json=[],
    )

    db = _FakeDB(workers=[worker], policies=[policy])
    client = _build_client(db)

    response = client.put(f"/api/v1/policy/{worker_id}/suspend")

    assert response.status_code == 403


def test_suspend_with_wrong_admin_key_returns_403(monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "secret-admin-key", raising=False)

    worker_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    worker = SimpleNamespace(
        id=worker_id,
        enrollment_date=datetime.now(timezone.utc) - timedelta(days=5),
        enrollment_week=1,
        language_preference="en",
    )
    policy = SimpleNamespace(
        id=policy_id,
        worker_id=worker_id,
        status="active",
        weekly_premium_amount=75.0,
        coverage_start_date=None,
        coverage_week_number=1,
        model_used="glm",
        shap_explanation_json=[],
    )

    db = _FakeDB(workers=[worker], policies=[policy])
    client = _build_client(db)

    response = client.put(
        f"/api/v1/policy/{worker_id}/suspend",
        headers={"X-Admin-Key": "wrong-key"},
    )

    assert response.status_code == 403


def test_suspend_with_correct_admin_key_suspends_and_writes_audit_event(monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "secret-admin-key", raising=False)

    worker_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    worker = SimpleNamespace(
        id=worker_id,
        enrollment_date=datetime.now(timezone.utc) - timedelta(days=30),
        enrollment_week=5,
        language_preference="en",
    )
    policy = SimpleNamespace(
        id=policy_id,
        worker_id=worker_id,
        status="active",
        weekly_premium_amount=99.0,
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=2),
        coverage_week_number=5,
        model_used="lgbm",
        shap_explanation_json=[],
    )

    db = _FakeDB(workers=[worker], policies=[policy])
    client = _build_client(db)

    response = client.put(
        f"/api/v1/policy/{worker_id}/suspend",
        headers={"X-Admin-Key": "secret-admin-key"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "suspended"
    assert len(db.audit_events) == 1
    assert db.audit_events[0].event_type == "policy_suspended"
    assert db.audit_events[0].payload["reason"] == "admin_action"
    assert db.audit_events[0].payload["worker_id"] == str(worker_id)
