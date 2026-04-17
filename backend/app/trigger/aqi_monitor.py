"""AQI monitoring utilities using CPCB NAMP data.gov.in feed."""

from __future__ import annotations

import logging
import math
from typing import Any

import httpx

from app.core.config import settings

LOGGER = logging.getLogger(__name__)

CPCB_RESOURCE_URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
REQUEST_TIMEOUT_SECONDS = 15.0
BUFFER_SIZE = 4
AQI_TRIGGER_THRESHOLD = 300.0

# zone_cluster_id -> last 4 readings
_aqi_buffer: dict[int, list[float]] = {}


def _to_float(value: Any) -> float | None:
    """Convert value to float if possible and finite; otherwise return None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric_value = float(value)
        return numeric_value if math.isfinite(numeric_value) else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            numeric_value = float(text)
        except ValueError:
            return None
        return numeric_value if math.isfinite(numeric_value) else None
    return None


async def fetch_aqi_for_zone(zone_cluster_id: int, station_lat: float, station_lon: float) -> float | None:
    """Fetch nearest station AQI for the given zone centroid.

    Returns None for any failure and logs diagnostic context.
    """
    if not isinstance(zone_cluster_id, int):
        LOGGER.warning("AQI fetch skipped: zone_cluster_id must be int, got %s", type(zone_cluster_id))
        return None

    target_lat = _to_float(station_lat)
    target_lon = _to_float(station_lon)
    if target_lat is None or target_lon is None:
        LOGGER.warning(
            "AQI fetch skipped for zone %s: invalid station coordinates lat=%s lon=%s",
            zone_cluster_id,
            station_lat,
            station_lon,
        )
        return None

    params = {
        "api-key": settings.data_gov_in_api_key,
        "format": "json",
        "limit": 100,
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(CPCB_RESOURCE_URL, params=params)
            response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        LOGGER.warning("AQI fetch failed for zone %s: %s", zone_cluster_id, exc)
        return None

    records = payload.get("records")
    if not isinstance(records, list) or not records:
        LOGGER.warning("AQI fetch returned no records for zone %s", zone_cluster_id)
        return None

    closest_distance = float("inf")
    closest_aqi: float | None = None

    for record in records:
        if not isinstance(record, dict):
            continue

        rec_lat = _to_float(record.get("latitude"))
        rec_lon = _to_float(record.get("longitude"))
        rec_aqi = _to_float(record.get("aqi"))

        if rec_lat is None or rec_lon is None or rec_aqi is None:
            continue

        distance = math.sqrt((rec_lat - target_lat) ** 2 + (rec_lon - target_lon) ** 2)
        if distance < closest_distance:
            closest_distance = distance
            closest_aqi = rec_aqi

    if closest_aqi is None:
        LOGGER.warning("AQI fetch found no valid station rows for zone %s", zone_cluster_id)
        return None

    return float(closest_aqi)


def update_aqi_buffer(zone_cluster_id: int, aqi_reading: float) -> None:
    """Append AQI reading and retain only the most recent 4 values."""
    if not isinstance(zone_cluster_id, int):
        raise TypeError("zone_cluster_id must be int")

    reading_value = _to_float(aqi_reading)
    if reading_value is None:
        raise ValueError("aqi_reading must be a finite numeric value")

    readings = _aqi_buffer.setdefault(zone_cluster_id, [])
    readings.append(reading_value)
    if len(readings) > BUFFER_SIZE:
        del readings[:-BUFFER_SIZE]


def check_aqi_trigger(zone_cluster_id: int) -> dict[str, Any]:
    """Check whether the last 4 hourly AQI readings all exceed 300."""
    if not isinstance(zone_cluster_id, int):
        raise TypeError("zone_cluster_id must be int")

    readings = _aqi_buffer.get(zone_cluster_id, [])
    consecutive_readings = len(readings)
    latest_aqi = readings[-1] if readings else None

    triggered = consecutive_readings == BUFFER_SIZE and all(
        reading > AQI_TRIGGER_THRESHOLD for reading in readings
    )

    return {
        "triggered": triggered,
        "consecutive_readings": consecutive_readings,
        "latest_aqi": latest_aqi,
    }


async def poll_aqi_all_zones(zone_clusters: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Poll AQI for all zones and return trigger status per zone.

    Failures in one zone do not stop processing of other zones.
    """
    if not isinstance(zone_clusters, list):
        raise TypeError("zone_clusters must be a list")

    results: dict[int, dict[str, Any]] = {}

    for zone in zone_clusters:
        if not isinstance(zone, dict):
            LOGGER.warning("Skipping invalid zone payload: expected dict, got %s", type(zone))
            continue

        zone_id = zone.get("id")
        lat = zone.get("centroid_lat")
        lon = zone.get("centroid_lon")

        if not isinstance(zone_id, int):
            LOGGER.warning("Skipping zone payload with non-int id: %s", zone_id)
            continue

        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            LOGGER.warning(
                "Skipping AQI fetch for zone %s due to invalid centroid coordinates: lat=%s lon=%s",
                zone_id,
                lat,
                lon,
            )
            results[zone_id] = check_aqi_trigger(zone_id)
            continue

        try:
            aqi_reading = await fetch_aqi_for_zone(zone_id, float(lat), float(lon))
            if aqi_reading is not None:
                update_aqi_buffer(zone_id, aqi_reading)
            results[zone_id] = check_aqi_trigger(zone_id)
        except Exception as exc:  # Defensive isolation for per-zone failure.
            LOGGER.warning("AQI poll failed for zone %s: %s", zone_id, exc)
            results[zone_id] = check_aqi_trigger(zone_id)

    return results
