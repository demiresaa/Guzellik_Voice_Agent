# services/booking_agent_service/models/__init__.py

"""
Domain models representing business entities.
Rich models with business logic encapsulation.
"""

from .customer import Customer
from .booking import Appointment, Service
from .enums import (
    AppointmentStatus,
    ServiceCategory,
    PaymentStatus,
    NotificationType,
    CampaignType,
    CustomerTier,
    SpecialistRole
)

__all__ = [
    'Customer',
    'Appointment',
    'Service',
    'AppointmentStatus',
    'ServiceCategory',
    'PaymentStatus',
    'NotificationType',
    'CampaignType',
    'CustomerTier',
    'SpecialistRole'
]
