"""Razorpay sandbox payout client utilities.

When RAZORPAY_KEY_ID is empty or a placeholder (starts with 'rzp_test_placeholder'
or is empty), the client operates in MOCK mode — returning a simulated successful
payout without calling the real Razorpay API. This is valid for hackathon demo
purposes where the requirement is 'simulated / test mode'.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.core.config import settings

LOGGER = logging.getLogger(__name__)

MIN_PAYOUT_PAISE = 100


def _is_mock_mode() -> bool:
    """Return True when Razorpay keys are missing or placeholder values."""
    key = settings.razorpay_key_id.strip()
    return not key or key.startswith("rzp_test_placeholder")


def validate_upi_vpa(vpa: str) -> bool:
    """Validate VPA format and length for payout eligibility."""
    if not isinstance(vpa, str):
        return False

    normalized = vpa.strip()
    if not normalized:
        return False

    if len(normalized) < 5 or len(normalized) > 100:
        return False

    return "@" in normalized


def _build_client() -> Any:
    """Create Razorpay SDK client using configured sandbox keys."""
    import razorpay

    return razorpay.Client(
        auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
    )


def _mock_payout_response(vpa: str, amount_rupees: float, claim_id: str) -> dict[str, Any]:
    """Return a simulated successful Razorpay payout for demo/sandbox mode."""
    mock_id = f"pout_MOCK_{uuid.uuid4().hex[:16].upper()}"
    LOGGER.info(
        "MOCK MODE: Simulating Razorpay UPI payout of Rs%.2f to %s (claim %s) -> payout_id=%s",
        amount_rupees,
        vpa,
        claim_id,
        mock_id,
    )
    return {
        "success": True,
        "payout_id": mock_id,
        "status": "paid",
        "mock": True,
    }


def initiate_upi_payout(vpa: str, amount_rupees: float, claim_id: str) -> dict[str, Any]:
    """Initiate UPI payout via Razorpay Payout API in test/sandbox mode.

    Falls back to mock simulation when API keys are not configured.
    This is the standard approach for hackathon demos as permitted by the contest rules.
    """
    if not validate_upi_vpa(vpa):
        return {"success": False, "error": "invalid_vpa"}

    amount_paise = int(round(float(amount_rupees) * 100))
    if amount_paise < MIN_PAYOUT_PAISE:
        return {"success": False, "error": "amount_below_minimum"}

    # ── Mock mode (no real keys configured) ───────────────────────────────────
    if _is_mock_mode():
        return _mock_payout_response(vpa, amount_rupees, claim_id)

    # ── Real Razorpay sandbox call ─────────────────────────────────────────────
    payload = {
        "account_number": "2323230000000000",
        "fund_account": {
            "account_type": "vpa",
            "vpa": {
                "address": vpa.strip(),
            },
            "contact": {
                "name": "Giggle Worker",
                "type": "employee",
                "reference_id": str(claim_id),
            },
        },
        "amount": amount_paise,
        "currency": "INR",
        "mode": "UPI",
        "purpose": "payout",
        "reference_id": str(claim_id),
        "narration": "Giggle claim payout",
    }

    try:
        client = _build_client()
        if hasattr(client, "payout") and hasattr(client.payout, "create"):
            response = client.payout.create(payload)
        elif hasattr(client, "payouts") and hasattr(client.payouts, "create"):
            response = client.payouts.create(payload)
        else:
            response = client.post("/payouts", payload)
        return {
            "success": True,
            "payout_id": response.get("id"),
            "status": response.get("status"),
        }
    except Exception as exc:  # Razorpay SDK exceptions are surfaced as runtime errors.
        LOGGER.warning("Razorpay payout initiation failed for claim %s: %s", claim_id, exc)
        return {"success": False, "error": str(exc)}
