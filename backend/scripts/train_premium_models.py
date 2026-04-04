"""Training pipeline for Giggle premium models.

This script is intended to run in Kaggle and produce premium artifacts:
- app/ml/artifacts/glm_m1.joblib
- app/ml/artifacts/lgbm_m2.joblib
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
import statsmodels.api as sm
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

DEFAULT_INPUT_CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "synthetic_training_data.csv"
DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "app" / "ml" / "artifacts"

M1_FEATURES = ["flood_hazard_zone_tier", "season_flag", "platform"]
M2_FEATURES = [
    "flood_hazard_zone_tier",
    "zone_cluster_id",
    "platform",
    "delivery_baseline_30d",
    "income_baseline_weekly",
    "enrollment_week",
    "season_flag",
    "open_meteo_7d_precip_probability",
    "activity_consistency_score",
    "tenure_discount_factor",
    "historical_claim_rate_zone",
]
TARGET_COLUMN = "weekly_premium"

REQUIRED_COLUMNS = sorted(set(M1_FEATURES + M2_FEATURES + [TARGET_COLUMN, "enrollment_week"]))


def load_training_data(csv_path: Path) -> pd.DataFrame:
    """Load and validate training data required for M1 and M2 training."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Training CSV not found: {csv_path}")

    frame = pd.read_csv(csv_path)
    if frame.empty:
        raise ValueError(f"Training CSV is empty: {csv_path}")

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Training CSV is missing required columns: {', '.join(missing)}")

    logger.info("Loaded training data from %s with shape=%s", csv_path, frame.shape)
    return frame


def train_m1_glm_cold_start(frame: pd.DataFrame, artifact_path: Path) -> dict[str, Any]:
    """Train and save M1 GLM cold-start premium model.

    M1 uses only week 1-4 rows and exactly three categorical features:
    flood_hazard_zone_tier, season_flag, platform.
    """
    subset = frame.loc[frame["enrollment_week"] < 5].copy()
    if subset.empty:
        raise ValueError("No rows found for M1 training (enrollment_week < 5).")

    missing = [column for column in M1_FEATURES + [TARGET_COLUMN] if column not in subset.columns]
    if missing:
        raise ValueError(f"M1 training data is missing required columns: {', '.join(missing)}")

    x = subset[M1_FEATURES].copy()
    y = subset[TARGET_COLUMN].astype(float)

    encoders: dict[str, LabelEncoder] = {}
    for column in M1_FEATURES:
        encoder = LabelEncoder()
        x[column] = encoder.fit_transform(x[column].astype(str))
        encoders[column] = encoder

    x_train, x_valid, y_train, y_valid = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
    )

    x_train_const = sm.add_constant(x_train, has_constant="add")
    x_valid_const = sm.add_constant(x_valid, has_constant="add")

    glm_model = sm.GLM(
        y_train,
        x_train_const,
        family=sm.families.Tweedie(var_power=1.5, link=sm.families.links.Log()),
    )
    glm_result = glm_model.fit()

    predictions = glm_result.predict(x_valid_const)
    rmse = float(np.sqrt(mean_squared_error(y_valid, predictions)))

    artifact = {
        "model_name": "glm_cold_start",
        "features": M1_FEATURES,
        "target": TARGET_COLUMN,
        "encoders": encoders,
        "model": glm_result,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, artifact_path)

    logger.info(
        "M1 GLM trained. rows=%d, train=%d, valid=%d, rmse=%.4f, artifact=%s",
        len(subset),
        len(x_train),
        len(x_valid),
        rmse,
        artifact_path,
    )
    print(f"M1 RMSE: {rmse:.4f}")

    return {
        "rmse": rmse,
        "train_rows": int(len(x_train)),
        "valid_rows": int(len(x_valid)),
        "artifact_path": str(artifact_path),
    }


def train_m2_lgbm_weekly(
    frame: pd.DataFrame,
    model_artifact_path: Path,
    shap_artifact_path: Path,
    feature_list_artifact_path: Path,
) -> dict[str, Any]:
    """Train and save M2 LightGBM weekly premium model and SHAP explainer."""
    subset = frame.loc[frame["enrollment_week"] >= 5].copy()
    if subset.empty:
        raise ValueError("No rows found for M2 training (enrollment_week >= 5).")

    missing = [column for column in M2_FEATURES + [TARGET_COLUMN] if column not in subset.columns]
    if missing:
        raise ValueError(f"M2 training data is missing required columns: {', '.join(missing)}")

    x = subset[M2_FEATURES].copy()
    y = subset[TARGET_COLUMN].astype(float)

    categorical_columns = ["flood_hazard_zone_tier", "platform", "season_flag"]
    for column in categorical_columns:
        x[column] = x[column].astype("category")

    x_train, x_valid, y_train, y_valid = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
    )

    model = lgb.LGBMRegressor(
        objective="tweedie",
        tweedie_variance_power=1.5,
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
    )
    model.fit(
        x_train,
        y_train,
        eval_set=[(x_valid, y_valid)],
        eval_metric="rmse",
        categorical_feature=categorical_columns,
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
    )

    predictions = model.predict(x_valid)
    rmse = float(np.sqrt(mean_squared_error(y_valid, predictions)))
    negative_predictions = int((predictions < 0).sum())
    if negative_predictions > 0:
        raise ValueError(f"M2 produced negative predictions: count={negative_predictions}")

    explainer = shap.TreeExplainer(model)
    sample_row = x_valid.head(1)
    if sample_row.empty:
        sample_row = x_train.head(1)
    _ = explainer.shap_values(sample_row)

    model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    shap_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    feature_list_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_artifact_path)
    joblib.dump(explainer, shap_artifact_path)
    joblib.dump(M2_FEATURES, feature_list_artifact_path)

    logger.info(
        "M2 LightGBM trained. rows=%d, train=%d, valid=%d, rmse=%.4f, model=%s",
        len(subset),
        len(x_train),
        len(x_valid),
        rmse,
        model_artifact_path,
    )
    print(f"M2 RMSE: {rmse:.4f}")

    return {
        "rmse": rmse,
        "train_rows": int(len(x_train)),
        "valid_rows": int(len(x_valid)),
        "negative_predictions": negative_predictions,
        "model_artifact_path": str(model_artifact_path),
        "shap_artifact_path": str(shap_artifact_path),
        "feature_list_artifact_path": str(feature_list_artifact_path),
    }


def run_m1_m2_training_pipeline(
    input_csv_path: Path = DEFAULT_INPUT_CSV_PATH,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
) -> dict[str, Any]:
    """Run end-to-end training for M1 and M2 and return summary metrics."""
    frame = load_training_data(input_csv_path)

    glm_path = artifact_dir / "glm_m1.joblib"
    lgbm_path = artifact_dir / "lgbm_m2.joblib"
    shap_path = artifact_dir / "shap_explainer_m2.joblib"
    feature_path = artifact_dir / "lgbm_m2_feature_list.joblib"

    m1_result = train_m1_glm_cold_start(frame, glm_path)
    m2_result = train_m2_lgbm_weekly(
        frame,
        model_artifact_path=lgbm_path,
        shap_artifact_path=shap_path,
        feature_list_artifact_path=feature_path,
    )

    summary = {
        "input_csv_path": str(input_csv_path),
        "artifact_dir": str(artifact_dir),
        "m1": m1_result,
        "m2": m2_result,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Giggle M1 and M2 premium models.")
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DEFAULT_INPUT_CSV_PATH,
        help="Path to synthetic premium training CSV.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help="Directory where model artifacts will be saved.",
    )
    args = parser.parse_args()

    summary = run_m1_m2_training_pipeline(
        input_csv_path=args.input_csv,
        artifact_dir=args.artifact_dir,
    )

    print("Training completed:")
    print(f"- input_csv_path: {summary['input_csv_path']}")
    print(f"- artifact_dir: {summary['artifact_dir']}")
    print(f"- m1_rmse: {summary['m1']['rmse']:.4f}")
    print(f"- m2_rmse: {summary['m2']['rmse']:.4f}")
    print(f"- m1_artifact: {summary['m1']['artifact_path']}")
    print(f"- m2_artifact: {summary['m2']['model_artifact_path']}")
    print(f"- m2_shap_artifact: {summary['m2']['shap_artifact_path']}")
    print(f"- m2_feature_list_artifact: {summary['m2']['feature_list_artifact_path']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
