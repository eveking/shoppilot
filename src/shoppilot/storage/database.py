"""异步引擎与会话工厂的构建。"""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def _ensure_sqlite_dir(database_url: str) -> None:
    """确保 SQLite 文件的父目录存在。"""
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        return
    path = database_url[len(prefix) :]
    if not path or path == ":memory:":
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def make_engine_and_factory(database_url: str) -> tuple[AsyncEngine, async_sessionmaker]:
    _ensure_sqlite_dir(database_url)
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory
