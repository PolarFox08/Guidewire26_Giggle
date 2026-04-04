"""Create and seed platform_partners table.

Revision ID: 20260404_04
Revises: 20260403_03
Create Date: 2026-04-04 00:00:00
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260404_04"
down_revision = "20260403_03"
branch_labels = None
depends_on = None


platform_partners_table = sa.table(
    "platform_partners",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("platform", sa.String(length=10)),
    sa.column("partner_id", sa.String(length=50)),
    sa.column("partner_name", sa.String(length=100)),
)


zomato_names = [
    "Arun Kumar",
    "Bala Subramanian",
    "Charan Raj",
    "Deepak Iyer",
    "Eswar Prasad",
    "Farooq Ali",
    "Gokul Nair",
    "Hari Krishnan",
    "Imran Khan",
    "Jagan Mohan",
    "Karthik Ravi",
    "Logesh Kumar",
    "Manoj Prabhu",
    "Naveen Raj",
    "Pradeep Anand",
    "Raghu Ram",
    "Sathish Kumar",
    "Thiru Murugan",
    "Uday Shankar",
    "Vigneshwaran S",
]


swiggy_names = [
    "Akash Verma",
    "Bharath Chandran",
    "Chetan Das",
    "Dinesh Babu",
    "Elango Mani",
    "Faizal Rahman",
    "Ganesh B",
    "Harishankar T",
    "Irfan Ahmed",
    "Jeeva N",
    "Kiran Raj",
    "Lokeshwar P",
    "Madhan K",
    "Nitin Joseph",
    "Omkar R",
    "Pranav Selvam",
    "Ramesh B",
    "Saravanan M",
    "Tarun S",
    "Vasanth K",
]


def _seed_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for idx, partner_name in enumerate(zomato_names, start=1):
        rows.append(
            {
                "id": uuid.uuid4(),
                "platform": "zomato",
                "partner_id": f"ZOM-TEST-{idx:03d}",
                "partner_name": partner_name,
            }
        )

    for idx, partner_name in enumerate(swiggy_names, start=1):
        rows.append(
            {
                "id": uuid.uuid4(),
                "platform": "swiggy",
                "partner_id": f"SWY-TEST-{idx:03d}",
                "partner_name": partner_name,
            }
        )

    return rows


def upgrade() -> None:
    op.create_table(
        "platform_partners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column("partner_id", sa.String(length=50), nullable=False),
        sa.Column("partner_name", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("partner_id"),
    )

    op.bulk_insert(platform_partners_table, _seed_rows())


def downgrade() -> None:
    op.drop_table("platform_partners")
