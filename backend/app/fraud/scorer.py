"""Fraud model artifact loading and scoring utilities."""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np

LOGGER = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "ml" / "artifacts"
ISO_FOREST_ARTIFACT = "iso_forest_m3.joblib"
CBLOF_ARTIFACT = "cblof_m4.joblib"

IF_MODEL = None
CBLOF_MODEL = None
IF_LOADED = False
CBLOF_LOADED = False


def _load_model_artifacts(artifacts_dir: Path = ARTIFACTS_DIR) -> tuple[object | None, object | None, bool, bool]:
    """Load fraud artifacts once at startup, falling back safely when absent."""
    iso_path = artifacts_dir / ISO_FOREST_ARTIFACT
    cblof_path = artifacts_dir / CBLOF_ARTIFACT

    if not iso_path.exists() or not cblof_path.exists():
        LOGGER.warning(
            "Fraud models not found — scorer will return default score 0.1 until models are loaded"
        )
        return None, None, False, False

    try:
        if_model = joblib.load(iso_path)
        cblof_model = joblib.load(cblof_path)
    except Exception:
        LOGGER.warning(
            "Fraud models not found — scorer will return default score 0.1 until models are loaded"
        )
        return None, None, False, False

    return if_model, cblof_model, True, True


IF_MODEL, CBLOF_MODEL, IF_LOADED, CBLOF_LOADED = _load_model_artifacts()


def compute_fraud_score(
    zone_claim_match: int,
    activity_7d_score: float,
    claim_to_enrollment_days: int,
    event_claim_frequency: int,
) -> float:
    """Compute fraud score from IF and CBLOF models with safe fallback behavior."""
    if not IF_LOADED and not CBLOF_LOADED:
        return 0.1

    features = np.array(
        [[zone_claim_match, activity_7d_score, claim_to_enrollment_days, event_claim_frequency]],
        dtype=float,
    )

    if_score = 0.0
    cblof_score = 0.0

    if IF_LOADED and IF_MODEL is not None:
        raw_if_score = float(IF_MODEL.decision_function(features)[0])
        # Map expected IF range of roughly [-0.5, 0.5] to anomaly score where higher is riskier.
        if_score = 1 - (raw_if_score + 0.5)
        if_score = float(min(max(if_score, 0.0), 1.0))

    if CBLOF_LOADED and CBLOF_MODEL is not None:
        cblof_proba = CBLOF_MODEL.predict_proba(features)
        cblof_score = float(cblof_proba[0][1])
        cblof_score = float(min(max(cblof_score, 0.0), 1.0))

    final_score = max(if_score, cblof_score)
    return float(min(max(final_score, 0.0), 1.0))


def route_claim(fraud_score: float) -> str:
    """Map fraud score to routing decision."""
    if fraud_score < 0.3:
        return "auto_approve"
    if fraud_score <= 0.7:
        return "partial_review"
    return "hold"
