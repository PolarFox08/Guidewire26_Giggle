from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any, cast

import pytest

from app.core import database as core_database
from app.models.audit import AuditEvent


def test_get_db_yields_session_and_closes(monkeypatch):
    class _FakeSession:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    fake_session = _FakeSession()
    monkeypatch.setattr(core_database, "SessionLocal", lambda: fake_session)

    gen = cast(Iterator[Any], core_database.get_db())
    yielded = next(gen)

    assert yielded is fake_session

    with pytest.raises(StopIteration):
        next(gen)

    assert fake_session.closed is True


def test_receive_before_flush_blocks_audit_update():
    audit = AuditEvent(
        event_type="x",
        entity_id="00000000-0000-0000-0000-000000000000",
        entity_type="claim",
        payload={"x": 1},
        actor="system",
    )

    class _FakeSession:
        dirty = [audit]
        deleted = []

    with pytest.raises(RuntimeError):
        core_database.receive_before_flush(_FakeSession(), None, None)


def test_receive_before_flush_blocks_audit_delete():
    audit = AuditEvent(
        event_type="x",
        entity_id="00000000-0000-0000-0000-000000000000",
        entity_type="claim",
        payload={"x": 1},
        actor="system",
    )

    class _FakeSession:
        dirty = []
        deleted = [audit]

    with pytest.raises(RuntimeError):
        core_database.receive_before_flush(_FakeSession(), None, None)


def test_celery_app_schedule_and_timezone():
    celery_module = importlib.import_module("app.tasks.celery_app")

    assert celery_module.celery_app.conf.timezone == "Asia/Kolkata"
    schedule = celery_module.celery_app.conf.beat_schedule
    assert "trigger-polling-30m" in schedule
    assert "weekly-renewal-sunday-midnight" in schedule
    assert "cascade-recovery-12h" in schedule
    assert "aqi-polling-hourly" in schedule
