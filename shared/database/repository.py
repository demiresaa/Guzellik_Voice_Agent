"""
shared/database/repository.py

Generic Repository Pattern

Provides base repository with CRUD operations.
"""

from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.common.exceptions import NotFoundException, DatabaseException
from shared.common.logging import get_logger

logger = get_logger(__name__)

# Generic type for model
ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    Generic repository for database operations.

    Usage:
        class UserRepository(BaseRepository[User]):
            def __init__(self, session: AsyncSession):
                super().__init__(session, User)

            async def find_by_email(self, email: str) -> Optional[User]:
                stmt = select(User).where(User.email == email)
                result = await self.session.execute(stmt)
                return result.scalar_one_or_none()
    """

    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        """
        Initialize repository.

        Args:
            session: Async database session
            model: SQLAlchemy model class
        """
        self.session = session
        self.model = model

    async def create(self, entity: ModelType) -> ModelType:
        """
        Create new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity with ID

        Raises:
            DatabaseException: If creation fails
        """
        try:
            self.session.add(entity)
            await self.session.flush()
            await self.session.refresh(entity)

            logger.debug(f"Created {self.model.__name__}", extra={
                "model": self.model.__name__
            })

            return entity

        except Exception as e:
            logger.error(f"Failed to create {self.model.__name__}", extra={
                "model": self.model.__name__,
                "error": str(e)
            })
            raise DatabaseException(
                f"Failed to create {self.model.__name__}",
                operation="create",
                original_error=e
            )

    async def get_by_id(self, entity_id: Any) -> Optional[ModelType]:
        """
        Get entity by ID.

        Args:
            entity_id: Entity ID

        Returns:
            Entity or None if not found
        """
        try:
            result = await self.session.get(self.model, entity_id)
            return result

        except Exception as e:
            logger.error(f"Failed to get {self.model.__name__} by ID", extra={
                "model": self.model.__name__,
                "id": entity_id,
                "error": str(e)
            })
            raise DatabaseException(
                f"Failed to get {self.model.__name__}",
                operation="get_by_id",
                original_error=e
            )

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        """
        Get all entities.

        Args:
            limit: Max number of results
            offset: Number of results to skip

        Returns:
            List of entities
        """
        try:
            stmt = select(self.model).limit(limit).offset(offset)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Failed to get all {self.model.__name__}", extra={
                "model": self.model.__name__,
                "error": str(e)
            })
            raise DatabaseException(
                f"Failed to get all {self.model.__name__}",
                operation="get_all",
                original_error=e
            )

    async def update(self, entity: ModelType) -> ModelType:
        """
        Update existing entity.

        Args:
            entity: Entity to update

        Returns:
            Updated entity

        Raises:
            DatabaseException: If update fails
        """
        try:
            await self.session.flush()
            await self.session.refresh(entity)

            logger.debug(f"Updated {self.model.__name__}", extra={
                "model": self.model.__name__
            })

            return entity

        except Exception as e:
            logger.error(f"Failed to update {self.model.__name__}", extra={
                "model": self.model.__name__,
                "error": str(e)
            })
            raise DatabaseException(
                f"Failed to update {self.model.__name__}",
                operation="update",
                original_error=e
            )

    async def delete_by_id(self, entity_id: Any) -> bool:
        """
        Delete entity by ID.

        Args:
            entity_id: Entity ID

        Returns:
            True if deleted, False if not found

        Raises:
            DatabaseException: If deletion fails
        """
        try:
            stmt = delete(self.model).where(self.model.id == entity_id)
            result = await self.session.execute(stmt)
            await self.session.flush()

            deleted = result.rowcount > 0

            if deleted:
                logger.debug(f"Deleted {self.model.__name__}", extra={
                    "model": self.model.__name__,
                    "id": entity_id
                })

            return deleted

        except Exception as e:
            logger.error(f"Failed to delete {self.model.__name__}", extra={
                "model": self.model.__name__,
                "id": entity_id,
                "error": str(e)
            })
            raise DatabaseException(
                f"Failed to delete {self.model.__name__}",
                operation="delete",
                original_error=e
            )

    async def count(self) -> int:
        """
        Count total entities.

        Returns:
            Total count
        """
        try:
            from sqlalchemy import func as sql_func
            stmt = select(sql_func.count()).select_from(self.model)
            result = await self.session.execute(stmt)
            return result.scalar_one()

        except Exception as e:
            logger.error(f"Failed to count {self.model.__name__}", extra={
                "model": self.model.__name__,
                "error": str(e)
            })
            raise DatabaseException(
                f"Failed to count {self.model.__name__}",
                operation="count",
                original_error=e
            )

    async def exists(self, entity_id: Any) -> bool:
        """
        Check if entity exists.

        Args:
            entity_id: Entity ID

        Returns:
            True if exists, False otherwise
        """
        entity = await self.get_by_id(entity_id)
        return entity is not None
