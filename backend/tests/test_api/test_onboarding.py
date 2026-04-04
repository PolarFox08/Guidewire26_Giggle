import hashlib
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.core.database import get_db
from app.api.onboarding import router
from app.models.audit import AuditEvent
from app.models.policy import Policy
from app.models.platform_partner import PlatformPartner
from app.models.worker import WorkerProfile


def _get_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class _FakePartner:
    def __init__(self, platform: str, partner_id: str, partner_name: str):
        self.platform = platform
        self.partner_id = partner_id
        self.partner_name = partner_name


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters = {}

    def filter_by(self, **kwargs):
        self._filters.update(kwargs)
        return self

    def first(self):
        for row in self._rows:
            if row.platform == self._filters.get("platform") and row.partner_id == self._filters.get("partner_id"):
                return row
        return None


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, _model):
        return _FakeQuery(self._rows)


def _get_test_client_with_partner_rows(rows) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield _FakeDB(rows)

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


class _FakeWorkerQuery:
    def __init__(self, db, model):
        self._db = db
        self._model = model
        self._filters = {}

    def filter_by(self, **kwargs):
        self._filters.update(kwargs)
        return self

    def first(self):
        for row in self._rows_for_model():
            if all(getattr(row, key, None) == value for key, value in self._filters.items()):
                return row
        return None

    def _rows_for_model(self):
        if self._model is WorkerProfile:
            return self._db.worker_profiles
        if self._model is PlatformPartner:
            return self._db.platform_partners
        if self._model is Policy:
            return self._db.policies
        if self._model is AuditEvent:
            return self._db.audit_events
        return []


class _FakeRegistrationDB:
    def __init__(self, worker_profiles=None, platform_partners=None):
        self.worker_profiles = worker_profiles or []
        self.platform_partners = platform_partners or []
        self.policies = []
        self.audit_events = []

    def query(self, model):
        return _FakeWorkerQuery(self, model)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()

        if isinstance(obj, WorkerProfile):
            self.worker_profiles.append(obj)
        elif isinstance(obj, Policy):
            self.policies.append(obj)
        elif isinstance(obj, AuditEvent):
            self.audit_events.append(obj)

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, _obj):
        return None


class _FakePremiumClient:
    def __init__(self, timeout=5.0):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, _url, json):
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "premium_amount": 82.0,
                "model_used": "glm",
                "shap_top3": [],
                "worker_id": json["worker_id"],
            },
        )


def _build_register_client(db: _FakeRegistrationDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_aadhaar_kyc_valid_returns_hash():
    client = _get_test_client()

    response = client.post(
        "/api/v1/onboarding/kyc/aadhaar",
        json={"aadhaar_number": "123456789012", "otp": "123456"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["aadhaar_hash"] == hashlib.sha256("123456789012".encode("utf-8")).hexdigest()


def test_aadhaar_kyc_strips_spaces_before_validation_and_hashing():
    client = _get_test_client()

    response = client.post(
        "/api/v1/onboarding/kyc/aadhaar",
        json={"aadhaar_number": "1234 5678 9012", "otp": "123456"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["aadhaar_hash"] == hashlib.sha256("123456789012".encode("utf-8")).hexdigest()


def test_aadhaar_kyc_rejects_short_aadhaar():
    client = _get_test_client()

    response = client.post(
        "/api/v1/onboarding/kyc/aadhaar",
        json={"aadhaar_number": "12345678901", "otp": "123456"},
    )

    assert response.status_code == 400


def test_aadhaar_kyc_rejects_long_aadhaar():
    client = _get_test_client()

    response = client.post(
        "/api/v1/onboarding/kyc/aadhaar",
        json={"aadhaar_number": "1234567890123", "otp": "123456"},
    )

    assert response.status_code == 400


def test_pan_kyc_rejects_invalid_format():
    client = _get_test_client()

    response = client.post(
        "/api/v1/onboarding/kyc/pan",
        json={"pan_number": "abcde1234f"},
    )

    assert response.status_code == 400


def test_pan_kyc_valid_returns_hash():
    client = _get_test_client()

    response = client.post(
        "/api/v1/onboarding/kyc/pan",
        json={"pan_number": "ABCDE1234F"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["pan_hash"] == hashlib.sha256("ABCDE1234F".encode("utf-8")).hexdigest()


def test_bank_kyc_rejects_upi_without_at_sign():
    client = _get_test_client()

    response = client.post(
        "/api/v1/onboarding/kyc/bank",
        json={"upi_vpa": "workerokaxis"},
    )

    assert response.status_code == 400


def test_bank_kyc_rejects_upi_too_short():
    client = _get_test_client()

    response = client.post(
        "/api/v1/onboarding/kyc/bank",
        json={"upi_vpa": "a@b"},
    )

    assert response.status_code == 400


def test_bank_kyc_valid_upi_returns_mocked_bank_details():
    client = _get_test_client()

    response = client.post(
        "/api/v1/onboarding/kyc/bank",
        json={"upi_vpa": "worker@okaxis"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["bank_name"] == "HDFC Bank"
    assert body["account_type"] == "savings"


def test_platform_verify_rejects_unknown_platform():
    client = _get_test_client_with_partner_rows([])

    response = client.post(
        "/api/v1/onboarding/platform/verify",
        json={"platform": "paytm", "partner_id": "PTM-TEST-001"},
    )

    assert response.status_code == 400


def test_platform_verify_returns_404_for_unknown_partner_id():
    rows = [_FakePartner("zomato", "ZOM-TEST-001", "Arun Kumar")]
    client = _get_test_client_with_partner_rows(rows)

    response = client.post(
        "/api/v1/onboarding/platform/verify",
        json={"platform": "zomato", "partner_id": "ZOM-TEST-999"},
    )

    assert response.status_code == 404


def test_platform_verify_returns_verified_for_known_partner_id():
    rows = [_FakePartner("swiggy", "SWY-TEST-001", "Akash Verma")]
    client = _get_test_client_with_partner_rows(rows)

    response = client.post(
        "/api/v1/onboarding/platform/verify",
        json={"platform": "swiggy", "partner_id": "SWY-TEST-001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["partner_name"] == "Akash Verma"


def test_register_complete_valid_registration_returns_waiting(monkeypatch):
    monkeypatch.setattr("app.api.onboarding.get_flood_tier_for_pincode", lambda _pincode: "high")
    monkeypatch.setattr("app.api.onboarding.get_zone_cluster_for_pincode", lambda _pincode: 4)
    monkeypatch.setattr("app.api.onboarding.httpx.Client", _FakePremiumClient)

    db = _FakeRegistrationDB()
    client = _build_register_client(db)

    payload = {
        "aadhaar_hash": "a" * 64,
        "pan_hash": "b" * 64,
        "upi_vpa": "worker@okaxis",
        "platform": "zomato",
        "partner_id": "ZOM-NEW-001",
        "pincode": 600042,
        "device_fingerprint": "fp-device-001",
        "language_preference": "ta",
    }

    response = client.post("/api/v1/onboarding/register", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "waiting"
    assert body["days_until_eligible"] == 28
    assert body["weekly_premium_amount"] == 82.0
    assert body["coverage_start"] is None


def test_register_missing_device_fingerprint_returns_422(monkeypatch):
    monkeypatch.setattr("app.api.onboarding.get_flood_tier_for_pincode", lambda _pincode: "high")
    monkeypatch.setattr("app.api.onboarding.get_zone_cluster_for_pincode", lambda _pincode: 4)
    monkeypatch.setattr("app.api.onboarding.httpx.Client", _FakePremiumClient)

    db = _FakeRegistrationDB()
    client = _build_register_client(db)

    payload = {
        "aadhaar_hash": "a" * 64,
        "pan_hash": "b" * 64,
        "upi_vpa": "worker@okaxis",
        "platform": "zomato",
        "partner_id": "ZOM-NEW-001",
        "pincode": 600042,
        "language_preference": "ta",
    }

    response = client.post("/api/v1/onboarding/register", json=payload)

    assert response.status_code == 422


def test_register_duplicate_aadhaar_returns_409(monkeypatch):
    monkeypatch.setattr("app.api.onboarding.get_flood_tier_for_pincode", lambda _pincode: "high")
    monkeypatch.setattr("app.api.onboarding.get_zone_cluster_for_pincode", lambda _pincode: 4)
    monkeypatch.setattr("app.api.onboarding.httpx.Client", _FakePremiumClient)

    existing_worker = WorkerProfile(
        id=uuid.uuid4(),
        aadhaar_hash="a" * 64,
        pan_hash="c" * 64,
        platform="zomato",
        partner_id="ZOM-OLD-001",
        pincode=600042,
        flood_hazard_tier="high",
        zone_cluster_id=4,
        upi_vpa="old@okaxis",
        device_fingerprint="fp-existing",
        language_preference="ta",
    )
    db = _FakeRegistrationDB(worker_profiles=[existing_worker])
    client = _build_register_client(db)

    payload = {
        "aadhaar_hash": "a" * 64,
        "pan_hash": "b" * 64,
        "upi_vpa": "worker@okaxis",
        "platform": "zomato",
        "partner_id": "ZOM-NEW-001",
        "pincode": 600042,
        "device_fingerprint": "fp-device-001",
        "language_preference": "ta",
    }

    response = client.post("/api/v1/onboarding/register", json=payload)

    assert response.status_code == 409


def test_register_duplicate_pan_returns_409(monkeypatch):
    monkeypatch.setattr("app.api.onboarding.get_flood_tier_for_pincode", lambda _pincode: "high")
    monkeypatch.setattr("app.api.onboarding.get_zone_cluster_for_pincode", lambda _pincode: 4)
    monkeypatch.setattr("app.api.onboarding.httpx.Client", _FakePremiumClient)

    existing_worker = WorkerProfile(
        id=uuid.uuid4(),
        aadhaar_hash="c" * 64,
        pan_hash="b" * 64,
        platform="zomato",
        partner_id="ZOM-OLD-002",
        pincode=600042,
        flood_hazard_tier="high",
        zone_cluster_id=4,
        upi_vpa="old@okaxis",
        device_fingerprint="fp-existing",
        language_preference="ta",
    )
    db = _FakeRegistrationDB(worker_profiles=[existing_worker])
    client = _build_register_client(db)

    payload = {
        "aadhaar_hash": "a" * 64,
        "pan_hash": "b" * 64,
        "upi_vpa": "worker@okaxis",
        "platform": "zomato",
        "partner_id": "ZOM-NEW-001",
        "pincode": 600042,
        "device_fingerprint": "fp-device-001",
        "language_preference": "ta",
    }

    response = client.post("/api/v1/onboarding/register", json=payload)

    assert response.status_code == 409


def test_register_duplicate_device_fingerprint_is_not_blocked_and_audited(monkeypatch):
    monkeypatch.setattr("app.api.onboarding.get_flood_tier_for_pincode", lambda _pincode: "high")
    monkeypatch.setattr("app.api.onboarding.get_zone_cluster_for_pincode", lambda _pincode: 4)
    monkeypatch.setattr("app.api.onboarding.httpx.Client", _FakePremiumClient)

    existing_worker = WorkerProfile(
        id=uuid.uuid4(),
        aadhaar_hash="c" * 64,
        pan_hash="d" * 64,
        platform="zomato",
        partner_id="ZOM-OLD-003",
        pincode=600042,
        flood_hazard_tier="high",
        zone_cluster_id=4,
        upi_vpa="old@okaxis",
        device_fingerprint="same-fp",
        language_preference="ta",
    )
    db = _FakeRegistrationDB(worker_profiles=[existing_worker])
    client = _build_register_client(db)

    payload = {
        "aadhaar_hash": "a" * 64,
        "pan_hash": "b" * 64,
        "upi_vpa": "worker@okaxis",
        "platform": "zomato",
        "partner_id": "ZOM-NEW-001",
        "pincode": 600042,
        "device_fingerprint": "same-fp",
        "language_preference": "ta",
    }

    response = client.post("/api/v1/onboarding/register", json=payload)

    assert response.status_code == 200
    assert any(event.event_type == "device_fingerprint_collision" for event in db.audit_events)


def test_register_known_pincode_600042_sets_high_flood_tier(monkeypatch):
    monkeypatch.setattr(
        "app.api.onboarding.get_flood_tier_for_pincode",
        lambda pincode: "high" if pincode == 600042 else "low",
    )
    monkeypatch.setattr("app.api.onboarding.get_zone_cluster_for_pincode", lambda _pincode: 2)
    monkeypatch.setattr("app.api.onboarding.httpx.Client", _FakePremiumClient)

    db = _FakeRegistrationDB()
    client = _build_register_client(db)

    payload = {
        "aadhaar_hash": "e" * 64,
        "pan_hash": "f" * 64,
        "upi_vpa": "worker@okaxis",
        "platform": "zomato",
        "partner_id": "ZOM-NEW-002",
        "pincode": 600042,
        "device_fingerprint": "fp-device-002",
        "language_preference": "ta",
    }

    response = client.post("/api/v1/onboarding/register", json=payload)

    assert response.status_code == 200
    assert db.worker_profiles[-1].flood_hazard_tier == "high"


def test_register_unknown_pincode_defaults_to_low(monkeypatch):
    monkeypatch.setattr("app.api.onboarding.get_flood_tier_for_pincode", lambda _pincode: "low")
    monkeypatch.setattr("app.api.onboarding.get_zone_cluster_for_pincode", lambda _pincode: 1)
    monkeypatch.setattr("app.api.onboarding.httpx.Client", _FakePremiumClient)

    db = _FakeRegistrationDB()
    client = _build_register_client(db)

    payload = {
        "aadhaar_hash": "1" * 64,
        "pan_hash": "2" * 64,
        "upi_vpa": "worker@okaxis",
        "platform": "swiggy",
        "partner_id": "SWY-NEW-001",
        "pincode": 999999,
        "device_fingerprint": "fp-device-003",
        "language_preference": "en",
    }

    response = client.post("/api/v1/onboarding/register", json=payload)

    assert response.status_code == 200
    assert db.worker_profiles[-1].flood_hazard_tier == "low"


def test_register_writes_worker_registered_audit_event(monkeypatch):
    monkeypatch.setattr("app.api.onboarding.get_flood_tier_for_pincode", lambda _pincode: "high")
    monkeypatch.setattr("app.api.onboarding.get_zone_cluster_for_pincode", lambda _pincode: 9)
    monkeypatch.setattr("app.api.onboarding.httpx.Client", _FakePremiumClient)

    db = _FakeRegistrationDB()
    client = _build_register_client(db)

    payload = {
        "aadhaar_hash": "3" * 64,
        "pan_hash": "4" * 64,
        "upi_vpa": "worker@okaxis",
        "platform": "zomato",
        "partner_id": "ZOM-NEW-004",
        "pincode": 600042,
        "device_fingerprint": "fp-device-004",
        "language_preference": "ta",
    }

    response = client.post("/api/v1/onboarding/register", json=payload)

    assert response.status_code == 200
    worker_registered_events = [event for event in db.audit_events if event.event_type == "worker_registered"]
    assert len(worker_registered_events) == 1
    assert worker_registered_events[0].payload["zone_cluster_id"] == 9
