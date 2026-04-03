from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models.delivery import DeliveryHistory


def test_delivery_history_table_name():
    assert DeliveryHistory.__tablename__ == "delivery_history"


def test_delivery_history_schema():
    columns = DeliveryHistory.__table__.columns

    assert isinstance(columns["id"].type, PGUUID)
    assert columns["id"].primary_key is True
    assert isinstance(columns["worker_id"].type, PGUUID)
    assert columns["worker_id"].foreign_keys
    assert isinstance(columns["recorded_at"].type, DateTime)
    assert columns["recorded_at"].type.timezone is True
    assert isinstance(columns["deliveries_count"].type, Integer)
    assert isinstance(columns["earnings_declared"].type, Numeric)
    assert columns["earnings_declared"].type.precision == 8
    assert columns["earnings_declared"].type.scale == 2
    assert isinstance(columns["gps_latitude"].type, Geometry)
    assert columns["gps_latitude"].type.geometry_type == "POINT"
    assert columns["gps_latitude"].type.srid == 4326
    assert isinstance(columns["gps_longitude"].type, Geometry)
    assert columns["gps_longitude"].type.geometry_type == "POINT"
    assert columns["gps_longitude"].type.srid == 4326
    assert columns["platform"].type.length == 10
    assert isinstance(columns["is_simulated"].type, Boolean)


def test_delivery_history_defaults():
    columns = DeliveryHistory.__table__.columns

    assert columns["is_simulated"].default.arg is True