# services/booking_agent_service/models/booking.py

"""
Booking/Appointment data model.
Staff Engineer principle: Comprehensive state management and business rules.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List
from .enums import AppointmentStatus, PaymentStatus
import uuid


@dataclass
class Service:
    """Service definition"""
    service_id: str
    name: str
    category: str
    duration_minutes: int
    price: float
    specialist_id: str
    specialist_name: str


@dataclass
class Appointment:
    """
    Appointment entity with full lifecycle management.

    Security considerations:
    - Audit trail for all state changes
    - Cancellation policies
    - Payment verification
    """

    appointment_id: str = field(default_factory=lambda: f"APT-{uuid.uuid4().hex[:8].upper()}")
    customer_id: str = ""
    customer_phone: str = field(metadata={"pii": True})

    # Scheduling
    appointment_date: datetime = field(default_factory=datetime.utcnow)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)

    # Services
    services: List[Service] = field(default_factory=list)
    total_duration_minutes: int = 0
    total_price: float = 0.0

    # Status
    status: AppointmentStatus = AppointmentStatus.PENDING
    payment_status: PaymentStatus = PaymentStatus.NOT_REQUIRED

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None

    # Notifications
    confirmation_sent: bool = False
    reminder_sent: bool = False

    # Notes
    customer_notes: Optional[str] = None
    staff_notes: Optional[str] = None

    def __post_init__(self):
        """Calculate totals"""
        self.calculate_totals()

    def calculate_totals(self):
        """Calculate total duration and price from services"""
        self.total_duration_minutes = sum(s.duration_minutes for s in self.services)
        self.total_price = sum(s.price for s in self.services)

        # Update end_time based on duration
        if self.start_time:
            self.end_time = self.start_time + timedelta(minutes=self.total_duration_minutes)

    def confirm(self):
        """Confirm the appointment"""
        if self.status != AppointmentStatus.PENDING:
            raise ValueError(f"Cannot confirm appointment in {self.status} status")

        self.status = AppointmentStatus.CONFIRMED
        self.confirmed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def cancel(self, reason: Optional[str] = None):
        """
        Cancel the appointment with business rules.

        Args:
            reason: Cancellation reason

        Raises:
            ValueError: If cancellation is not allowed
        """
        if self.status in [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED]:
            raise ValueError(f"Cannot cancel appointment in {self.status} status")

        # Check cancellation window (business rule)
        from ..config import settings
        hours_until_appointment = (self.start_time - datetime.utcnow()).total_seconds() / 3600

        if hours_until_appointment < settings.CANCELLATION_WINDOW_HOURS:
            raise ValueError(
                f"Cancellation must be at least {settings.CANCELLATION_WINDOW_HOURS} hours before appointment"
            )

        self.status = AppointmentStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        self.cancellation_reason = reason
        self.updated_at = datetime.utcnow()

    def complete(self):
        """Mark appointment as completed"""
        if self.status != AppointmentStatus.CONFIRMED:
            raise ValueError(f"Cannot complete appointment in {self.status} status")

        self.status = AppointmentStatus.COMPLETED
        self.updated_at = datetime.utcnow()

    def mark_no_show(self):
        """Mark customer as no-show"""
        if self.status != AppointmentStatus.CONFIRMED:
            raise ValueError(f"Cannot mark no-show for appointment in {self.status} status")

        self.status = AppointmentStatus.NO_SHOW
        self.updated_at = datetime.utcnow()

    def requires_prepayment(self) -> bool:
        """
        Check if appointment requires prepayment based on business rules.

        Returns:
            True if prepayment is required
        """
        from ..config import settings
        return self.total_price >= settings.PREPAYMENT_THRESHOLD_TRY

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "appointment_id": self.appointment_id,
            "customer_id": self.customer_id,
            "customer_phone": self.customer_phone,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "services": [
                {
                    "service_id": s.service_id,
                    "name": s.name,
                    "duration_minutes": s.duration_minutes,
                    "price": s.price,
                    "specialist_name": s.specialist_name
                }
                for s in self.services
            ],
            "total_duration_minutes": self.total_duration_minutes,
            "total_price": self.total_price,
            "status": self.status.value,
            "payment_status": self.payment_status.value,
            "created_at": self.created_at.isoformat(),
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None
        }
