"""程序化执行 Alembic 迁移（启动时自动迁移用）。"""

from pathlib import Path

from alembic import command
from alembic.config import Config


def to_sync_url(database_url: str) -> str:
    """把异步驱动 URL 转成 Alembic 使用的同步 URL。"""
    return database_url.replace("+aiosqlite", "").replace("+asyncpg", "")


def run_migrations(database_url: str, project_root: Path) -> None:
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", to_sync_url(database_url))
    command.upgrade(cfg, "head")
