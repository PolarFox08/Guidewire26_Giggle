"""Open-Meteo client utilities for 3-point spatial oversampling."""

from __future__ import annotations

import logging
import math
from typing import Any

import httpx

from app.core.config import settings

LOGGER = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0
REQUEST_TIMEOUT_SECONDS = 15.0
NNE_BEARING_DEGREES = 22.5
SSW_BEARING_DEGREES = 202.5
OFFSET_DISTANCE_KM = 3.0


def get_bearing_offset(
    lat: float,
    lon: float,
    bearing_degrees: float,
    distance_km: float,
) -> tuple[float, float]:
    """Compute destination point from origin, bearing, and distance on a sphere."""
    for field_name, value in {
        "lat": lat,
        "lon": lon,
        "bearing_degrees": bearing_degrees,
        "distance_km": distance_km,
    }.items():
        if not isinstance(value, (int, float)):
            raise TypeError(f"{field_name} must be numeric")
        if not math.isfinite(float(value)):
            raise ValueError(f"{field_name} must be finite")

    lat_value = float(lat)
    lon_value = float(lon)
    bearing = math.radians(float(bearing_degrees))
    distance = float(distance_km)

    if not -90.0 <= lat_value <= 90.0:
        raise ValueError("lat must be between -90 and 90")
    if not -180.0 <= lon_value <= 180.0:
        raise ValueError("lon must be between -180 and 180")
    if distance < 0:
        raise ValueError("distance_km cannot be negative")

    angular_distance = distance / EARTH_RADIUS_KM

    lat_rad = math.radians(lat_value)
    lon_rad = math.radians(lon_value)

    new_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(angular_distance)
        + math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing)
    )

    new_lon_rad = lon_rad + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat_rad),
        math.cos(angular_distance) - math.sin(lat_rad) * math.sin(new_lat_rad),
    )

    normalized_lon_rad = (new_lon_rad + math.pi) % (2 * math.pi) - math.pi

    return math.degrees(new_lat_rad), math.degrees(normalized_lon_rad)


async def get_current_precipitation(lat: float, lon: float) -> float:
    """Fetch the latest 24h precipitation sum (mm) for a single coordinate."""
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        raise TypeError("lat and lon must be numeric")

    lat_value = float(lat)
    lon_value = float(lon)
    if not math.isfinite(lat_value) or not math.isfinite(lon_value):
        raise ValueError("lat and lon must be finite")

    if not -90.0 <= lat_value <= 90.0:
        raise ValueError("lat must be between -90 and 90")
    if not -180.0 <= lon_value <= 180.0:
        raise ValueError("lon must be between -180 and 180")

    url = f"{settings.open_meteo_base_url.rstrip('/')}/forecast"
    params = {
        "latitude": lat_value,
        "longitude": lon_value,
        "hourly": "precipitation,temperature_2m",
        "timezone": "Asia/Kolkata",
        "forecast_days": 1,
        "past_days": 1,
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()

    payload = response.json()
    hourly_data: dict[str, Any] | None = payload.get("hourly")
    if not isinstance(hourly_data, dict):
        raise ValueError("Open-Meteo response missing hourly data")

    precipitation_values = hourly_data.get("precipitation")
    if not isinstance(precipitation_values, list) or len(precipitation_values) < 24:
        raise ValueError("Open-Meteo response missing 24 hourly precipitation values")

    numeric_values: list[float] = []
    for idx, value in enumerate(precipitation_values[-24:]):
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"Invalid precipitation value at index {idx}")
        numeric_values.append(float(value))

    return float(sum(numeric_values))


async def query_three_points(zone_centroid_lat: float, zone_centroid_lon: float) -> dict[str, Any]:
    """Query centroid + 3km NNE + 3km SSW and return the maximum precipitation."""
    centroid_point = (float(zone_centroid_lat), float(zone_centroid_lon))
    nne_point = get_bearing_offset(
        zone_centroid_lat,
        zone_centroid_lon,
        NNE_BEARING_DEGREES,
        OFFSET_DISTANCE_KM,
    )
    ssw_point = get_bearing_offset(
        zone_centroid_lat,
        zone_centroid_lon,
        SSW_BEARING_DEGREES,
        OFFSET_DISTANCE_KM,
    )

    points = [centroid_point, nne_point, ssw_point]

    successful_values: list[float] = []
    point_results: list[dict[str, Any]] = []

    for index, (lat, lon) in enumerate(points):
        try:
            precipitation = await get_current_precipitation(lat, lon)
            successful_values.append(precipitation)
            point_results.append(
                {
                    "point_index": index,
                    "latitude": lat,
                    "longitude": lon,
                    "success": True,
                    "precipitation_24h_mm": precipitation,
                }
            )
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            LOGGER.warning(
                "Open-Meteo point query failed at index %s (%s, %s): %s",
                index,
                lat,
                lon,
                exc,
            )
            point_results.append(
                {
                    "point_index": index,
                    "latitude": lat,
                    "longitude": lon,
                    "success": False,
                    "error": str(exc),
                }
            )

    if not successful_values:
        raise RuntimeError("All Open-Meteo point queries failed")

    return {
        "max_precipitation_24h_mm": max(successful_values),
        "successful_points": len(successful_values),
        "degraded": len(successful_values) < 2,
        "points": point_results,
    }
