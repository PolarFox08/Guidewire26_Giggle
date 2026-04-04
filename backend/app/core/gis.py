"""GIS utilities for pincode tier lookups."""

from __future__ import annotations

import logging
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
from shapely.geometry import MultiPolygon, Point, Polygon

from app.core.database import SessionLocal
from app.models.zone import ZoneCluster

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_PINCODES_PATH = _DATA_DIR / "chennai_pincodes.csv"
_FLOOD_KML_PATH = _DATA_DIR / "chennai_flood_hazard.kml"

_KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}
_TIER_PRIORITY = {"low": 1, "medium": 2, "high": 3}


def _normalize_tier(category: str | None) -> str:
    value = (category or "").strip().lower()
    if value in {"high", "very high"}:
        return "high"
    if value in {"medium", "moderate"}:
        return "medium"
    return "low"


def _parse_coordinates(raw_coords: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for chunk in raw_coords.strip().split():
        parts = chunk.split(",")
        if len(parts) < 2:
            continue
        lon = float(parts[0])
        lat = float(parts[1])
        points.append((lon, lat))
    return points


def _load_flood_zones() -> list[tuple[Polygon | MultiPolygon, str]]:
    zones: list[tuple[Polygon | MultiPolygon, str]] = []
    tree = ET.parse(_FLOOD_KML_PATH)
    root = tree.getroot()

    for placemark in root.findall(".//kml:Placemark", _KML_NS):
        category_node = placemark.find(".//kml:SimpleData[@name='CATEGORY']", _KML_NS)
        tier = _normalize_tier(category_node.text if category_node is not None else None)

        geometries: list[Polygon] = []
        for coord_node in placemark.findall(".//kml:coordinates", _KML_NS):
            coords = _parse_coordinates(coord_node.text or "")
            if len(coords) < 3:
                continue
            polygon = Polygon(coords)
            if polygon.is_empty:
                continue
            cleaned = polygon.buffer(0) if not polygon.is_valid else polygon
            if isinstance(cleaned, Polygon):
                geometries.append(cleaned)
            elif isinstance(cleaned, MultiPolygon):
                geometries.extend(cleaned.geoms)

        if not geometries:
            continue
        geometry = geometries[0] if len(geometries) == 1 else MultiPolygon(geometries)
        zones.append((geometry, tier))

    return zones


def _load_pincode_index() -> dict[int, tuple[float, float]]:
    frame = pd.read_csv(_PINCODES_PATH)
    frame.columns = [column.strip().lower() for column in frame.columns]

    required_columns = {"pincode", "latitude", "longitude"}
    if not required_columns.issubset(frame.columns):
        missing = required_columns.difference(frame.columns)
        raise ValueError(f"Missing required columns in {_PINCODES_PATH}: {sorted(missing)}")

    # Keep only the first row per pincode to ensure stable lookups.
    frame = frame.dropna(subset=["pincode", "latitude", "longitude"]).drop_duplicates(subset=["pincode"])

    index: dict[int, tuple[float, float]] = {}
    for row in frame.itertuples(index=False):
        pincode = int(getattr(row, "pincode"))
        lat = float(getattr(row, "latitude"))
        lon = float(getattr(row, "longitude"))
        index[pincode] = (lat, lon)

    return index


_PINCODE_COORDS = _load_pincode_index()
_FLOOD_ZONES = _load_flood_zones()


def _nearest_cluster_id(lat: float, lon: float, clusters: list[ZoneCluster]) -> int:
    nearest = min(
        clusters,
        key=lambda cluster: (float(cluster.centroid_lat) - lat) ** 2 + (float(cluster.centroid_lon) - lon) ** 2,
    )
    return int(nearest.id)


def get_flood_tier_for_pincode(pincode: int) -> str:
    """Return flood hazard tier for a pincode as 'high', 'medium', or 'low'."""
    try:
        key = int(pincode)
    except (TypeError, ValueError):
        return "low"

    coordinates = _PINCODE_COORDS.get(key)
    if coordinates is None:
        return "low"

    lat, lon = coordinates
    point = Point(lon, lat)

    selected_tier = "low"
    for geometry, tier in _FLOOD_ZONES:
        if geometry.covers(point) and _TIER_PRIORITY[tier] > _TIER_PRIORITY[selected_tier]:
            selected_tier = tier

    return selected_tier


def get_zone_cluster_for_pincode(pincode: int) -> int:
    """Return nearest zone cluster id for a pincode, with safe bootstrap fallback."""
    try:
        key = int(pincode)
    except (TypeError, ValueError):
        key = None

    db = SessionLocal()
    try:
        clusters = db.query(ZoneCluster).all()
    finally:
        db.close()

    if not clusters:
        logger.warning(
            "zone_clusters table is empty — returning default cluster 1. Run scripts/zone_clustering.py first."
        )
        return 1

    coordinates = _PINCODE_COORDS.get(key) if key is not None else None
    if coordinates is None:
        return int(min(clusters, key=lambda cluster: int(cluster.id)).id)

    lat, lon = coordinates
    return _nearest_cluster_id(lat, lon, clusters)
