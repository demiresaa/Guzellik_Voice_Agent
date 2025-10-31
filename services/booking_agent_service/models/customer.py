# services/booking_agent_service/models/customer.py

"""
Customer data model.
Staff Engineer principle: Rich domain models with business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from .enums import CustomerTier
import uuid


@dataclass
class Customer:
    """
    Customer entity representing a salon customer.

    Security considerations:
    - PII (Personally Identifiable Information) handling
    - GDPR/KVKK compliance
    - Data retention policies
    """

    # Required fields (no defaults) must come first
    phone_number: str = field(metadata={"pii": True})  # Primary identifier
    name: str = field(metadata={"pii": True})
    surname: str = field(metadata={"pii": True})

    # Auto-generated ID
    customer_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Optional fields
    email: Optional[str] = field(default=None, metadata={"pii": True})
    birth_date: Optional[datetime] = field(default=None, metadata={"pii": True})
    address: Optional[str] = field(default=None, metadata={"pii": True})

    # Business fields
    tier: CustomerTier = CustomerTier.NEW
    total_appointments: int = 0
    total_spent: float = 0.0
    loyalty_points: int = 0

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_visit: Optional[datetime] = None
    notes: Optional[str] = None  # Staff notes (allergies, preferences, etc.)

    # Preferences
    preferred_specialists: List[str] = field(default_factory=list)
    preferred_services: List[str] = field(default_factory=list)

    # Marketing consent (GDPR/KVKK)
    sms_consent: bool = False
    email_consent: bool = False
    marketing_consent: bool = False

    def __post_init__(self):
        """Validate phone number format"""
        if not self.phone_number or len(self.phone_number) < 10:
            raise ValueError("Invalid phone number")

        # Update tier based on total appointments
        self.update_tier()

    def update_tier(self):
        """
        Update customer tier based on total appointments.
        Business logic encapsulated in the model.
        """
        if self.total_appointments >= 31:
            self.tier = CustomerTier.PLATINUM
        elif self.total_appointments >= 16:
            self.tier = CustomerTier.GOLD
        elif self.total_appointments >= 6:
            self.tier = CustomerTier.SILVER
        elif self.total_appointments >= 1:
            self.tier = CustomerTier.BRONZE
        else:
            self.tier = CustomerTier.NEW

    def add_appointment(self, amount: float):
        """
        Update customer stats after appointment.

        Args:
            amount: Appointment total amount
        """
        self.total_appointments += 1
        self.total_spent += amount
        self.last_visit = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.update_tier()

        # Calculate loyalty points (1 point per 10 TRY spent)
        self.loyalty_points += int(amount / 10)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "customer_id": self.customer_id,
            "phone_number": self.phone_number,
            "name": self.name,
            "surname": self.surname,
            "email": self.email,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "tier": self.tier.value,
            "total_appointments": self.total_appointments,
            "total_spent": self.total_spent,
            "loyalty_points": self.loyalty_points,
            "created_at": self.created_at.isoformat(),
            "last_visit": self.last_visit.isoformat() if self.last_visit else None,
            "preferred_specialists": self.preferred_specialists,
            "preferred_services": self.preferred_services
        }
