# services/booking_agent_service/repositories/base.py

"""
Base Repository Pattern for data access abstraction.
Staff Engineer principle: Separation of concerns, testability, swappable implementations.

Benefits:
- Business logic separated from data access
- Easy to test (mock repositories)
- Easy to switch databases (in-memory → PostgreSQL → MongoDB)
- Consistent interface across all repositories
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Dict, Any
from datetime import datetime
from ..utils.logger import get_logger
from ..utils.exceptions import DatabaseError, NotFoundError

logger = get_logger(__name__)

# Type variable for entity types
T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository with common CRUD operations.

    All repositories inherit from this base class to ensure
    consistent interface and behavior.

    Type parameter T: Entity type (Customer, Appointment, etc.)
    """

    def __init__(self):
        """Initialize repository with storage backend"""
        self._storage: Dict[str, T] = {}
        logger.debug(f"{self.__class__.__name__} initialized")

    @abstractmethod
    def _get_entity_id(self, entity: T) -> str:
        """
        Get unique identifier from entity.

        Must be implemented by subclasses.

        Args:
            entity: Entity instance

        Returns:
            Unique identifier string
        """
        pass

    def create(self, entity: T) -> T:
        """
        Create a new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity

        Raises:
            DatabaseError: If creation fails
        """
        try:
            entity_id = self._get_entity_id(entity)

            if entity_id in self._storage:
                raise DatabaseError(
                    message=f"Entity with ID {entity_id} already exists",
                    details={"entity_id": entity_id}
                )

            self._storage[entity_id] = entity

            logger.debug(
                f"Entity created",
                repository=self.__class__.__name__,
                entity_id=entity_id
            )

            return entity

        except Exception as e:
            logger.error(
                f"Failed to create entity",
                repository=self.__class__.__name__,
                error=str(e)
            )
            raise DatabaseError(
                message="Failed to create entity",
                details={"error": str(e)}
            )

    def get_by_id(self, entity_id: str) -> Optional[T]:
        """
        Retrieve entity by ID.

        Args:
            entity_id: Unique identifier

        Returns:
            Entity if found, None otherwise
        """
        return self._storage.get(entity_id)

    def get_by_id_or_raise(self, entity_id: str) -> T:
        """
        Retrieve entity by ID or raise exception.

        Args:
            entity_id: Unique identifier

        Returns:
            Entity

        Raises:
            NotFoundError: If entity not found
        """
        entity = self.get_by_id(entity_id)
        if entity is None:
            raise NotFoundError(
                message=f"Entity with ID {entity_id} not found",
                details={"entity_id": entity_id}
            )
        return entity

    def update(self, entity: T) -> T:
        """
        Update existing entity.

        Args:
            entity: Entity with updated data

        Returns:
            Updated entity

        Raises:
            NotFoundError: If entity doesn't exist
            DatabaseError: If update fails
        """
        try:
            entity_id = self._get_entity_id(entity)

            if entity_id not in self._storage:
                raise NotFoundError(
                    message=f"Entity with ID {entity_id} not found",
                    details={"entity_id": entity_id}
                )

            self._storage[entity_id] = entity

            logger.debug(
                f"Entity updated",
                repository=self.__class__.__name__,
                entity_id=entity_id
            )

            return entity

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update entity",
                repository=self.__class__.__name__,
                error=str(e)
            )
            raise DatabaseError(
                message="Failed to update entity",
                details={"error": str(e)}
            )

    def delete(self, entity_id: str) -> bool:
        """
        Delete entity by ID.

        Args:
            entity_id: Unique identifier

        Returns:
            True if deleted, False if not found
        """
        if entity_id in self._storage:
            del self._storage[entity_id]
            logger.debug(
                f"Entity deleted",
                repository=self.__class__.__name__,
                entity_id=entity_id
            )
            return True
        return False

    def list_all(self) -> List[T]:
        """
        List all entities.

        Returns:
            List of all entities
        """
        return list(self._storage.values())

    def count(self) -> int:
        """
        Count total entities.

        Returns:
            Total count
        """
        return len(self._storage)

    def exists(self, entity_id: str) -> bool:
        """
        Check if entity exists.

        Args:
            entity_id: Unique identifier

        Returns:
            True if exists, False otherwise
        """
        return entity_id in self._storage

    def clear(self):
        """
        Clear all entities (use with caution!).

        Mainly for testing purposes.
        """
        count = len(self._storage)
        self._storage.clear()
        logger.warning(
            f"Repository cleared",
            repository=self.__class__.__name__,
            entities_removed=count
        )

    def find_by(self, **criteria) -> List[T]:
        """
        Find entities matching criteria.

        Generic implementation - subclasses should override for efficiency.

        Args:
            **criteria: Field-value pairs to match

        Returns:
            List of matching entities
        """
        results = []
        for entity in self._storage.values():
            match = True
            for key, value in criteria.items():
                if not hasattr(entity, key) or getattr(entity, key) != value:
                    match = False
                    break
            if match:
                results.append(entity)
        return results

    def find_one_by(self, **criteria) -> Optional[T]:
        """
        Find first entity matching criteria.

        Args:
            **criteria: Field-value pairs to match

        Returns:
            First matching entity or None
        """
        results = self.find_by(**criteria)
        return results[0] if results else None


class InMemoryDatabase:
    """
    Global in-memory database manager.

    In production, this would be replaced with actual database connection pool.

    Singleton pattern for shared storage across repositories.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._customers: Dict[str, Any] = {}
            self._appointments: Dict[str, Any] = {}
            self._services: Dict[str, Any] = {}
            self._campaigns: Dict[str, Any] = {}
            self._notifications: Dict[str, Any] = {}

            # Initialize with sample data
            self._init_sample_data()

            self._initialized = True
            logger.info("In-memory database initialized")

    def _init_sample_data(self):
        """Initialize with sample data for testing"""
        # Sample services
        from ..models.enums import ServiceCategory

        self._services = {
            "srv-001": {
                "service_id": "srv-001",
                "name": "Saç Kesimi",
                "category": ServiceCategory.HAIR.value,
                "price": 250.0,
                "duration_minutes": 60,
                "description": "Profesyonel saç kesimi"
            },
            "srv-002": {
                "service_id": "srv-002",
                "name": "Saç Boyama",
                "category": ServiceCategory.HAIR.value,
                "price": 500.0,
                "duration_minutes": 120,
                "description": "Saç boyama ve şekillendirme"
            },
            "srv-003": {
                "service_id": "srv-003",
                "name": "Manikür",
                "category": ServiceCategory.NAILS.value,
                "price": 150.0,
                "duration_minutes": 45,
                "description": "Profesyonel manikür"
            },
            "srv-004": {
                "service_id": "srv-004",
                "name": "Pedikür",
                "category": ServiceCategory.NAILS.value,
                "price": 180.0,
                "duration_minutes": 60,
                "description": "Profesyonel pedikür"
            },
            "srv-005": {
                "service_id": "srv-005",
                "name": "Keratin Bakımı",
                "category": ServiceCategory.HAIR.value,
                "price": 450.0,
                "duration_minutes": 90,
                "description": "Saç bakımı ve keratin tedavisi"
            }
        }

        logger.info(f"Initialized with {len(self._services)} sample services")

    def get_customers(self) -> Dict[str, Any]:
        """Get customers storage"""
        return self._customers

    def get_appointments(self) -> Dict[str, Any]:
        """Get appointments storage"""
        return self._appointments

    def get_services(self) -> Dict[str, Any]:
        """Get services storage"""
        return self._services

    def get_campaigns(self) -> Dict[str, Any]:
        """Get campaigns storage"""
        return self._campaigns

    def get_notifications(self) -> Dict[str, Any]:
        """Get notifications storage"""
        return self._notifications

    def reset(self):
        """Reset database (for testing)"""
        self._customers.clear()
        self._appointments.clear()
        self._services.clear()
        self._campaigns.clear()
        self._notifications.clear()
        self._init_sample_data()
        logger.warning("Database reset")


# Global database instance
db = InMemoryDatabase()
