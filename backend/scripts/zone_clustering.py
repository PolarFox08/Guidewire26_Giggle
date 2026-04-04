"""M5 zone clustering pipeline.

Implements Section 3.3 from AGENT_CONTEXT:
- Load pincode centroids and flood hazard polygons
- Spatially assign flood_hazard_tier
- Query Open-Meteo archive for 50 sampled pincodes
- Cluster with KMeans(n_clusters=20) on [flood_tier_numeric, avg_heavy_rain_days_yr]
- Upsert zone_clusters in Supabase
- Save kmeans_m5.joblib artifact for onboarding use
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
import argparse
from pathlib import Path
from typing import Any
import random
import time

import joblib
import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

LOGGER = logging.getLogger(__name__)

CHENNAI_LAT_MIN = 12.7
CHENNAI_LAT_MAX = 13.3
CHENNAI_LON_MIN = 80.0
CHENNAI_LON_MAX = 80.4

N_CLUSTERS = 20
SAMPLE_SIZE = 50
HEAVY_RAIN_THRESHOLD_MM = 64.5
START_DATE = "1944-01-01"
END_DATE = "2023-12-31"
YEARS_IN_WINDOW = 80.0

ARCHIVE_TIMEOUT_SECONDS = 30
ARCHIVE_RETRIES = 3
ARCHIVE_MIN_REQUEST_GAP_SECONDS = 2.0


_LAST_ARCHIVE_REQUEST_TS = 0.0


@dataclass(frozen=True)
class Paths:
    backend_root: Path
    data_dir: Path
    pincode_csv: Path
    hazard_geojson: Path
    hazard_kml: Path
    rain_cache_csv: Path
    model_output: Path


def _resolve_paths() -> Paths:
    backend_root = Path(__file__).resolve().parents[1]
    data_dir = backend_root / "data"
    return Paths(
        backend_root=backend_root,
        data_dir=data_dir,
        pincode_csv=data_dir / "chennai_pincodes.csv",
        hazard_geojson=data_dir / "chennai_flood_hazard.geojson",
        hazard_kml=data_dir / "chennai_flood_hazard.kml",
        rain_cache_csv=data_dir / "rain_history_cache.csv",
        model_output=backend_root / "app" / "ml" / "artifacts" / "kmeans_m5.joblib",
    )


def _load_database_url(backend_root: Path) -> str:
    load_dotenv(backend_root / ".env", override=False)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is missing. Set it in backend/.env.")
    return database_url


def _get_existing_zone_cluster_count(database_url: str) -> int:
    query = text("SELECT COUNT(*) AS count FROM zone_clusters")
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        result = conn.execute(query).mappings().one()
    return int(result["count"])


def _resolve_archive_base_url() -> str:
    base = os.getenv("OPEN_METEO_ARCHIVE_URL", "https://archive-api.open-meteo.com/v1")
    base = base.rstrip("/")
    if not base.endswith("/archive"):
        base = f"{base}/archive"
    return base


def _resolve_hazard_file(paths: Paths) -> Path:
    if paths.hazard_geojson.exists():
        return paths.hazard_geojson
    if paths.hazard_kml.exists():
        LOGGER.warning("GeoJSON not found, falling back to KML: %s", paths.hazard_kml)
        return paths.hazard_kml
    raise FileNotFoundError(
        "Flood hazard file missing. Expected one of: "
        f"{paths.hazard_geojson} or {paths.hazard_kml}"
    )


def _normalize_columns(frame: Any) -> Any:
    frame.columns = [str(col).strip().lower().replace(" ", "_") for col in frame.columns]
    return frame


def _find_category_column(zones: Any) -> str:
    normalized = {
        str(col).strip().lower().replace(" ", "_"): str(col)
        for col in zones.columns
    }
    for candidate in ("category", "flood_hazard_tier", "flood_tier", "tier"):
        if candidate in normalized:
            return normalized[candidate]
    raise ValueError(
        "Hazard category column not found. Expected one of: "
        "category, flood_hazard_tier, flood_tier, tier"
    )


def _normalize_tier(value: Any) -> str:
    text_value = str(value).strip().lower()
    if "high" in text_value:
        return "high"
    if "medium" in text_value or "moderate" in text_value:
        return "medium"
    return "low"


def _tier_to_numeric(tier: str) -> int:
    mapping = {"low": 1, "medium": 2, "high": 3}
    return mapping.get(tier, 1)


def _zone_rates_for_tier(flood_tier_numeric: int) -> tuple[float, float, float]:
    # Derived from flood tier with increasing risk in ₹15-40 range.
    if flood_tier_numeric <= 1:
        return (15.0, 20.0, 25.0)
    if flood_tier_numeric == 2:
        return (20.0, 27.5, 35.0)
    return (25.0, 32.5, 40.0)


def load_and_prepare_points(paths: Paths) -> Any:
    import geopandas as gpd
    import pandas as pd

    if not paths.pincode_csv.exists():
        raise FileNotFoundError(f"Missing pincode CSV: {paths.pincode_csv}")

    points = pd.read_csv(paths.pincode_csv)
    points = _normalize_columns(points)

    required_columns = {"pincode", "latitude", "longitude"}
    missing_columns = required_columns.difference(set(points.columns))
    if missing_columns:
        raise ValueError(
            "chennai_pincodes.csv missing required columns: "
            f"{sorted(missing_columns)}"
        )

    points = points[["pincode", "latitude", "longitude"]].copy()
    points["pincode"] = pd.to_numeric(points["pincode"], errors="coerce")
    points["latitude"] = pd.to_numeric(points["latitude"], errors="coerce")
    points["longitude"] = pd.to_numeric(points["longitude"], errors="coerce")
    points = points.dropna(subset=["pincode", "latitude", "longitude"])

    points = points[
        points["latitude"].between(CHENNAI_LAT_MIN, CHENNAI_LAT_MAX)
        & points["longitude"].between(CHENNAI_LON_MIN, CHENNAI_LON_MAX)
    ]
    points = points.drop_duplicates(subset=["pincode"]).reset_index(drop=True)

    if points.empty:
        raise ValueError("No rows left after Chennai bounding filter and dedup.")

    points_gdf = gpd.GeoDataFrame(
        points,
        geometry=gpd.points_from_xy(points["longitude"], points["latitude"]),
        crs="EPSG:4326",
    )

    hazard_path = _resolve_hazard_file(paths)
    zones_gdf = gpd.read_file(hazard_path)
    if zones_gdf.empty:
        raise ValueError("Flood hazard layer is empty.")

    if zones_gdf.crs is None:
        zones_gdf = zones_gdf.set_crs("EPSG:4326")
    elif zones_gdf.crs.to_string() != "EPSG:4326":
        zones_gdf = zones_gdf.to_crs("EPSG:4326")

    category_col = _find_category_column(zones_gdf)
    zone_frame = zones_gdf[[category_col, "geometry"]].copy()
    zone_frame["flood_hazard_tier"] = zone_frame[category_col].apply(_normalize_tier)

    joined = gpd.sjoin(
        points_gdf,
        zone_frame[["flood_hazard_tier", "geometry"]],
        how="left",
        predicate="within",
    )
    joined["flood_hazard_tier"] = joined["flood_hazard_tier"].fillna("low")
    if "index_right" in joined.columns:
        joined = joined.drop(columns=["index_right"])

    joined["flood_tier_numeric"] = joined["flood_hazard_tier"].apply(_tier_to_numeric)
    return joined


def _fetch_avg_heavy_rain_days(lat: float, lon: float, archive_url: str) -> float:
    global _LAST_ARCHIVE_REQUEST_TS

    params = {
        "latitude": round(float(lat), 6),
        "longitude": round(float(lon), 6),
        "daily": "precipitation_sum",
        "start_date": START_DATE,
        "end_date": END_DATE,
        "timezone": "Asia/Kolkata",
    }

    last_error: Exception | None = None
    for attempt in range(1, ARCHIVE_RETRIES + 1):
        try:
            elapsed = time.time() - _LAST_ARCHIVE_REQUEST_TS
            if elapsed < ARCHIVE_MIN_REQUEST_GAP_SECONDS:
                time.sleep(ARCHIVE_MIN_REQUEST_GAP_SECONDS - elapsed)

            response = requests.get(archive_url, params=params, timeout=ARCHIVE_TIMEOUT_SECONDS)
            _LAST_ARCHIVE_REQUEST_TS = time.time()

            if response.status_code == 429:
                retry_after_header = response.headers.get("Retry-After")
                if retry_after_header and retry_after_header.isdigit():
                    wait_seconds = max(int(retry_after_header), 1)
                else:
                    # Exponential backoff + jitter when Retry-After isn't available.
                    wait_seconds = int((2 ** (attempt - 1)) + random.uniform(0.2, 1.0))

                LOGGER.warning(
                    "Open-Meteo 429 for (%.6f, %.6f). Waiting %ss before retry %s/%s.",
                    lat,
                    lon,
                    wait_seconds,
                    attempt,
                    ARCHIVE_RETRIES,
                )
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            payload = response.json()
            precipitation_values = payload.get("daily", {}).get("precipitation_sum", [])
            if not precipitation_values:
                raise ValueError("No precipitation_sum values in archive response.")

            heavy_days = sum(
                1 for value in precipitation_values
                if value is not None and float(value) >= HEAVY_RAIN_THRESHOLD_MM
            )
            return heavy_days / YEARS_IN_WINDOW
        except Exception as exc:  # pragma: no cover - network/runtime variability
            last_error = exc
            LOGGER.warning(
                "Open-Meteo request failed for (%.6f, %.6f), attempt %s/%s: %s",
                lat,
                lon,
                attempt,
                ARCHIVE_RETRIES,
                exc,
            )
            if attempt < ARCHIVE_RETRIES:
                wait_seconds = int((2 ** (attempt - 1)) + random.uniform(0.2, 1.0))
                time.sleep(wait_seconds)

    raise RuntimeError(
        f"Failed to fetch archive data for ({lat}, {lon}) after {ARCHIVE_RETRIES} attempts"
    ) from last_error


def attach_sampled_rain_history(joined: Any, sample_size: int = SAMPLE_SIZE) -> Any:
    import pandas as pd

    sampled = joined.sample(n=min(sample_size, len(joined)), random_state=42).copy()
    archive_url = _resolve_archive_base_url()

    cache_path = _resolve_paths().rain_cache_csv
    cache_lookup: dict[tuple[float, float], float] = {}

    if cache_path.exists():
        cached = pd.read_csv(cache_path)
        if {"lat", "lon", "avg_heavy_rain_days_yr"}.issubset(set(cached.columns)):
            for _, row in cached.iterrows():
                lat_key = round(float(row["lat"]), 6)
                lon_key = round(float(row["lon"]), 6)
                cache_lookup[(lat_key, lon_key)] = float(row["avg_heavy_rain_days_yr"])

    cache_updated = False

    def resolve_rain_history(row: Any) -> float:
        nonlocal cache_updated

        lat_key = round(float(row["latitude"]), 6)
        lon_key = round(float(row["longitude"]), 6)
        key = (lat_key, lon_key)

        if key in cache_lookup:
            return cache_lookup[key]

        value = _fetch_avg_heavy_rain_days(lat_key, lon_key, archive_url)
        cache_lookup[key] = value
        cache_updated = True
        return value

    sampled["avg_heavy_rain_days_yr"] = sampled.apply(resolve_rain_history, axis=1)

    if cache_updated:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_rows = [
            {"lat": key[0], "lon": key[1], "avg_heavy_rain_days_yr": value}
            for key, value in sorted(cache_lookup.items())
        ]
        pd.DataFrame(cache_rows).to_csv(cache_path, index=False)
        LOGGER.info("Updated rain-history cache: %s", cache_path)

    if sampled.shape[0] < N_CLUSTERS:
        raise ValueError(
            f"Sample size must be at least {N_CLUSTERS} rows after filtering; got {sampled.shape[0]}"
        )

    return sampled


def fit_kmeans(sampled: Any) -> tuple[Any, Any, Any]:
    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    feature_columns = ["flood_tier_numeric", "avg_heavy_rain_days_yr"]
    feature_matrix = sampled[feature_columns].astype(float).copy()

    # Avoid degenerate clustering when many points share identical feature values.
    # Jitter is tiny and deterministic, used only for fitting stability.
    unique_feature_rows = int(feature_matrix.drop_duplicates().shape[0])
    if unique_feature_rows < N_CLUSTERS:
        LOGGER.warning(
            "Only %s unique feature rows for %s clusters; applying tiny deterministic jitter.",
            unique_feature_rows,
            N_CLUSTERS,
        )
        feature_matrix["avg_heavy_rain_days_yr"] = (
            feature_matrix["avg_heavy_rain_days_yr"]
            + np.linspace(0.0, 1e-6, len(feature_matrix), dtype=float)
        )

    scaler = StandardScaler()
    scaled = scaler.fit_transform(feature_matrix)

    model = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    sampled = sampled.copy()
    sampled["zone_cluster_id"] = model.fit_predict(scaled) + 1

    return sampled, scaler, model


def build_zone_cluster_rows(clustered: Any) -> Any:
    import pandas as pd

    frame = clustered.copy()
    frame["zone_cluster_id"] = pd.Categorical(
        frame["zone_cluster_id"],
        categories=list(range(1, N_CLUSTERS + 1)),
        ordered=True,
    )

    grouped = (
        frame.groupby("zone_cluster_id", as_index=False, observed=False)
        .agg(
            centroid_lat=("latitude", "mean"),
            centroid_lon=("longitude", "mean"),
            flood_tier_numeric=("flood_tier_numeric", "mean"),
            avg_heavy_rain_days_yr=("avg_heavy_rain_days_yr", "mean"),
        )
        .sort_values("zone_cluster_id")
        .reset_index(drop=True)
    )

    if grouped.shape[0] != N_CLUSTERS:
        raise ValueError(f"Expected {N_CLUSTERS} output clusters, got {grouped.shape[0]}.")

    # Fill sparse/empty-cluster aggregates with global means to keep full 20-row output.
    if grouped[["centroid_lat", "centroid_lon", "flood_tier_numeric", "avg_heavy_rain_days_yr"]].isna().any().any():
        LOGGER.warning("One or more clusters had no assigned points; filling from global means.")
        grouped["centroid_lat"] = grouped["centroid_lat"].fillna(frame["latitude"].mean())
        grouped["centroid_lon"] = grouped["centroid_lon"].fillna(frame["longitude"].mean())
        grouped["flood_tier_numeric"] = grouped["flood_tier_numeric"].fillna(frame["flood_tier_numeric"].mean())
        grouped["avg_heavy_rain_days_yr"] = grouped["avg_heavy_rain_days_yr"].fillna(frame["avg_heavy_rain_days_yr"].mean())

    grouped["id"] = grouped["zone_cluster_id"].astype(int)
    grouped["flood_tier_numeric"] = grouped["flood_tier_numeric"].round().clip(1, 3).astype(int)

    rates = grouped["flood_tier_numeric"].apply(_zone_rates_for_tier)
    grouped["zone_rate_min"] = rates.apply(lambda value: value[0])
    grouped["zone_rate_mid"] = rates.apply(lambda value: value[1])
    grouped["zone_rate_max"] = rates.apply(lambda value: value[2])

    grouped["centroid_lat"] = grouped["centroid_lat"].round(7)
    grouped["centroid_lon"] = grouped["centroid_lon"].round(7)
    grouped["avg_heavy_rain_days_yr"] = grouped["avg_heavy_rain_days_yr"].round(2)

    return pd.DataFrame(
        grouped[
            [
                "id",
                "centroid_lat",
                "centroid_lon",
                "flood_tier_numeric",
                "avg_heavy_rain_days_yr",
                "zone_rate_min",
                "zone_rate_mid",
                "zone_rate_max",
            ]
        ]
    )


def upsert_zone_clusters(zone_rows: Any, database_url: str) -> int:
    required_columns = [
        "id",
        "centroid_lat",
        "centroid_lon",
        "flood_tier_numeric",
        "avg_heavy_rain_days_yr",
        "zone_rate_min",
        "zone_rate_mid",
        "zone_rate_max",
    ]
    missing_columns = set(required_columns).difference(set(zone_rows.columns))
    if missing_columns:
        raise ValueError(f"zone_rows missing required columns: {sorted(missing_columns)}")

    payload = zone_rows[required_columns].to_dict(orient="records")

    upsert_sql = text(
        """
        INSERT INTO zone_clusters (
            id,
            centroid_lat,
            centroid_lon,
            flood_tier_numeric,
            avg_heavy_rain_days_yr,
            zone_rate_min,
            zone_rate_mid,
            zone_rate_max
        ) VALUES (
            :id,
            :centroid_lat,
            :centroid_lon,
            :flood_tier_numeric,
            :avg_heavy_rain_days_yr,
            :zone_rate_min,
            :zone_rate_mid,
            :zone_rate_max
        )
        ON CONFLICT (id) DO UPDATE SET
            centroid_lat = EXCLUDED.centroid_lat,
            centroid_lon = EXCLUDED.centroid_lon,
            flood_tier_numeric = EXCLUDED.flood_tier_numeric,
            avg_heavy_rain_days_yr = EXCLUDED.avg_heavy_rain_days_yr,
            zone_rate_min = EXCLUDED.zone_rate_min,
            zone_rate_mid = EXCLUDED.zone_rate_mid,
            zone_rate_max = EXCLUDED.zone_rate_max
        """
    )

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(upsert_sql, payload)

    return len(payload)


def save_kmeans_artifact(output_path: Path, scaler: Any, model: Any) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "scaler": scaler,
        "kmeans": model,
        "feature_columns": ["flood_tier_numeric", "avg_heavy_rain_days_yr"],
        "n_clusters": N_CLUSTERS,
        "random_state": 42,
    }
    joblib.dump(artifact, output_path)


def _tier_distribution(zone_rows: Any) -> dict[str, int]:
    numeric_to_tier = {1: "low", 2: "medium", 3: "high"}
    counts = {"low": 0, "medium": 0, "high": 0}
    for tier_num in zone_rows["flood_tier_numeric"].tolist():
        label = numeric_to_tier.get(int(tier_num), "low")
        counts[label] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and upsert Giggle M5 zone clusters.")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=SAMPLE_SIZE,
        help="Number of pincode centroids to sample for Open-Meteo archive calls.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild and upsert zone_clusters even if the table already has rows.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    paths = _resolve_paths()
    database_url = _load_database_url(paths.backend_root)

    existing_count = _get_existing_zone_cluster_count(database_url)
    if existing_count >= N_CLUSTERS and not args.force:
        LOGGER.info(
            "zone_clusters already has %s rows. Skipping rebuild. Use --force to overwrite.",
            existing_count,
        )
        print(f"zone_clusters already populated with {existing_count} rows. Use --force to rebuild.")
        return

    LOGGER.info("Loading Chennai pincode points and flood hazard zones...")
    joined = load_and_prepare_points(paths)

    sample_size = min(args.sample_size, len(joined))
    LOGGER.info("Sampling %s points and fetching Open-Meteo archive history...", sample_size)
    sampled = attach_sampled_rain_history(joined, sample_size=sample_size)

    LOGGER.info("Training KMeans model for %s clusters...", N_CLUSTERS)
    clustered, scaler, model = fit_kmeans(sampled)

    zone_rows = build_zone_cluster_rows(clustered)

    LOGGER.info("Upserting zone clusters into Supabase...")
    upserted = upsert_zone_clusters(zone_rows, database_url)

    LOGGER.info("Saving kmeans artifact to %s", paths.model_output)
    save_kmeans_artifact(paths.model_output, scaler, model)

    print("\nZone clustering summary")
    print("-" * 30)
    print(f"Zones created: {upserted}")
    print(f"Tier distribution: {_tier_distribution(zone_rows)}")
    print(f"Artifact saved: {paths.model_output}")


if __name__ == "__main__":
    main()
