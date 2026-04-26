from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.api.admin import router
from app.core.database import get_db
from app.models.audit import AuditEvent
from app.models.slab import SlabConfig


class _FakeDB:
    def __init__(self, row: dict = None, rows: list[dict] = None):
        self._row = row
        self._rows = rows or []
        self._slab_configs = []
        self._audit_events = []

    def execute(self, _statement, _params=None):
        if self._rows:
            return _FakeResult(rows=self._rows)
        return _FakeResult(row=self._row)

    def query(self, model):
        if model is SlabConfig:
            return _FakeSlabConfigQuery(self._slab_configs)
        return _FakeQuery([])

    def add(self, obj):
        if isinstance(obj, AuditEvent):
            self._audit_events.append(obj)

    def commit(self):
        pass


class _FakeSlabConfigQuery:
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


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return None if not self._rows else self._rows[0]


class _FakeResult:
    def __init__(self, row: dict = None, rows: list[dict] = None):
        self._row = row
        self._rows = rows or []

    def mappings(self):
        return self

    def one(self):
        return self._row

    def all(self):
        return self._rows


def _build_client(db: _FakeDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_dashboard_summary_without_admin_key_returns_403(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    db = _FakeDB(
        row={
            "active_workers": 0,
            "active_triggers": 0,
            "claims_this_week": 0,
            "payouts_this_week": 0,
            "avg_fraud_score_this_week": None,
        }
    )
    client = _build_client(db)

    response = client.get("/api/v1/admin/dashboard/summary")

    assert response.status_code == 403


def test_dashboard_summary_returns_expected_fields_and_types(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    db = _FakeDB(
        row={
            "active_workers": 11,
            "active_triggers": 2,
            "claims_this_week": 5,
            "payouts_this_week": 1420.5,
            "avg_fraud_score_this_week": 0.318,
        }
    )
    client = _build_client(db)

    response = client.get(
        "/api/v1/admin/dashboard/summary",
        headers={"X-Admin-Key": "secret-admin"},
    )

    assert response.status_code == 200
    body = response.json()

    assert set(body.keys()) == {
        "active_workers",
        "active_triggers",
        "claims_this_week",
        "payouts_this_week",
        "avg_fraud_score_this_week",
        "upi_mandate_coverage_pct",
    }
    assert isinstance(body["active_workers"], int)
    assert isinstance(body["active_triggers"], int)
    assert isinstance(body["claims_this_week"], int)
    assert isinstance(body["payouts_this_week"], float)
    assert isinstance(body["avg_fraud_score_this_week"], float)
    assert isinstance(body["upi_mandate_coverage_pct"], float)


def test_loss_ratio_without_admin_key_returns_403(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    db = _FakeDB(rows=[])
    client = _build_client(db)

    response = client.get("/api/v1/admin/dashboard/loss-ratio")

    assert response.status_code == 403


def test_loss_ratio_returns_expected_fields_and_types(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    db = _FakeDB(
        rows=[
            {
                "zone_cluster_id": 1,
                "month": "2026-04",
                "loss_ratio": 0.45,
                "total_payouts": 5400.0,
                "total_premiums": 12000.0,
            },
            {
                "zone_cluster_id": 2,
                "month": "2026-04",
                "loss_ratio": None,
                "total_payouts": 0.0,
                "total_premiums": 0.0,
            },
        ]
    )
    client = _build_client(db)

    response = client.get(
        "/api/v1/admin/dashboard/loss-ratio",
        headers={"X-Admin-Key": "secret-admin"},
    )

    assert response.status_code == 200
    body = response.json()

    assert len(body) == 2
    assert body[0]["zone_cluster_id"] == 1
    assert body[0]["month"] == "2026-04"
    assert body[0]["loss_ratio"] == 0.45
    assert body[0]["total_payouts"] == 5400.0
    assert body[0]["total_premiums"] == 12000.0

    assert body[1]["zone_cluster_id"] == 2
    assert body[1]["loss_ratio"] is None
    assert body[1]["total_payouts"] == 0.0
    assert body[1]["total_premiums"] == 0.0


def test_claims_forecast_without_admin_key_returns_403(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    db = _FakeDB(rows=[])
    client = _build_client(db)

    response = client.get("/api/v1/admin/dashboard/claims-forecast")

    assert response.status_code == 403


def test_claims_forecast_returns_7_day_array_with_zone_breakdown(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    zone_rows = [
        {
            "zone_cluster_id": 1,
            "centroid_lat": 13.0,
            "centroid_lon": 80.0,
            "active_worker_count": 50,
        },
        {
            "zone_cluster_id": 2,
            "centroid_lat": 13.1,
            "centroid_lon": 80.1,
            "active_worker_count": 30,
        },
    ]

    avg_payout_rows = [
        {"zone_cluster_id": 1, "avg_payout": 400.0},
        {"zone_cluster_id": 2, "avg_payout": 350.0},
    ]

    call_count = [0]
    expected_sqls = 2

    def fake_db_execute(statement, params=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return _FakeResult(rows=zone_rows)
        elif call_count[0] == 2:
            return _FakeResult(rows=avg_payout_rows)

    class _FakeDBWithMultipleExecutes:
        def __init__(self):
            pass

        def execute(self, statement, params=None):
            return fake_db_execute(statement, params)

    db = _FakeDBWithMultipleExecutes()

    def _override_get_db():
        yield db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = _override_get_db

    monkeypatch.setattr(
        "app.api.admin._get_open_meteo_daily_precipitation_probability",
        lambda lat, lon, forecast_date: (65.0 if forecast_date.day < 4 else 45.0),
    )

    client = TestClient(app)

    response = client.get(
        "/api/v1/admin/dashboard/claims-forecast",
        headers={"X-Admin-Key": "secret-admin"},
    )

    assert response.status_code == 200
    body = response.json()

    assert len(body) == 7
    first_day = body[0]
    assert "date" in first_day
    assert "zones" in first_day
    assert len(first_day["zones"]) == 2

    zone1_forecast = first_day["zones"][0]
    assert zone1_forecast["zone_cluster_id"] == 1
    assert isinstance(zone1_forecast["expected_claims"], (int, float))

    zone2_forecast = first_day["zones"][1]
    assert zone2_forecast["zone_cluster_id"] == 2
    assert isinstance(zone2_forecast["expected_claims"], (int, float))


def test_slab_config_verify_without_admin_key_returns_403(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    db = _FakeDB(rows=[])
    client = _build_client(db)

    response = client.get("/api/v1/admin/slab-config/verify")

    assert response.status_code == 403


def test_slab_config_verify_row_verified_today_returns_no_alert(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    now = datetime.now(timezone.utc)
    db = _FakeDB(
        rows=[
            {
                "id": 1,
                "platform": "zomato",
                "deliveries_threshold": 7,
                "bonus_amount": 50.0,
                "last_verified_at": now,
                "is_active": True,
            }
        ]
    )
    client = _build_client(db)

    response = client.get(
        "/api/v1/admin/slab-config/verify",
        headers={"X-Admin-Key": "secret-admin"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["stale_alert"] is False
    assert len(body["slab_rows"]) == 1
    assert body["slab_rows"][0]["platform"] == "zomato"
    assert body["slab_rows"][0]["days_since_verified"] == 0


def test_slab_config_verify_row_verified_31_days_ago_returns_alert(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=31)
    db = _FakeDB(
        rows=[
            {
                "id": 1,
                "platform": "zomato",
                "deliveries_threshold": 7,
                "bonus_amount": 50.0,
                "last_verified_at": old_date,
                "is_active": True,
            }
        ]
    )
    client = _build_client(db)

    response = client.get(
        "/api/v1/admin/slab-config/verify",
        headers={"X-Admin-Key": "secret-admin"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["stale_alert"] is True
    assert len(body["slab_rows"]) == 1
    assert body["slab_rows"][0]["days_since_verified"] == 31


def test_slab_config_verify_row_with_null_verified_at_returns_alert(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    db = _FakeDB(
        rows=[
            {
                "id": 1,
                "platform": "swiggy",
                "deliveries_threshold": 12,
                "bonus_amount": 120.0,
                "last_verified_at": None,
                "is_active": True,
            }
        ]
    )
    client = _build_client(db)

    response = client.get(
        "/api/v1/admin/slab-config/verify",
        headers={"X-Admin-Key": "secret-admin"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["stale_alert"] is True
    assert len(body["slab_rows"]) == 1
    assert body["slab_rows"][0]["last_verified_at"] is None
    assert body["slab_rows"][0]["days_since_verified"] is None


def test_slab_config_update_without_admin_key_returns_403(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    db = _FakeDB()
    client = _build_client(db)

    response = client.put(
        "/api/v1/admin/slab-config/update",
        json={"platform": "zomato", "deliveries_threshold": 7, "bonus_amount": 55.0},
    )

    assert response.status_code == 403


def test_slab_config_update_unknown_row_returns_404(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    db = _FakeDB()
    db._slab_configs = []
    client = _build_client(db)

    response = client.put(
        "/api/v1/admin/slab-config/update",
        json={"platform": "zomato", "deliveries_threshold": 999, "bonus_amount": 55.0},
        headers={"X-Admin-Key": "secret-admin"},
    )

    assert response.status_code == 404


def test_slab_config_update_resets_verified_at_and_audits(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    old_verified = datetime.now(timezone.utc) - timedelta(days=10)

    fake_slab = SimpleNamespace(
        id=1,
        platform="zomato",
        deliveries_threshold=7,
        bonus_amount=50.0,
        last_verified_at=old_verified,
        is_active=True,
    )

    db = _FakeDB()
    db._slab_configs = [fake_slab]
    client = _build_client(db)

    response = client.put(
        "/api/v1/admin/slab-config/update",
        json={"platform": "zomato", "deliveries_threshold": 7, "bonus_amount": 75.0},
        headers={"X-Admin-Key": "secret-admin"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["bonus_amount"] == 75.0
    assert body["platform"] == "zomato"
    assert body["deliveries_threshold"] == 7
    assert body["id"] == 1

    assert len(db._audit_events) == 1
    audit = db._audit_events[0]
    assert audit.event_type == "slab_config_updated"
    assert audit.payload["old_bonus_amount"] == 50.0
    assert audit.payload["new_bonus_amount"] == 75.0

    assert fake_slab.bonus_amount == 75.0
    assert fake_slab.last_verified_at > old_verified


def test_model_health_without_admin_key_returns_403(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    db = _FakeDB()
    client = _build_client(db)

    response = client.get("/api/v1/admin/model-health")

    assert response.status_code == 403


def test_model_health_returns_expected_fields_and_types(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=5)

    rmse_row = {
        "claim_count": 100,
        "mean_squared_error": 400.0,
    }
    fraud_row = {
        "total_resolved_held": 30,
        "confirmed_fraud_count": 6,
    }
    slab_row = {
        "stale_count": 0,
        "oldest_verified_at": old_date,
    }

    class _FakeDBMultiQuery(_FakeDB):
        def __init__(self):
            super().__init__()
            self._call_order = 0

        def execute(self, _statement, _params=None):
            self._call_order += 1
            if self._call_order == 1:
                return _FakeResult(row=rmse_row)
            elif self._call_order == 2:
                return _FakeResult(row=fraud_row)
            elif self._call_order == 3:
                return _FakeResult(row=slab_row)
            elif self._call_order == 4:
                return _FakeResult(rows=[{"has_drift": False}])
            return _FakeResult(row={})

    db = _FakeDBMultiQuery()

    def _override_get_db():
        yield db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = _override_get_db

    client = TestClient(app)

    response = client.get(
        "/api/v1/admin/model-health",
        headers={"X-Admin-Key": "secret-admin"},
    )

    assert response.status_code == 200
    body = response.json()

    assert "premium_model_rmse" in body
    assert "fraud_precision" in body
    assert "slab_config_stale" in body
    assert "oldest_slab_verified_days" in body
    assert "baseline_drift_alert" in body

    assert isinstance(body["premium_model_rmse"], float)
    assert body["premium_model_rmse"] == 20.0
    assert isinstance(body["fraud_precision"], float)
    assert body["fraud_precision"] == 0.2
    assert isinstance(body["slab_config_stale"], bool)
    assert body["slab_config_stale"] is False
    assert isinstance(body["oldest_slab_verified_days"], int)
    assert body["oldest_slab_verified_days"] == 5
    assert isinstance(body["baseline_drift_alert"], bool)


def test_model_health_premium_model_rmse_null_if_fewer_than_50_claims(monkeypatch):
    monkeypatch.setattr("app.api.admin.settings.admin_key", "secret-admin")

    rmse_row = {
        "claim_count": 30,
        "mean_squared_error": 400.0,
    }
    fraud_row = {
        "total_resolved_held": 5,
        "confirmed_fraud_count": 1,
    }
    slab_row = {
        "stale_count": 0,
        "oldest_verified_at": None,
    }

    class _FakeDBMultiQuery(_FakeDB):
        def __init__(self):
            super().__init__()
            self._call_order = 0

        def execute(self, _statement, _params=None):
            self._call_order += 1
            if self._call_order == 1:
                return _FakeResult(row=rmse_row)
            elif self._call_order == 2:
                return _FakeResult(row=fraud_row)
            elif self._call_order == 3:
                return _FakeResult(row=slab_row)
            elif self._call_order == 4:
                return _FakeResult(rows=[{"has_drift": None}])
            return _FakeResult(row={})

    db = _FakeDBMultiQuery()

    def _override_get_db():
        yield db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = _override_get_db

    client = TestClient(app)

    response = client.get(
        "/api/v1/admin/model-health",
        headers={"X-Admin-Key": "secret-admin"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["premium_model_rmse"] is None
    assert body["fraud_precision"] is None
