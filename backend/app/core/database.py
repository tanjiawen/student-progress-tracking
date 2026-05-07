from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_recycle=3600,
    future=True,
    echo=settings.DEBUG,
)

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
