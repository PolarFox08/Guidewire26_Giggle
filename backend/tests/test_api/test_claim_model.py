from sqlalchemy import Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models.claims import Claim


def test_claim_table_name():
    assert Claim.__tablename__ == "claims"


def test_claim_schema():
    columns = Claim.__table__.columns

    assert isinstance(columns["id"].type, PGUUID)
    assert columns["id"].primary_key is True
    assert isinstance(columns["worker_id"].type, PGUUID)
    assert columns["worker_id"].foreign_keys
    assert isinstance(columns["trigger_event_id"].type, PGUUID)
    assert columns["trigger_event_id"].foreign_keys
    assert isinstance(columns["policy_id"].type, PGUUID)
    assert columns["policy_id"].foreign_keys
    assert isinstance(columns["claim_date"].type, DateTime)
    assert columns["claim_date"].type.timezone is True
    assert isinstance(columns["cascade_day"].type, Integer)
    assert isinstance(columns["deliveries_completed"].type, Integer)
    assert isinstance(columns["base_loss_amount"].type, Numeric)
    assert columns["base_loss_amount"].type.precision == 8
    assert columns["base_loss_amount"].type.scale == 2
    assert isinstance(columns["slab_delta_amount"].type, Numeric)
    assert columns["slab_delta_amount"].type.precision == 8
    assert columns["slab_delta_amount"].type.scale == 2
    assert isinstance(columns["monthly_proximity_amount"].type, Numeric)
    assert columns["monthly_proximity_amount"].type.precision == 8
    assert columns["monthly_proximity_amount"].type.scale == 2
    assert isinstance(columns["peak_multiplier_applied"].type, Boolean)
    assert isinstance(columns["total_payout_amount"].type, Numeric)
    assert columns["total_payout_amount"].type.precision == 8
    assert columns["total_payout_amount"].type.scale == 2
    assert isinstance(columns["fraud_score"].type, Numeric)
    assert columns["fraud_score"].type.precision == 4
    assert columns["fraud_score"].type.scale == 3
    assert columns["fraud_routing"].type.length == 20
    assert isinstance(columns["zone_claim_match"].type, Boolean)
    assert isinstance(columns["activity_7d_score"].type, Numeric)
    assert columns["activity_7d_score"].type.precision == 4
    assert columns["activity_7d_score"].type.scale == 3
    assert columns["status"].type.length == 20


def test_claim_defaults():
    columns = Claim.__table__.columns

    assert columns["cascade_day"].default.arg == 1
    assert columns["slab_delta_amount"].default.arg == 0
    assert columns["monthly_proximity_amount"].default.arg == 0
    assert columns["peak_multiplier_applied"].default.arg is False
    assert columns["status"].default.arg == "pending"