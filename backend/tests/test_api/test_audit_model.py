from sqlalchemy import DateTime, String, event
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from app.models.audit import AuditEvent, prevent_audit_event_update


def test_audit_event_table_name():
    assert AuditEvent.__tablename__ == "audit_events"


def test_audit_event_schema():
    columns = AuditEvent.__table__.columns

    assert isinstance(columns["id"].type, PGUUID)
    assert columns["id"].primary_key is True
    assert isinstance(columns["event_type"].type, String)
    assert columns["event_type"].type.length == 50
    assert isinstance(columns["entity_id"].type, PGUUID)
    assert isinstance(columns["entity_type"].type, String)
    assert columns["entity_type"].type.length == 30
    assert isinstance(columns["payload"].type, JSONB)
    assert isinstance(columns["actor"].type, String)
    assert columns["actor"].type.length == 50
    assert isinstance(columns["created_at"].type, DateTime)
    assert columns["created_at"].type.timezone is True


def test_audit_event_defaults_and_listener():
    columns = AuditEvent.__table__.columns

    assert columns["actor"].default is not None
    assert columns["created_at"].server_default is not None
    assert event.contains(AuditEvent, "before_update", prevent_audit_event_update)


def test_audit_event_before_update_listener_raises_runtime_error():
    event_instance = AuditEvent(
        event_type="test_event",
        entity_id="00000000-0000-0000-0000-000000000001",
        entity_type="worker",
        payload={"ok": True},
    )

    try:
        prevent_audit_event_update(None, None, event_instance)
    except RuntimeError as exc:
        assert "append-only" in str(exc)
        assert "UPDATE operations" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError to be raised")