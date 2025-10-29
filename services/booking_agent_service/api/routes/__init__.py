# services/booking_agent_service/api/routes/__init__.py

"""
API Routes - All 9 Tools exposed as REST endpoints
"""

from . import customer
from . import booking
from . import marketing
from . import notification

__all__ = [
    'customer',
    'booking',
    'marketing',
    'notification'
]
