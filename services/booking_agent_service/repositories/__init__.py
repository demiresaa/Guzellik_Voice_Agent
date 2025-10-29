# services/booking_agent_service/repositories/__init__.py

"""
Repository Layer - Data Access Abstraction

Pattern: Repository Pattern
Benefits:
- Separation of concerns
- Testability (mock repositories)
- Database independence
- Consistent interface
"""

from .base import (
    BaseRepository,
    InMemoryDatabase,
    db
)

from .customer_repository import (
    CustomerRepository,
    customer_repository
)

from .booking_repository import (
    BookingRepository,
    booking_repository
)

__all__ = [
    # Base
    'BaseRepository',
    'InMemoryDatabase',
    'db',

    # Customer
    'CustomerRepository',
    'customer_repository',

    # Booking
    'BookingRepository',
    'booking_repository'
]
