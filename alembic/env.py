"""Alembic 环境。

连接串由调用方注入（见 storage/migrations.py）：
优先取 config 中已设置的 sqlalchemy.url，否则回退 SHOPILOT_DATABASE_URL。
"""

import os

from alembic import context
from sqlalchemy import create_engine

from shoppilot.storage.models import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url and url != "sqlite://":
        return url
    return os.getenv("SHOPILOT_DATABASE_URL", "sqlite:///./data/shoppilot.db")


def run_migrations_online() -> None:
    engine = create_engine(_database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    context.configure(url=_database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
