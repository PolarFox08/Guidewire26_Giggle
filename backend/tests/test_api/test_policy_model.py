from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from app.models.policy import Policy


def test_policy_table_name():
    assert Policy.__tablename__ == "policies"


def test_policy_schema():
    columns = Policy.__table__.columns

    assert isinstance(columns["id"].type, PGUUID)
    assert columns["id"].primary_key is True
    assert isinstance(columns["worker_id"].type, PGUUID)
    assert columns["worker_id"].foreign_keys
    assert columns["status"].type.length == 20
    assert isinstance(columns["weekly_premium_amount"].type, Numeric)
    assert columns["weekly_premium_amount"].type.precision == 8
    assert columns["weekly_premium_amount"].type.scale == 2
    assert isinstance(columns["coverage_start_date"].type, DateTime)
    assert columns["coverage_start_date"].type.timezone is True
    assert isinstance(columns["coverage_week_number"].type, Integer)
    assert isinstance(columns["clean_claim_weeks"].type, Integer)
    assert isinstance(columns["last_premium_paid_at"].type, DateTime)
    assert columns["last_premium_paid_at"].type.timezone is True
    assert isinstance(columns["next_renewal_at"].type, DateTime)
    assert columns["next_renewal_at"].type.timezone is True
    assert columns["model_used"].type.length == 10
    assert isinstance(columns["shap_explanation_json"].type, JSONB)
    assert isinstance(columns["created_at"].type, DateTime)
    assert columns["created_at"].type.timezone is True
    assert isinstance(columns["updated_at"].type, DateTime)
    assert columns["updated_at"].type.timezone is True


def test_policy_defaults():
    columns = Policy.__table__.columns

    assert columns["coverage_week_number"].default.arg == 1
    assert columns["clean_claim_weeks"].default.arg == 0