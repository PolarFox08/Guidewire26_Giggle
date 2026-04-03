"""Worker profile ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.database import DeclarativeBase


class WorkerProfile(DeclarativeBase):
    __tablename__ = "worker_profiles"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aadhaar_hash = Column(String(64), nullable=False, unique=True)
    pan_hash = Column(String(64), nullable=False, unique=True)
    platform = Column(String(10), nullable=False)
    partner_id = Column(String(50), nullable=False, unique=True)
    pincode = Column(Integer, nullable=False)
    flood_hazard_tier = Column(String(6), nullable=False)
    zone_cluster_id = Column(Integer, ForeignKey("zone_clusters.id"), nullable=False)
    upi_vpa = Column(String(100), nullable=False)
    device_fingerprint = Column(String(128), nullable=True)
    registration_ip = Column(String(45), nullable=True)
    enrollment_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    enrollment_week = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    language_preference = Column(String(5), nullable=False, default="ta")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


__all__ = ["WorkerProfile"]