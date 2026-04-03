from sqlalchemy import Boolean, DateTime, Integer, Numeric

from app.models.slab import SlabConfig


def test_slab_config_table_name():
    assert SlabConfig.__tablename__ == "slab_config"


def test_slab_config_schema():
    columns = SlabConfig.__table__.columns

    assert isinstance(columns["id"].type, Integer)
    assert columns["id"].primary_key is True
    assert columns["id"].autoincrement is True
    assert columns["platform"].type.length == 10
    assert isinstance(columns["deliveries_threshold"].type, Integer)
    assert isinstance(columns["bonus_amount"].type, Numeric)
    assert columns["bonus_amount"].type.precision == 8
    assert columns["bonus_amount"].type.scale == 2
    assert isinstance(columns["last_verified_at"].type, DateTime)
    assert columns["last_verified_at"].type.timezone is True
    assert isinstance(columns["is_active"].type, Boolean)


def test_slab_config_defaults():
    columns = SlabConfig.__table__.columns

    assert columns["is_active"].default.arg is True