from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import payout as payout_api
from app.models.payout import PayoutEvent
from app.models.worker import WorkerProfile


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

    def first(self):
        values = self.db.first_results.get(self.key, [])
        if values:
            return values.pop(0)
        if isinstance(self.key, tuple) and self.key and self.key[0] in self.db.first_results:
            fallback = self.db.first_results[self.key[0]]
            return fallback.pop(0) if fallback else None
        return None

    def all(self):
        if self.key in self.db.all_results:
            return self.db.all_results[self.key]
        if isinstance(self.key, tuple) and self.key and self.key[0] in self.db.all_results:
            return self.db.all_results[self.key[0]]
        return []


class _FakeDB:
    def __init__(self):
        self.first_results: dict[object, list[object]] = {}
        self.all_results: dict[object, list[object]] = {}
        self.added = []
        self.commits = 0

    def query(self, *entities):
        key = entities[0] if len(entities) == 1 else tuple(entities)
        return _FakeQuery(self, key)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


def _client_with_db(fake_db: _FakeDB) -> TestClient:
    app = FastAPI()
    app.include_router(payout_api.router)
    app.dependency_overrides[payout_api.get_db] = lambda: fake_db
    return TestClient(app)


def test_get_worker_payout_history_returns_items():
    fake_db = _FakeDB()
    worker_id = uuid4()

    fake_db.first_results[WorkerProfile] = [SimpleNamespace(id=worker_id)]
    fake_db.all_results[PayoutEvent] = [
        SimpleNamespace(
            id=uuid4(),
            claim_id=uuid4(),
            amount=Decimal("210.00"),
            status="paid",
            razorpay_payout_id="pout_1",
            initiated_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
    ]

    client = _client_with_db(fake_db)
    response = client.get(f"/api/v1/payout/{worker_id}/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["worker_id"] == str(worker_id)
    assert payload["items"][0]["status"] == "paid"


def test_get_worker_payout_history_returns_404_for_unknown_worker():
    fake_db = _FakeDB()
    fake_db.first_results[WorkerProfile] = [None]

    client = _client_with_db(fake_db)
    response = client.get(f"/api/v1/payout/{uuid4()}/history")

    assert response.status_code == 404


def test_webhook_rejects_invalid_signature(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(payout_api.settings, "razorpay_key_secret", "test_secret")

    client = _client_with_db(fake_db)
    payload = {
        "event": "payout.processed",
        "payload": {"payout": {"entity": {"id": "pout_abc"}}},
    }
    raw = json.dumps(payload).encode("utf-8")

    response = client.post(
        "/api/v1/payout/webhook/razorpay",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "bad-signature"},
    )

    assert response.status_code == 401


def test_webhook_accepts_valid_signature_and_updates_paid(monkeypatch):
    fake_db = _FakeDB()
    payout_event = SimpleNamespace(
        id=uuid4(),
        status="processing",
        completed_at=None,
        razorpay_payout_id="pout_ok",
    )
    fake_db.first_results[PayoutEvent] = [payout_event]

    monkeypatch.setattr(payout_api.settings, "razorpay_key_secret", "test_secret")

    payload = {
        "event": "payout.processed",
        "payload": {"payout": {"entity": {"id": "pout_ok"}}},
    }
    raw = json.dumps(payload).encode("utf-8")
    signature = hmac.new(b"test_secret", raw, hashlib.sha256).hexdigest()

    client = _client_with_db(fake_db)
    response = client.post(
        "/api/v1/payout/webhook/razorpay",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["processed"] is True
    assert body["mapped_status"] == "paid"
    assert payout_event.status == "paid"
    assert payout_event.completed_at is not None
    assert fake_db.commits == 1


def test_webhook_returns_404_when_payout_id_not_found(monkeypatch):
    fake_db = _FakeDB()
    fake_db.first_results[PayoutEvent] = [None]
    monkeypatch.setattr(payout_api.settings, "razorpay_key_secret", "test_secret")

    payload = {
        "event": "payout.failed",
        "payload": {"payout": {"entity": {"id": "pout_missing"}}},
    }
    raw = json.dumps(payload).encode("utf-8")
    signature = hmac.new(b"test_secret", raw, hashlib.sha256).hexdigest()

    client = _client_with_db(fake_db)
    response = client.post(
        "/api/v1/payout/webhook/razorpay",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )

    assert response.status_code == 404


def test_webhook_rejects_when_signature_missing(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(payout_api.settings, "razorpay_key_secret", "test_secret")

    payload = {
        "event": "payout.processed",
        "payload": {"payout": {"entity": {"id": "pout_ok"}}},
    }
    raw = json.dumps(payload).encode("utf-8")

    client = _client_with_db(fake_db)
    response = client.post(
        "/api/v1/payout/webhook/razorpay",
        content=raw,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401


def test_webhook_returns_422_when_payload_missing_payout_id(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(payout_api.settings, "razorpay_key_secret", "test_secret")

    payload = {"event": "payout.processed", "payload": {"payout": {"entity": {}}}}
    raw = json.dumps(payload).encode("utf-8")
    signature = hmac.new(b"test_secret", raw, hashlib.sha256).hexdigest()

    client = _client_with_db(fake_db)
    response = client.post(
        "/api/v1/payout/webhook/razorpay",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )

    assert response.status_code == 422


def test_webhook_maps_failed_event_to_failed_status(monkeypatch):
    fake_db = _FakeDB()
    payout_event = SimpleNamespace(
        id=uuid4(),
        status="processing",
        completed_at=None,
        razorpay_payout_id="pout_fail",
    )
    fake_db.first_results[PayoutEvent] = [payout_event]

    monkeypatch.setattr(payout_api.settings, "razorpay_key_secret", "test_secret")

    payload = {
        "event": "payout.failed",
        "payload": {"payout": {"entity": {"id": "pout_fail"}}},
    }
    raw = json.dumps(payload).encode("utf-8")
    signature = hmac.new(b"test_secret", raw, hashlib.sha256).hexdigest()

    client = _client_with_db(fake_db)
    response = client.post(
        "/api/v1/payout/webhook/razorpay",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )

    assert response.status_code == 200
    assert response.json()["mapped_status"] == "failed"
    assert payout_event.status == "failed"
