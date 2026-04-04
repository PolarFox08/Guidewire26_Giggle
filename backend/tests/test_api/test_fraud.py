import sys
from unittest.mock import MagicMock
from pathlib import Path
import importlib

import joblib
import numpy as np
import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.fraud.behavioral import (
    check_conditional_baseline_floor,
    check_rain_paradox,
    compute_activity_7d_score,
    compute_enrollment_recency_score,
)
from app.fraud.graph import detect_ring_registrations
import app.fraud.scorer as scorer


def test_compute_activity_7d_score_returns_ratio_for_standard_case():
    assert compute_activity_7d_score(70, 10) == 1.0


def test_compute_activity_7d_score_returns_default_when_average_is_zero():
    assert compute_activity_7d_score(70, 0) == 0.5


def test_compute_activity_7d_score_caps_ratio_at_1_point_5():
    assert compute_activity_7d_score(140, 10) == 1.5


def test_compute_enrollment_recency_score_week_one_is_about_0_point_96():
    assert compute_enrollment_recency_score(1) == 1 - (1 / 26)


def test_compute_enrollment_recency_score_week_26_is_zero():
    assert compute_enrollment_recency_score(26) == 0.0


def test_compute_enrollment_recency_score_week_52_is_clamped_to_zero():
    assert compute_enrollment_recency_score(52) == 0.0


def test_check_rain_paradox_low_tier_above_threshold_is_true():
    assert check_rain_paradox("low", 1.15) is True


def test_check_rain_paradox_high_tier_above_threshold_is_false():
    assert check_rain_paradox("high", 1.15) is False


def test_check_rain_paradox_medium_tier_above_threshold_is_false():
    assert check_rain_paradox("medium", 1.15) is False


def test_check_rain_paradox_low_tier_below_threshold_is_false():
    assert check_rain_paradox("low", 1.05) is False


def test_check_conditional_baseline_floor_both_true_is_true():
    assert check_conditional_baseline_floor(True, True) is True


def test_check_conditional_baseline_floor_dropped_without_forecast_is_false():
    assert check_conditional_baseline_floor(True, False) is False


def test_check_conditional_baseline_floor_forecast_without_drop_is_false():
    assert check_conditional_baseline_floor(False, True) is False


def test_check_conditional_baseline_floor_both_false_is_false():
    assert check_conditional_baseline_floor(False, False) is False


def test_detect_ring_registrations_three_workers_same_device_returns_one_ring_of_three():
    db = MagicMock()
    db.query.return_value.all.return_value = [
        ("worker-uuid-1", "device-a", "ip-1"),
        ("worker-uuid-2", "device-a", "ip-2"),
        ("worker-uuid-3", "device-a", "ip-3"),
    ]

    result = detect_ring_registrations(db)

    assert result == [["worker-uuid-1", "worker-uuid-2", "worker-uuid-3"]]


def test_detect_ring_registrations_two_workers_same_ip_only_returns_one_ring_of_two():
    db = MagicMock()
    db.query.return_value.all.return_value = [
        ("worker-uuid-1", "device-a", "ip-shared"),
        ("worker-uuid-2", "device-b", "ip-shared"),
    ]

    result = detect_ring_registrations(db)

    assert result == [["worker-uuid-1", "worker-uuid-2"]]


def test_detect_ring_registrations_two_separate_pairs_returns_two_rings():
    db = MagicMock()
    db.query.return_value.all.return_value = [
        ("worker-uuid-1", "device-a", "ip-1"),
        ("worker-uuid-2", "device-a", "ip-2"),
        ("worker-uuid-3", "device-b", "ip-3"),
        ("worker-uuid-4", "device-b", "ip-4"),
    ]

    result = detect_ring_registrations(db)

    assert result == [
        ["worker-uuid-1", "worker-uuid-2"],
        ["worker-uuid-3", "worker-uuid-4"],
    ]


def test_detect_ring_registrations_all_unique_returns_empty_list():
    db = MagicMock()
    db.query.return_value.all.return_value = [
        ("worker-uuid-1", "device-a", "ip-1"),
        ("worker-uuid-2", "device-b", "ip-2"),
        ("worker-uuid-3", "device-c", "ip-3"),
    ]

    result = detect_ring_registrations(db)

    assert result == []


def test_detect_ring_registrations_mixed_ring_and_solos_returns_only_ring():
    db = MagicMock()
    db.query.return_value.all.return_value = [
        ("worker-uuid-1", "device-a", "ip-1"),
        ("worker-uuid-2", "device-a", "ip-2"),
        ("worker-uuid-3", "device-c", "ip-2"),
        ("worker-uuid-4", "device-d", "ip-4"),
        ("worker-uuid-5", "device-e", "ip-5"),
    ]

    result = detect_ring_registrations(db)

    assert result == [["worker-uuid-1", "worker-uuid-2", "worker-uuid-3"]]


def test_load_model_artifacts_returns_flags_false_when_files_missing(caplog, tmp_path):
    with caplog.at_level("WARNING"):
        if_model, cblof_model, if_loaded, cblof_loaded = scorer._load_model_artifacts(tmp_path)

    assert if_model is None
    assert cblof_model is None
    assert if_loaded is False
    assert cblof_loaded is False
    assert (
        "Fraud models not found — scorer will return default score 0.1 until models are loaded"
        in caplog.text
    )


def test_load_model_artifacts_returns_flags_true_when_files_exist(tmp_path):
    iso_path = tmp_path / scorer.ISO_FOREST_ARTIFACT
    cblof_path = tmp_path / scorer.CBLOF_ARTIFACT

    iso_obj = {"model": "if"}
    cblof_obj = {"model": "cblof"}

    joblib.dump(iso_obj, iso_path)
    joblib.dump(cblof_obj, cblof_path)

    if_model, cblof_model, if_loaded, cblof_loaded = scorer._load_model_artifacts(tmp_path)

    assert if_loaded is True
    assert cblof_loaded is True
    assert if_model == iso_obj
    assert cblof_model == cblof_obj


def test_module_startup_loader_sets_flags_when_artifacts_missing(monkeypatch):
    monkeypatch.setattr(scorer.Path, "exists", lambda self: False)

    reloaded = importlib.reload(scorer)

    assert reloaded.IF_LOADED is False
    assert reloaded.CBLOF_LOADED is False


def test_compute_fraud_score_returns_default_when_models_not_loaded(monkeypatch):
    monkeypatch.setattr(scorer, "IF_LOADED", False)
    monkeypatch.setattr(scorer, "CBLOF_LOADED", False)
    monkeypatch.setattr(scorer, "IF_MODEL", None)
    monkeypatch.setattr(scorer, "CBLOF_MODEL", None)

    score = scorer.compute_fraud_score(1, 1.0, 180, 2)

    assert score == 0.1


def test_compute_fraud_score_returns_max_of_if_and_cblof(monkeypatch):
    if_model = MagicMock()
    if_model.decision_function.return_value = np.array([-0.1])

    cblof_model = MagicMock()
    cblof_model.predict_proba.return_value = np.array([[0.7, 0.3]])

    monkeypatch.setattr(scorer, "IF_LOADED", True)
    monkeypatch.setattr(scorer, "CBLOF_LOADED", True)
    monkeypatch.setattr(scorer, "IF_MODEL", if_model)
    monkeypatch.setattr(scorer, "CBLOF_MODEL", cblof_model)

    score = scorer.compute_fraud_score(1, 1.0, 180, 2)

    assert score == 0.6


def test_route_claim_0_point_29_auto_approve():
    assert scorer.route_claim(0.29) == "auto_approve"


def test_route_claim_0_point_30_partial_review():
    assert scorer.route_claim(0.30) == "partial_review"


def test_route_claim_0_point_70_partial_review():
    assert scorer.route_claim(0.70) == "partial_review"


def test_route_claim_0_point_71_hold():
    assert scorer.route_claim(0.71) == "hold"


def test_compute_fraud_score_gps_spoofer_vector_with_real_models_is_high():
    artifacts_dir = scorer.ARTIFACTS_DIR
    if not (
        (artifacts_dir / scorer.ISO_FOREST_ARTIFACT).exists()
        and (artifacts_dir / scorer.CBLOF_ARTIFACT).exists()
    ):
        pytest.skip("Fraud artifacts not present; skipping integration test.")

    if_model, cblof_model, if_loaded, cblof_loaded = scorer._load_model_artifacts(artifacts_dir)
    if not (if_loaded and cblof_loaded):
        pytest.skip("Fraud artifacts could not be loaded; skipping integration test.")

    original_if_model = scorer.IF_MODEL
    original_cblof_model = scorer.CBLOF_MODEL
    original_if_loaded = scorer.IF_LOADED
    original_cblof_loaded = scorer.CBLOF_LOADED

    try:
        scorer.IF_MODEL = if_model
        scorer.CBLOF_MODEL = cblof_model
        scorer.IF_LOADED = True
        scorer.CBLOF_LOADED = True

        score = scorer.compute_fraud_score(0, 1.0, 180, 2)
    finally:
        scorer.IF_MODEL = original_if_model
        scorer.CBLOF_MODEL = original_cblof_model
        scorer.IF_LOADED = original_if_loaded
        scorer.CBLOF_LOADED = original_cblof_loaded

    assert score > 0.5