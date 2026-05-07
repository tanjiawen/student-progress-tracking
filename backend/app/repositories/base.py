"""Base repository with generic CRUD operations."""

from typing import Generic, TypeVar

from sqlmodel import SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

T = TypeVar("T", bound=SQLModel)


class BaseRepository(Generic[T]):
    """Generic base repository providing standard CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, id: int) -> T | None:
        """Get a single record by primary key."""
        statement = select(self.model).where(self.model.id == id)
        result = await self.session.exec(statement)
        return result.first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        """Get a paginated list of records."""
        statement = select(self.model).offset(skip).limit(limit)
        result = await self.session.exec(statement)
        return list(result.all())

    async def create(self, obj: T) -> T:
        """Create a new record."""
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, id: int, data: dict) -> T | None:
        """Update an existing record by primary key."""
        db_obj = await self.get_by_id(id)
        if not db_obj:
            return None
        for key, value in data.items():
            setattr(db_obj, key, value)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: int) -> bool:
        """Delete a record by primary key."""
        db_obj = await self.get_by_id(id)
        if not db_obj:
            return False
        await self.session.delete(db_obj)
        await self.session.commit()
        return True

    async def count(self) -> int:
        """Count total records in the table."""
        statement = select(func.count(self.model.id))
        result = await self.session.exec(statement)
        return result.one()
