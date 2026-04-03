"""Zone cluster ORM model."""

from __future__ import annotations

from sqlalchemy import Column, Integer, Numeric

from app.core.database import DeclarativeBase


class ZoneCluster(DeclarativeBase):
    __tablename__ = "zone_clusters"

    id = Column(Integer, primary_key=True)
    centroid_lat = Column(Numeric(10, 7), nullable=False)
    centroid_lon = Column(Numeric(10, 7), nullable=False)
    flood_tier_numeric = Column(Integer, nullable=False)
    avg_heavy_rain_days_yr = Column(Numeric(5, 2), nullable=False)
    zone_rate_min = Column(Numeric(6, 2), nullable=False)
    zone_rate_mid = Column(Numeric(6, 2), nullable=False)
    zone_rate_max = Column(Numeric(6, 2), nullable=False)


__all__ = ["ZoneCluster"]