"""Trigger event ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.database import DeclarativeBase


class TriggerEvent(DeclarativeBase):
    __tablename__ = "trigger_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_cluster_id = Column(Integer, ForeignKey("zone_clusters.id"), nullable=False)
    triggered_at = Column(DateTime(timezone=True), nullable=False)
    trigger_type = Column(String(30), nullable=False)
    composite_score = Column(Numeric(4, 3), nullable=False)
    rain_signal_value = Column(Numeric(8, 2), nullable=True)
    aqi_signal_value = Column(Integer, nullable=True)
    temp_signal_value = Column(Numeric(5, 2), nullable=True)
    platform_suspended = Column(Boolean, nullable=False, default=False)
    gis_flood_activated = Column(Boolean, nullable=False, default=False)
    corroboration_sources = Column(Integer, nullable=False)
    fast_path_used = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="active")
    closed_at = Column(DateTime(timezone=True), nullable=True)


__all__ = ["TriggerEvent"]