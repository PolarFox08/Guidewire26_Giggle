from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient  # type: ignore[reportMissingImports]

sys.path.append(str(Path(__file__).resolve().parents[2]))

import main as main_module


PERSON1_OPENAPI_PATHS = {
    "/api/v1/onboarding/kyc/aadhaar",
    "/api/v1/policy/{worker_id}",
    "/api/v1/fraud/score",
    "/api/v1/admin/",
}


def _build_client() -> TestClient:
    return TestClient(main_module.app)


def test_health_endpoint_returns_200_and_all_fields(monkeypatch):
    monkeypatch.setattr(main_module, "_check_database", lambda: "ok")
    monkeypatch.setattr(main_module, "_check_redis", lambda: "ok")
    monkeypatch.setattr(main_module, "_check_fraud_models", lambda: "loaded")

    client = _build_client()
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"status", "database", "redis", "fraud_models", "version"}
    assert body["status"] == "healthy"
    assert body["database"] == "ok"
    assert body["redis"] == "ok"
    assert body["fraud_models"] == "loaded"
    assert body["version"] == "0.2.0"


def test_health_endpoint_returns_200_when_degraded(monkeypatch):
    monkeypatch.setattr(main_module, "_check_database", lambda: "error")
    monkeypatch.setattr(main_module, "_check_redis", lambda: "ok")
    monkeypatch.setattr(main_module, "_check_fraud_models", lambda: "missing")

    client = _build_client()
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"
    assert body["redis"] == "ok"
    assert body["fraud_models"] == "missing"


def test_docs_endpoint_is_reachable():
    client = _build_client()

    response = client.get("/docs")

    assert response.status_code == 200


def test_person1_routers_appear_in_openapi_schema():
    client = _build_client()

    schema = client.get("/openapi.json").json()
    paths = set(schema["paths"].keys())

    for path in PERSON1_OPENAPI_PATHS:
        assert path in paths
