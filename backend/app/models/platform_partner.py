"""Platform partner seed table ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.database import DeclarativeBase


class PlatformPartner(DeclarativeBase):
    __tablename__ = "platform_partners"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform = Column(String(10), nullable=False)
    partner_id = Column(String(50), nullable=False, unique=True)
    partner_name = Column(String(100), nullable=False)


__all__ = ["PlatformPartner"]
