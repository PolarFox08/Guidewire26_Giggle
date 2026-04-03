"""Slab configuration ORM model."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, func

from app.core.database import DeclarativeBase


class SlabConfig(DeclarativeBase):
    __tablename__ = "slab_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(10), nullable=False)
    deliveries_threshold = Column(Integer, nullable=False)
    bonus_amount = Column(Numeric(8, 2), nullable=False)
    last_verified_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_active = Column(Boolean, nullable=False, default=True)


__all__ = ["SlabConfig"]