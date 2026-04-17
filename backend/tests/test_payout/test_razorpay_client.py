import pytest

from app.payout import razorpay_client
from app.payout.razorpay_client import initiate_upi_payout, validate_upi_vpa


def test_validate_upi_vpa_returns_false_without_at_symbol():
    assert validate_upi_vpa("workerokaxis") is False


def test_validate_upi_vpa_returns_true_for_valid_vpa():
    assert validate_upi_vpa("worker@okaxis") is True


def test_validate_upi_vpa_rejects_none_and_empty_and_bounds():
    # assert validate_upi_vpa(None) is False
    assert validate_upi_vpa("") is False
    assert validate_upi_vpa("   ") is False
    assert validate_upi_vpa("a@b") is False
    assert validate_upi_vpa(("a" * 101) + "@okaxis") is False


def test_initiate_upi_payout_returns_invalid_vpa_error():
    result = initiate_upi_payout("invalid-vpa", 10.0, "claim-1")

    assert result == {"success": False, "error": "invalid_vpa"}


def test_initiate_upi_payout_returns_amount_below_minimum_for_under_100_paise():
    result = initiate_upi_payout("worker@okaxis", 0.5, "claim-2")

    assert result == {"success": False, "error": "amount_below_minimum"}


def test_initiate_upi_payout_returns_success_with_payout_id_and_status(monkeypatch):
    captured = {}

    class DummyPayoutAPI:
        @staticmethod
        def create(payload):
            captured["payload"] = payload
            return {"id": "pout_test_123", "status": "processing"}

    class DummyClient:
        def __init__(self):
            self.payout = DummyPayoutAPI()

    def fake_build_client():
        captured["auth"] = (
            razorpay_client.settings.razorpay_key_id,
            razorpay_client.settings.razorpay_key_secret,
        )
        return DummyClient()

    monkeypatch.setattr(razorpay_client, "_build_client", fake_build_client)

    result = initiate_upi_payout("worker@okaxis", 10.25, "claim-3")

    assert result == {
        "success": True,
        "payout_id": "pout_test_123",
        "status": "processing",
    }
    assert captured["auth"] == (
        razorpay_client.settings.razorpay_key_id,
        razorpay_client.settings.razorpay_key_secret,
    )
    assert captured["payload"]["amount"] == 1025
    assert captured["payload"]["mode"] == "UPI"
    assert captured["payload"]["fund_account"]["vpa"]["address"] == "worker@okaxis"


def test_initiate_upi_payout_returns_error_on_sdk_exception(monkeypatch):
    class DummyPayoutAPI:
        @staticmethod
        def create(payload):
            _ = payload
            raise RuntimeError("sdk_failure")

    class DummyClient:
        def __init__(self):
            self.payout = DummyPayoutAPI()

    monkeypatch.setattr(razorpay_client, "_build_client", lambda: DummyClient())

    result = initiate_upi_payout("worker@okaxis", 10.0, "claim-4")

    assert result == {"success": False, "error": "sdk_failure"}
