from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

POOL_CONFIG = {
    "pool_size": 20,
    "max_overflow": 30,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
    "echo": settings.DEBUG,
}


def create_async_engine_with_pool(url: str):
    """创建带有统一连接池配置的异步引擎."""
    return create_async_engine(url, **POOL_CONFIG, future=True)


def create_sync_engine_with_pool(url: str):
    """创建带有统一连接池配置的同步引擎."""
    return create_engine(url, **POOL_CONFIG, future=True)


engine = create_async_engine_with_pool(settings.DATABASE_URL)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_db() -> None:
    from sqlmodel import SQLModel

    # Import models module so SQLModel registers them as a side effect
    import importlib

    importlib.import_module("app.models")

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
