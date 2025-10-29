# services/booking_agent_service/schemas/__init__.py

"""
Pydantic schemas for API request/response validation.
All schemas are type-safe, documented, and security-hardened.
"""

# Customer Management Schemas
from .customer import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    CustomerInfoResponse,
    GetCustomerByPhoneRequest,
    CustomerOperationResponse
)

# Booking Management Schemas
from .booking import (
    ServiceSelection,
    AvailableSlot,
    CheckAvailabilityRequest,
    CheckAvailabilityResponse,
    CreateAppointmentRequest,
    CreateAppointmentResponse,
    CancelAppointmentRequest,
    CancelAppointmentResponse
)

# Marketing & Sales Schemas
from .marketing import (
    ServiceSuggestion,
    GetComplementaryServicesRequest,
    GetComplementaryServicesResponse,
    Campaign,
    GetActiveCampaignsRequest,
    GetActiveCampaignsResponse
)

# Notification & Payment Schemas
from .notification import (
    SendSmsRequest,
    SendSmsResponse,
    PaymentLink,
    RequestPrepaymentRequest,
    RequestPrepaymentResponse,
    NotificationHistory
)

__all__ = [
    # Customer
    'CustomerCreateRequest',
    'CustomerUpdateRequest',
    'CustomerInfoResponse',
    'GetCustomerByPhoneRequest',
    'CustomerOperationResponse',

    # Booking
    'ServiceSelection',
    'AvailableSlot',
    'CheckAvailabilityRequest',
    'CheckAvailabilityResponse',
    'CreateAppointmentRequest',
    'CreateAppointmentResponse',
    'CancelAppointmentRequest',
    'CancelAppointmentResponse',

    # Marketing
    'ServiceSuggestion',
    'GetComplementaryServicesRequest',
    'GetComplementaryServicesResponse',
    'Campaign',
    'GetActiveCampaignsRequest',
    'GetActiveCampaignsResponse',

    # Notification
    'SendSmsRequest',
    'SendSmsResponse',
    'PaymentLink',
    'RequestPrepaymentRequest',
    'RequestPrepaymentResponse',
    'NotificationHistory'
]
