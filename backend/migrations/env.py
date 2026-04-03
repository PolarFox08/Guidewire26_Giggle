from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from app.core.database import DeclarativeBase

# Import all models so Alembic metadata is complete for autogenerate workflows.
from app.models.audit import AuditEvent  # noqa: F401
from app.models.claims import Claim  # noqa: F401
from app.models.delivery import DeliveryHistory  # noqa: F401
from app.models.payout import PayoutEvent  # noqa: F401
from app.models.policy import Policy  # noqa: F401
from app.models.slab import SlabConfig  # noqa: F401
from app.models.trigger import TriggerEvent  # noqa: F401
from app.models.worker import WorkerProfile  # noqa: F401
from app.models.zone import ZoneCluster  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_dotenv()
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set. Add it to backend/.env before running Alembic.")

config.set_main_option("sqlalchemy.url", database_url)

target_metadata = DeclarativeBase.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
