from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models.payout import PayoutEvent


def test_payout_event_table_name():
    assert PayoutEvent.__tablename__ == "payout_events"


def test_payout_event_schema():
    columns = PayoutEvent.__table__.columns

    assert isinstance(columns["id"].type, PGUUID)
    assert columns["id"].primary_key is True
    assert isinstance(columns["claim_id"].type, PGUUID)
    assert columns["claim_id"].foreign_keys
    assert isinstance(columns["worker_id"].type, PGUUID)
    assert columns["worker_id"].foreign_keys
    assert columns["razorpay_payout_id"].type.length == 100
    assert isinstance(columns["amount"].type, Numeric)
    assert columns["amount"].type.precision == 8
    assert columns["amount"].type.scale == 2
    assert columns["upi_vpa"].type.length == 100
    assert columns["status"].type.length == 20
    assert isinstance(columns["initiated_at"].type, DateTime)
    assert columns["initiated_at"].type.timezone is True
    assert isinstance(columns["completed_at"].type, DateTime)
    assert columns["completed_at"].type.timezone is True
    assert isinstance(columns["failure_reason"].type, String)


def test_payout_event_defaults():
    columns = PayoutEvent.__table__.columns

    assert columns["initiated_at"].server_default is not None