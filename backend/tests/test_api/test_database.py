from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.core.database as database_module
from app.models.audit import AuditEvent


def test_get_db_closes_session_on_exit(monkeypatch):
    closed = {"value": False}

    class FakeSession:
        def close(self):
            closed["value"] = True

    fake_session = FakeSession()
    monkeypatch.setattr(database_module, "SessionLocal", lambda: fake_session)

    generator = database_module.get_db()
    session = next(generator)

    assert session is fake_session

    with pytest.raises(StopIteration):
        next(generator)

    assert closed["value"] is True


def test_receive_before_flush_raises_for_dirty_audit_event():
    session = SimpleNamespace(dirty=[_build_audit_event()], deleted=[])

    with pytest.raises(RuntimeError, match="UPDATE operations are not permitted"):
        database_module.receive_before_flush(session, None, None)


def test_receive_before_flush_raises_for_deleted_audit_event():
    session = SimpleNamespace(dirty=[], deleted=[_build_audit_event()])

    with pytest.raises(RuntimeError, match="DELETE operations are not permitted"):
        database_module.receive_before_flush(session, None, None)


def _build_audit_event() -> AuditEvent:
    return AuditEvent(
        event_type="audit_test",
        entity_id=uuid4(),
        entity_type="worker",
        payload={"status": "ok"},
    )