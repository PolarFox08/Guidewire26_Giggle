"""Policy ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from app.core.database import DeclarativeBase


class Policy(DeclarativeBase):
    __tablename__ = "policies"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(PGUUID(as_uuid=True), ForeignKey("worker_profiles.id"), nullable=False)
    status = Column(String(20), nullable=False)
    weekly_premium_amount = Column(Numeric(8, 2), nullable=False)
    coverage_start_date = Column(DateTime(timezone=True), nullable=True)
    coverage_week_number = Column(Integer, nullable=False, default=1)
    clean_claim_weeks = Column(Integer, nullable=False, default=0)
    last_premium_paid_at = Column(DateTime(timezone=True), nullable=True)
    next_renewal_at = Column(DateTime(timezone=True), nullable=True)
    model_used = Column(String(10), nullable=True)
    shap_explanation_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


__all__ = ["Policy"]