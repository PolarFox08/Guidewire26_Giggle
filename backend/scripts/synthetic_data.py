"""
Synthetic training data generation for M1 and M2 premium models.
Section 3.5: Generates 10,000 synthetic worker-week records with features and labels.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from .loss_ratio_simulation import (
        WEEKLY_PREMIUM_CEILING,
        WEEKLY_PREMIUM_FLOOR,
        compute_weekly_premium_target,
    )
except ImportError:  # pragma: no cover - allows direct script execution
    from loss_ratio_simulation import (
        WEEKLY_PREMIUM_CEILING,
        WEEKLY_PREMIUM_FLOOR,
        compute_weekly_premium_target,
    )

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "synthetic_training_data.csv"
DEFAULT_NUM_ROWS = 10_000
RANDOM_SEED = 42

FLOOD_TIER_TO_NUMERIC = {"low": 1, "medium": 2, "high": 3}

M1_FEATURE_COLUMNS = ["flood_hazard_zone_tier", "season_flag", "platform"]
M2_FEATURE_COLUMNS = [
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


def _weighted_choice(rng: np.random.Generator, values: list[Any], weights: list[float]) -> Any:
    probabilities = np.asarray(weights, dtype=float)
    probabilities = probabilities / probabilities.sum()
    return rng.choice(values, p=probabilities)


def _sample_zone_cluster_id(rng: np.random.Generator) -> int:
    cluster_ids = list(range(1, 21))
    weights = [1.35 if cluster_id <= 5 else 1.0 for cluster_id in cluster_ids]
    return int(_weighted_choice(rng, cluster_ids, weights))


def _sample_flood_tier(rng: np.random.Generator) -> str:
    return str(_weighted_choice(rng, ["low", "medium", "high"], [0.30, 0.40, 0.30]))


def _sample_season(rng: np.random.Generator) -> str:
    return str(_weighted_choice(rng, ["NE_monsoon", "SW_monsoon", "heat", "dry_season"], [0.35, 0.25, 0.20, 0.20]))


def _sample_platform(rng: np.random.Generator) -> str:
    return str(_weighted_choice(rng, ["zomato", "swiggy"], [0.65, 0.35]))


def _build_row(rng: np.random.Generator) -> dict[str, Any]:
    flood_hazard_zone_tier = _sample_flood_tier(rng)
    zone_cluster_id = _sample_zone_cluster_id(rng)
    platform = _sample_platform(rng)
    season_flag = _sample_season(rng)
    enrollment_week = int(rng.integers(1, 53))

    flood_tier_numeric = FLOOD_TIER_TO_NUMERIC[flood_hazard_zone_tier]
    delivery_baseline_30d = float(np.clip(rng.normal(280.0, 60.0), 90.0, 520.0))
    zone_rate_mid = float(np.clip(rng.normal(27.5 + (flood_tier_numeric - 2) * 2.5, 2.0), 15.0, 40.0))
    income_baseline_weekly = float(np.clip(delivery_baseline_30d * zone_rate_mid / 30.0 * 7.0, 350.0, 6000.0))
    open_meteo_7d_precip_probability = float(np.clip(rng.beta(2.5, 3.0), 0.0, 1.0))
    activity_consistency_score = float(np.clip(rng.normal(0.72, 0.14), 0.0, 1.0))
    tenure_discount_factor = float(np.clip(1.0 - (enrollment_week / 120.0) - rng.uniform(0.0, 0.03), 0.85, 1.0))
    historical_claim_rate_zone = float(np.clip({1: 0.08, 2: 0.12, 3: 0.18}[flood_tier_numeric] + rng.normal(0.0, 0.03), 0.0, 1.0))

    weekly_premium = compute_weekly_premium_target(
        avg_heavy_rain_days_yr=historical_claim_rate_zone * 365.0,
        flood_tier_numeric=flood_tier_numeric,
        season=season_flag,
    )
    weekly_premium = float(np.clip(weekly_premium * float(rng.lognormal(mean=0.0, sigma=0.05)), WEEKLY_PREMIUM_FLOOR, WEEKLY_PREMIUM_CEILING))

    return {
        "flood_hazard_zone_tier": flood_hazard_zone_tier,
        "zone_cluster_id": zone_cluster_id,
        "platform": platform,
        "delivery_baseline_30d": round(delivery_baseline_30d, 2),
        "income_baseline_weekly": round(income_baseline_weekly, 2),
        "enrollment_week": enrollment_week,
        "season_flag": season_flag,
        "open_meteo_7d_precip_probability": round(open_meteo_7d_precip_probability, 4),
        "activity_consistency_score": round(activity_consistency_score, 4),
        "tenure_discount_factor": round(tenure_discount_factor, 4),
        "historical_claim_rate_zone": round(historical_claim_rate_zone, 4),
        "weekly_premium": round(weekly_premium, 2),
    }


def generate_synthetic_training_data(num_rows: int = DEFAULT_NUM_ROWS, seed: int = RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(_build_row(rng) for _ in range(num_rows))
    frame = frame[
        [
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
            "weekly_premium",
        ]
    ]
    frame["zone_cluster_id"] = frame["zone_cluster_id"].astype(int)
    frame["enrollment_week"] = frame["enrollment_week"].astype(int)
    return frame


def save_synthetic_training_data(
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    num_rows: int = DEFAULT_NUM_ROWS,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    frame = generate_synthetic_training_data(num_rows=num_rows, seed=seed)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_file, index=False)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic premium training data.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Output CSV path")
    parser.add_argument("--rows", type=int, default=DEFAULT_NUM_ROWS, help="Number of rows to generate")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Random seed")
    args = parser.parse_args()

    frame = save_synthetic_training_data(args.output, num_rows=args.rows, seed=args.seed)
    print(frame.shape)
    print(frame.head(5))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
