from sqlalchemy import Boolean, DateTime, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models.trigger import TriggerEvent


def test_trigger_event_table_name():
    assert TriggerEvent.__tablename__ == "trigger_events"


def test_trigger_event_schema():
    columns = TriggerEvent.__table__.columns

    assert isinstance(columns["id"].type, PGUUID)
    assert columns["id"].primary_key is True
    assert isinstance(columns["zone_cluster_id"].type, Integer)
    assert columns["zone_cluster_id"].foreign_keys
    assert isinstance(columns["triggered_at"].type, DateTime)
    assert columns["triggered_at"].type.timezone is True
    assert columns["trigger_type"].type.length == 30
    assert isinstance(columns["composite_score"].type, Numeric)
    assert columns["composite_score"].type.precision == 4
    assert columns["composite_score"].type.scale == 3
    assert isinstance(columns["rain_signal_value"].type, Numeric)
    assert columns["rain_signal_value"].type.precision == 8
    assert columns["rain_signal_value"].type.scale == 2
    assert isinstance(columns["aqi_signal_value"].type, Integer)
    assert isinstance(columns["temp_signal_value"].type, Numeric)
    assert columns["temp_signal_value"].type.precision == 5
    assert columns["temp_signal_value"].type.scale == 2
    assert isinstance(columns["platform_suspended"].type, Boolean)
    assert isinstance(columns["gis_flood_activated"].type, Boolean)
    assert isinstance(columns["corroboration_sources"].type, Integer)
    assert isinstance(columns["fast_path_used"].type, Boolean)
    assert columns["status"].type.length == 20
    assert isinstance(columns["closed_at"].type, DateTime)
    assert columns["closed_at"].type.timezone is True


def test_trigger_event_defaults():
    columns = TriggerEvent.__table__.columns

    assert columns["platform_suspended"].default.arg is False
    assert columns["gis_flood_activated"].default.arg is False
    assert columns["fast_path_used"].default.arg is False
    assert columns["status"].default.arg == "active"