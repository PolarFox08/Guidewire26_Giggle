from sqlalchemy import Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models.worker import WorkerProfile


def test_worker_profile_table_name():
    assert WorkerProfile.__tablename__ == "worker_profiles"


def test_worker_profile_schema():
    columns = WorkerProfile.__table__.columns

    assert isinstance(columns["id"].type, PGUUID)
    assert columns["id"].primary_key is True
    assert columns["aadhaar_hash"].type.length == 64
    assert columns["pan_hash"].type.length == 64
    assert columns["platform"].type.length == 10
    assert columns["partner_id"].type.length == 50
    assert isinstance(columns["pincode"].type, Integer)
    assert columns["flood_hazard_tier"].type.length == 6
    assert columns["zone_cluster_id"].foreign_keys
    assert columns["upi_vpa"].type.length == 100
    assert columns["device_fingerprint"].type.length == 128
    assert columns["registration_ip"].type.length == 45
    assert isinstance(columns["enrollment_date"].type, DateTime)
    assert columns["enrollment_date"].type.timezone is True
    assert isinstance(columns["enrollment_week"].type, Integer)
    assert isinstance(columns["is_active"].type, Boolean)
    assert columns["language_preference"].type.length == 5
    assert isinstance(columns["created_at"].type, DateTime)
    assert columns["created_at"].type.timezone is True
    assert isinstance(columns["updated_at"].type, DateTime)
    assert columns["updated_at"].type.timezone is True


def test_worker_profile_defaults():
    columns = WorkerProfile.__table__.columns

    assert columns["enrollment_week"].default.arg == 1
    assert columns["is_active"].default.arg is True
    assert columns["language_preference"].default.arg == "ta"