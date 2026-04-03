"""Create initial GigShield schema tables.

Revision ID: 20260403_01
Revises:
Create Date: 2026-04-03 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260403_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Base lookup tables first (no foreign keys).
    op.create_table(
        "zone_clusters",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("centroid_lat", sa.Numeric(10, 7), nullable=False),
        sa.Column("centroid_lon", sa.Numeric(10, 7), nullable=False),
        sa.Column("flood_tier_numeric", sa.Integer(), nullable=False),
        sa.Column("avg_heavy_rain_days_yr", sa.Numeric(5, 2), nullable=False),
        sa.Column("zone_rate_min", sa.Numeric(6, 2), nullable=False),
        sa.Column("zone_rate_mid", sa.Numeric(6, 2), nullable=False),
        sa.Column("zone_rate_max", sa.Numeric(6, 2), nullable=False),
    )

    op.create_table(
        "slab_config",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column("deliveries_threshold", sa.Integer(), nullable=False),
        sa.Column("bonus_amount", sa.Numeric(8, 2), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # Worker and policy entities.
    op.create_table(
        "worker_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("aadhaar_hash", sa.String(length=64), nullable=False),
        sa.Column("pan_hash", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column("partner_id", sa.String(length=50), nullable=False),
        sa.Column("pincode", sa.Integer(), nullable=False),
        sa.Column("flood_hazard_tier", sa.String(length=6), nullable=False),
        sa.Column("zone_cluster_id", sa.Integer(), sa.ForeignKey("zone_clusters.id"), nullable=False),
        sa.Column("upi_vpa", sa.String(length=100), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("registration_ip", sa.String(length=45), nullable=True),
        sa.Column("enrollment_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("enrollment_week", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("language_preference", sa.String(length=5), nullable=False, server_default=sa.text("'ta'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("aadhaar_hash"),
        sa.UniqueConstraint("pan_hash"),
        sa.UniqueConstraint("partner_id"),
    )

    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("worker_profiles.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("weekly_premium_amount", sa.Numeric(8, 2), nullable=False),
        sa.Column("coverage_start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("coverage_week_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("clean_claim_weeks", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_premium_paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_renewal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_used", sa.String(length=10), nullable=True),
        sa.Column("shap_explanation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Time-series style event/history tables (plain PostgreSQL tables only).
    op.create_table(
        "delivery_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("worker_profiles.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deliveries_count", sa.Integer(), nullable=False),
        sa.Column("earnings_declared", sa.Numeric(8, 2), nullable=True),
        sa.Column("gps_latitude", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("gps_longitude", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "trigger_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("zone_cluster_id", sa.Integer(), sa.ForeignKey("zone_clusters.id"), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger_type", sa.String(length=30), nullable=False),
        sa.Column("composite_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("rain_signal_value", sa.Numeric(8, 2), nullable=True),
        sa.Column("aqi_signal_value", sa.Integer(), nullable=True),
        sa.Column("temp_signal_value", sa.Numeric(5, 2), nullable=True),
        sa.Column("platform_suspended", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("gis_flood_activated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("corroboration_sources", sa.Integer(), nullable=False),
        sa.Column("fast_path_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("worker_profiles.id"), nullable=False),
        sa.Column("trigger_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trigger_events.id"), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("claim_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("cascade_day", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("deliveries_completed", sa.Integer(), nullable=False),
        sa.Column("base_loss_amount", sa.Numeric(8, 2), nullable=False),
        sa.Column("slab_delta_amount", sa.Numeric(8, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("monthly_proximity_amount", sa.Numeric(8, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("peak_multiplier_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("total_payout_amount", sa.Numeric(8, 2), nullable=False),
        sa.Column("fraud_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("fraud_routing", sa.String(length=20), nullable=False),
        sa.Column("zone_claim_match", sa.Boolean(), nullable=True),
        sa.Column("activity_7d_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
    )

    op.create_table(
        "payout_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("worker_profiles.id"), nullable=False),
        sa.Column("razorpay_payout_id", sa.String(length=100), nullable=True),
        sa.Column("amount", sa.Numeric(8, 2), nullable=False),
        sa.Column("upi_vpa", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("actor", sa.String(length=50), nullable=False, server_default=sa.text("'system'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("payout_events")
    op.drop_table("claims")
    op.drop_table("trigger_events")
    op.drop_table("delivery_history")
    op.drop_table("policies")
    op.drop_table("worker_profiles")
    op.drop_table("slab_config")
    op.drop_table("zone_clusters")
