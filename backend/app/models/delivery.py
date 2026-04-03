"""Delivery history ORM model."""

from __future__ import annotations

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.database import DeclarativeBase


class DeliveryHistory(DeclarativeBase):
    __tablename__ = "delivery_history"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(PGUUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    deliveries_count = Column(Integer, nullable=False)
    earnings_declared = Column(Numeric(8, 2), nullable=True)
    gps_latitude = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    gps_longitude = Column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    platform = Column(String(10), nullable=False)
    is_simulated = Column(Boolean, nullable=False, default=True)


__all__ = ["DeliveryHistory"]