"""Seed slab_config with Zomato slab thresholds.

Revision ID: 20260403_02
Revises: 20260403_01
Create Date: 2026-04-03 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260403_02"
down_revision = "20260403_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO slab_config (platform, deliveries_threshold, bonus_amount, is_active)
            VALUES
                ('zomato', 7, 50.00, TRUE),
                ('zomato', 12, 120.00, TRUE),
                ('zomato', 15, 150.00, TRUE),
                ('zomato', 21, 200.00, TRUE)
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM slab_config
            WHERE platform = 'zomato'
              AND (deliveries_threshold, bonus_amount) IN (
                  (7, 50.00),
                  (12, 120.00),
                  (15, 150.00),
                  (21, 200.00)
              )
            """
        )
    )
