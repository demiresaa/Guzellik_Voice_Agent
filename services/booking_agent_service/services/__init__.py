# services/booking_agent_service/services/__init__.py

"""
Service Layer - Business Logic for all 9 Tools

Architecture:
- Clean separation from data access (repositories)
- Clean separation from presentation (API routes)
- Business rules encapsulation
- LLM-friendly responses
"""

from .customer_service import (
    CustomerService,
    customer_service
)

from .booking_service import (
    BookingService,
    booking_service
)

from .marketing_service import (
    MarketingService,
    marketing_service
)

from .notification_service import (
    NotificationService,
    notification_service
)

__all__ = [
    # Customer Management (Tool #1-2)
    'CustomerService',
    'customer_service',

    # Booking Management (Tool #3-5)
    'BookingService',
    'booking_service',

    # Marketing & Sales (Tool #6-7)
    'MarketingService',
    'marketing_service',

    # Notifications & Payment (Tool #8-9)
    'NotificationService',
    'notification_service'
]
