import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from pyod.models.cblof import CBLOF
from sklearn import metrics
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


FEATURE_COLUMNS = [
    "zone_claim_match",
    "activity_7d_score",
    "claim_to_enrollment_days",
    "event_claim_frequency",
]


def build_training_dataframe() -> pd.DataFrame:
    """Build deterministic 28-profile fraud training data."""
    profiles = [
        # 20 normal worker profiles
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 0.70, "claim_to_enrollment_days": 60, "event_claim_frequency": 0},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 0.72, "claim_to_enrollment_days": 75, "event_claim_frequency": 1},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 0.75, "claim_to_enrollment_days": 90, "event_claim_frequency": 0},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 0.78, "claim_to_enrollment_days": 105, "event_claim_frequency": 1},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 0.82, "claim_to_enrollment_days": 120, "event_claim_frequency": 2},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 0.85, "claim_to_enrollment_days": 135, "event_claim_frequency": 1},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 0.88, "claim_to_enrollment_days": 150, "event_claim_frequency": 0},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 0.90, "claim_to_enrollment_days": 165, "event_claim_frequency": 2},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 0.93, "claim_to_enrollment_days": 180, "event_claim_frequency": 1},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 0.96, "claim_to_enrollment_days": 195, "event_claim_frequency": 2},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 1.00, "claim_to_enrollment_days": 210, "event_claim_frequency": 1},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 1.03, "claim_to_enrollment_days": 225, "event_claim_frequency": 3},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 1.06, "claim_to_enrollment_days": 240, "event_claim_frequency": 1},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 1.09, "claim_to_enrollment_days": 255, "event_claim_frequency": 2},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 1.12, "claim_to_enrollment_days": 270, "event_claim_frequency": 1},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 1.15, "claim_to_enrollment_days": 285, "event_claim_frequency": 2},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 1.18, "claim_to_enrollment_days": 305, "event_claim_frequency": 3},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 1.22, "claim_to_enrollment_days": 325, "event_claim_frequency": 2},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 1.26, "claim_to_enrollment_days": 345, "event_claim_frequency": 3},
        {"profile_type": "normal", "zone_claim_match": 1, "activity_7d_score": 1.30, "claim_to_enrollment_days": 365, "event_claim_frequency": 2},
        # 3 GPS spoofer profiles
        {"profile_type": "gps_spoofer", "zone_claim_match": 0, "activity_7d_score": 0.90, "claim_to_enrollment_days": 90, "event_claim_frequency": 1},
        {"profile_type": "gps_spoofer", "zone_claim_match": 0, "activity_7d_score": 1.00, "claim_to_enrollment_days": 140, "event_claim_frequency": 2},
        {"profile_type": "gps_spoofer", "zone_claim_match": 0, "activity_7d_score": 1.10, "claim_to_enrollment_days": 200, "event_claim_frequency": 2},
        # 3 pre-event suppressor profiles
        {"profile_type": "pre_event_suppressor", "zone_claim_match": 1, "activity_7d_score": 0.10, "claim_to_enrollment_days": 20, "event_claim_frequency": 4},
        {"profile_type": "pre_event_suppressor", "zone_claim_match": 1, "activity_7d_score": 0.25, "claim_to_enrollment_days": 40, "event_claim_frequency": 6},
        {"profile_type": "pre_event_suppressor", "zone_claim_match": 1, "activity_7d_score": 0.40, "claim_to_enrollment_days": 60, "event_claim_frequency": 8},
        # 2 ring registration profiles
        {"profile_type": "ring_registration", "zone_claim_match": 1, "activity_7d_score": 0.80, "claim_to_enrollment_days": 5, "event_claim_frequency": 8},
        {"profile_type": "ring_registration", "zone_claim_match": 1, "activity_7d_score": 0.80, "claim_to_enrollment_days": 20, "event_claim_frequency": 12},
    ]

    df = pd.DataFrame(profiles)
    if len(df) != 28:
        raise ValueError(f"Expected 28 profiles, found {len(df)}")
    return df


def train_isolation_forest(features: np.ndarray) -> IsolationForest:
    """Train M3 Isolation Forest model."""
    model = IsolationForest(contamination=0.05, n_estimators=200, random_state=42)
    model.fit(features)
    return model


def train_cblof(features: np.ndarray) -> CBLOF:
    """Train M4 CBLOF model."""
    model = make_pipeline(
        StandardScaler(),
        CBLOF(contamination=0.05, n_clusters=3, random_state=42, alpha=0.6, beta=1.5),
    )
    model.fit(features)
    return model


def validate_models(
    df: pd.DataFrame,
    iso_model: IsolationForest,
    cblof_model: CBLOF,
) -> bool:
    """Check that a GPS spoofer profile is scored riskier than a normal profile."""
    normal_profile = df[df["profile_type"] == "normal"].iloc[[0]][FEATURE_COLUMNS].to_numpy()
    spoofer_profile = df[df["profile_type"] == "gps_spoofer"].iloc[[0]][FEATURE_COLUMNS].to_numpy()

    # Higher values below indicate higher anomaly likelihood.
    iso_normal = float(-iso_model.decision_function(normal_profile)[0])
    iso_spoofer = float(-iso_model.decision_function(spoofer_profile)[0])
    cblof_normal = float(cblof_model.decision_function(normal_profile)[0])
    cblof_spoofer = float(cblof_model.decision_function(spoofer_profile)[0])

    normal_score = max(iso_normal, cblof_normal)
    spoofer_score = max(iso_spoofer, cblof_spoofer)

    print(f"IsolationForest anomaly score - normal: {iso_normal:.6f}, gps_spoofer: {iso_spoofer:.6f}")
    print(f"CBLOF anomaly score           - normal: {cblof_normal:.6f}, gps_spoofer: {cblof_spoofer:.6f}")
    print(f"Ensemble max anomaly score    - normal: {normal_score:.6f}, gps_spoofer: {spoofer_score:.6f}")

    # Optional diagnostic metric over full dataset (fraud classes vs normal) for visibility.
    labels = (df["profile_type"] != "normal").astype(int).to_numpy()
    features = df[FEATURE_COLUMNS].to_numpy()
    ensemble_scores = np.maximum(
        -iso_model.decision_function(features),
        cblof_model.decision_function(features),
    )
    auc = metrics.roc_auc_score(labels, ensemble_scores)
    print(f"Diagnostic ROC-AUC (normal vs fraud profiles): {auc:.4f}")

    if spoofer_score <= normal_score:
        print("WARNING: GPS spoofer anomaly score is not higher than normal profile.")
        return False

    return True


def save_artifacts(iso_model: IsolationForest, cblof_model: CBLOF) -> None:
    """Persist trained artifacts to backend/app/ml/artifacts/."""
    artifact_dir = Path("backend/app/ml/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(iso_model, artifact_dir / "iso_forest_m3.joblib")
    joblib.dump(cblof_model, artifact_dir / "cblof_m4.joblib")
    print("Artifacts saved to backend/app/ml/artifacts/")


def main() -> int:
    df = build_training_dataframe()
    features = df[FEATURE_COLUMNS].to_numpy()

    iso_model = train_isolation_forest(features)
    cblof_model = train_cblof(features)

    is_valid = validate_models(df, iso_model, cblof_model)
    if not is_valid:
        return 1

    save_artifacts(iso_model, cblof_model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
