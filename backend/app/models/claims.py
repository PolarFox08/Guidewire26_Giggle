"""Claim ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.database import DeclarativeBase


class Claim(DeclarativeBase):
    __tablename__ = "claims"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(PGUUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    trigger_event_id = Column(PGUUID(as_uuid=True), ForeignKey("trigger_events.id"), nullable=False)
    policy_id = Column(PGUUID(as_uuid=True), ForeignKey("policies.id"), nullable=False)
    claim_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    cascade_day = Column(Integer, nullable=False, default=1)
    deliveries_completed = Column(Integer, nullable=False)
    base_loss_amount = Column(Numeric(8, 2), nullable=False)
    slab_delta_amount = Column(Numeric(8, 2), nullable=False, default=0)
    monthly_proximity_amount = Column(Numeric(8, 2), nullable=False, default=0)
    peak_multiplier_applied = Column(Boolean, nullable=False, default=False)
    total_payout_amount = Column(Numeric(8, 2), nullable=False)
    fraud_score = Column(Numeric(4, 3), nullable=False)
    fraud_routing = Column(String(20), nullable=False)
    zone_claim_match = Column(Boolean, nullable=True)
    activity_7d_score = Column(Numeric(4, 3), nullable=True)
    status = Column(String(20), nullable=False, default="pending")


__all__ = ["Claim"]