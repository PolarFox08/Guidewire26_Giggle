"""Audit event ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, String, event, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from app.core.database import DeclarativeBase


class AuditEvent(DeclarativeBase):
    __tablename__ = "audit_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)
    entity_id = Column(PGUUID(as_uuid=True), nullable=False)
    entity_type = Column(String(30), nullable=False)
    payload = Column(JSONB, nullable=False)
    actor = Column(String(50), nullable=False, default="system")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


@event.listens_for(AuditEvent, "before_update")
def prevent_audit_event_update(mapper, connection, target):
    raise RuntimeError("audit_events table is append-only. UPDATE operations are not permitted.")


__all__ = ["AuditEvent", "prevent_audit_event_update"]