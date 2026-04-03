"""Payout event ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.database import DeclarativeBase


class PayoutEvent(DeclarativeBase):
    __tablename__ = "payout_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(PGUUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    worker_id = Column(PGUUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    razorpay_payout_id = Column(String(100), nullable=True)
    amount = Column(Numeric(8, 2), nullable=False)
    upi_vpa = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)
    initiated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(String, nullable=True)


__all__ = ["PayoutEvent"]