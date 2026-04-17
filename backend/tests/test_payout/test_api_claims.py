from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import claims as claims_api
from app.models.claims import Claim
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

    def scalar(self):
        values = self.db.scalar_results.get(self.key, [])
        if values:
            return values.pop(0)
        if self.db.scalar_default:
            return self.db.scalar_default.pop(0)
        return 0


class _FakeDB:
    def __init__(self):
        self.first_results: dict[object, list[object]] = {}
        self.all_results: dict[object, list[object]] = {}
        self.scalar_results: dict[object, list[object]] = {}
        self.scalar_default: list[object] = []
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
    app.include_router(claims_api.router)
    app.dependency_overrides[claims_api.get_db] = lambda: fake_db
    return TestClient(app)


def test_get_pending_claims_returns_partial_and_held_sorted():
    fake_db = _FakeDB()
    c1 = SimpleNamespace(
        id=uuid4(),
        worker_id=uuid4(),
        claim_date=datetime.now(timezone.utc),
        fraud_score=Decimal("0.650"),
        fraud_routing="partial_review",
        status="partial",
        zone_claim_match=True,
        activity_7d_score=Decimal("1.000"),
    )
    c2 = SimpleNamespace(
        id=uuid4(),
        worker_id=uuid4(),
        claim_date=datetime.now(timezone.utc),
        fraud_score=Decimal("0.800"),
        fraud_routing="hold",
        status="held",
        zone_claim_match=False,
        activity_7d_score=Decimal("0.300"),
    )
    fake_db.all_results[Claim] = [c2, c1]

    client = _client_with_db(fake_db)
    response = client.get("/api/v1/claims/pending")

    assert response.status_code == 200
    payload = response.json()["items"]
    assert len(payload) == 2
    assert payload[0]["fraud_score"] >= payload[1]["fraud_score"]


def test_get_claim_detail_returns_breakdown_fields():
    fake_db = _FakeDB()
    claim_id = uuid4()
    fake_db.first_results[Claim] = [
        SimpleNamespace(
            id=claim_id,
            worker_id=uuid4(),
            trigger_event_id=uuid4(),
            policy_id=uuid4(),
            claim_date=datetime.now(timezone.utc),
            cascade_day=2,
            deliveries_completed=10,
            base_loss_amount=Decimal("100.00"),
            slab_delta_amount=Decimal("72.00"),
            monthly_proximity_amount=Decimal("0.00"),
            peak_multiplier_applied=True,
            total_payout_amount=Decimal("206.40"),
            fraud_score=Decimal("0.350"),
            fraud_routing="partial_review",
            status="partial",
            zone_claim_match=True,
            activity_7d_score=Decimal("0.850"),
        )
    ]

    client = _client_with_db(fake_db)
    response = client.get(f"/api/v1/claims/detail/{claim_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["base_loss_amount"] == 100.0
    assert payload["slab_delta_amount"] == 72.0
    assert payload["fraud_routing"] == "partial_review"


def test_get_worker_claim_history_returns_paid_amounts():
    fake_db = _FakeDB()
    worker_id = uuid4()
    claim_id = uuid4()

    fake_db.first_results[WorkerProfile] = [SimpleNamespace(id=worker_id)]
    fake_db.all_results[Claim] = [
        SimpleNamespace(
            id=claim_id,
            claim_date=datetime.now(timezone.utc),
            total_payout_amount=Decimal("300.00"),
            fraud_score=Decimal("0.200"),
            fraud_routing="auto_approve",
            status="approved",
        )
    ]
    fake_db.scalar_default = [Decimal("300.00")]

    client = _client_with_db(fake_db)
    response = client.get(f"/api/v1/claims/{worker_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["worker_id"] == str(worker_id)
    assert payload["items"][0]["total_paid_amount"] == 300.0


def test_put_resolve_approve_pays_remaining_and_writes_event(monkeypatch):
    fake_db = _FakeDB()
    claim_id = uuid4()
    worker_id = uuid4()

    fake_db.first_results[Claim] = [
        SimpleNamespace(
            id=claim_id,
            worker_id=worker_id,
            total_payout_amount=Decimal("500.00"),
            status="held",
        )
    ]
    fake_db.first_results[WorkerProfile] = [SimpleNamespace(id=worker_id, upi_vpa="worker@okaxis")]

    fake_db.scalar_default = [Decimal("200.00")]

    payout_call = {}

    def _fake_payout(vpa, amount, claim_ref):
        payout_call["vpa"] = vpa
        payout_call["amount"] = amount
        payout_call["claim_ref"] = claim_ref
        return {"success": True, "payout_id": "pout_123", "status": "processing"}

    monkeypatch.setattr(claims_api, "initiate_upi_payout", _fake_payout)

    client = _client_with_db(fake_db)
    response = client.put(f"/api/v1/claims/{claim_id}/resolve", json={"resolution": "approve"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["remaining_payout_attempted"] == 300.0
    assert payload["payout_triggered"] is True
    assert payout_call["vpa"] == "worker@okaxis"
    assert payout_call["amount"] == 300.0
    assert fake_db.commits == 1


def test_put_resolve_reject_updates_status_without_payout(monkeypatch):
    fake_db = _FakeDB()
    claim_id = uuid4()
    worker_id = uuid4()

    fake_db.first_results[Claim] = [
        SimpleNamespace(
            id=claim_id,
            worker_id=worker_id,
            total_payout_amount=Decimal("500.00"),
            status="held",
        )
    ]
    fake_db.first_results[WorkerProfile] = [SimpleNamespace(id=worker_id, upi_vpa="worker@okaxis")]

    fake_db.scalar_default = [Decimal("250.00")]

    called = {"count": 0}
    monkeypatch.setattr(claims_api, "initiate_upi_payout", lambda *args: called.__setitem__("count", called["count"] + 1))

    client = _client_with_db(fake_db)
    response = client.put(f"/api/v1/claims/{claim_id}/resolve", json={"resolution": "reject"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "rejected"
    assert payload["payout_triggered"] is False
    assert called["count"] == 0


def test_put_resolve_returns_404_when_claim_missing():
    fake_db = _FakeDB()
    fake_db.first_results[Claim] = [None]

    client = _client_with_db(fake_db)
    response = client.put(f"/api/v1/claims/{uuid4()}/resolve", json={"resolution": "approve"})

    assert response.status_code == 404


def test_get_claim_detail_returns_404_when_missing():
    fake_db = _FakeDB()
    fake_db.first_results[Claim] = [None]

    client = _client_with_db(fake_db)
    response = client.get(f"/api/v1/claims/detail/{uuid4()}")

    assert response.status_code == 404


def test_get_worker_claim_history_returns_404_for_unknown_worker():
    fake_db = _FakeDB()
    fake_db.first_results[WorkerProfile] = [None]

    client = _client_with_db(fake_db)
    response = client.get(f"/api/v1/claims/{uuid4()}")

    assert response.status_code == 404


def test_put_resolve_approve_with_no_remaining_does_not_fire_payout(monkeypatch):
    fake_db = _FakeDB()
    claim_id = uuid4()
    worker_id = uuid4()

    fake_db.first_results[Claim] = [
        SimpleNamespace(
            id=claim_id,
            worker_id=worker_id,
            total_payout_amount=Decimal("400.00"),
            status="held",
        )
    ]
    fake_db.first_results[WorkerProfile] = [SimpleNamespace(id=worker_id, upi_vpa="worker@okaxis")]
    fake_db.scalar_default = [Decimal("400.00")]

    called = {"count": 0}
    monkeypatch.setattr(claims_api, "initiate_upi_payout", lambda *args: called.__setitem__("count", called["count"] + 1))

    client = _client_with_db(fake_db)
    response = client.put(f"/api/v1/claims/{claim_id}/resolve", json={"resolution": "approve"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["remaining_payout_attempted"] == 0.0
    assert payload["payout_triggered"] is False
    assert called["count"] == 0


def test_put_resolve_approve_returns_404_when_worker_missing():
    fake_db = _FakeDB()
    claim_id = uuid4()
    fake_db.first_results[Claim] = [
        SimpleNamespace(
            id=claim_id,
            worker_id=uuid4(),
            total_payout_amount=Decimal("400.00"),
            status="held",
        )
    ]
    fake_db.first_results[WorkerProfile] = [None]

    client = _client_with_db(fake_db)
    response = client.put(f"/api/v1/claims/{claim_id}/resolve", json={"resolution": "approve"})

    assert response.status_code == 404
