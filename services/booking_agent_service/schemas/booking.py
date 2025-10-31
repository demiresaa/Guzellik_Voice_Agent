# services/booking_agent_service/schemas/booking.py

"""
Pydantic schemas for Booking Management API.
Staff Engineer principle: Complex business rules, time validation, conflict detection.
"""

from pydantic import BaseModel, Field, validator, model_validator
from datetime import datetime, date, time, timedelta
from typing import Optional, List
import re


class ServiceSelection(BaseModel):
    """
    Service selection for appointment booking.

    Security: Validate service IDs to prevent injection
    """

    service_name: str = Field(
        ...,
        description="Service name (e.g., 'Saç Kesimi', 'Manikür')",
        example="Saç Kesimi",
        min_length=2,
        max_length=100
    )
    category: Optional[str] = Field(
        None,
        description="Service category",
        example="hair"
    )
    specialist_name: Optional[str] = Field(
        None,
        description="Preferred specialist (e.g., 'Ayşe Hanım')",
        example="Ayşe Hanım"
    )

    @validator('service_name', 'specialist_name')
    def sanitize_text(cls, v):
        """Prevent XSS and injection attacks"""
        if v is None:
            return v
        if '<' in v or '>' in v or ';' in v or '--' in v:
            raise ValueError('Invalid characters detected')
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "service_name": "Saç Kesimi",
                "category": "hair",
                "specialist_name": "Ayşe Hanım"
            }
        }


class AvailableSlot(BaseModel):
    """
    Represents an available time slot.

    This is returned by checkAvailability tool.
    """

    start_time: datetime = Field(..., description="Slot start time")
    end_time: datetime = Field(..., description="Slot end time")
    specialist_id: str = Field(..., description="Specialist unique ID")
    specialist_name: str = Field(..., description="Specialist display name")
    duration_minutes: int = Field(..., description="Slot duration in minutes")

    class Config:
        json_schema_extra = {
            "example": {
                "start_time": "2025-10-30T10:00:00",
                "end_time": "2025-10-30T11:00:00",
                "specialist_id": "spec-001",
                "specialist_name": "Ayşe Hanım",
                "duration_minutes": 60
            }
        }


class CheckAvailabilityRequest(BaseModel):
    """
    Request schema for Tool #3: checkAvailability

    Security & Business Rules:
    - Cannot check availability for past dates
    - Date range must be reasonable (max 30 days)
    - Must specify at least one service
    """

    services: List[str] = Field(
        ...,
        description="List of service names to book",
        example=["Saç Kesimi", "Manikür"],
        min_items=1,
        max_items=5
    )
    specialist_name: Optional[str] = Field(
        None,
        description="Preferred specialist (if any)",
        example="Ayşe Hanım"
    )
    date_from: Optional[date] = Field(
        None,
        description="Start date for availability search (defaults to today)"
    )
    date_to: Optional[date] = Field(
        None,
        description="End date for availability search (defaults to +7 days)"
    )
    preferred_time: Optional[str] = Field(
        None,
        description="Preferred time of day: 'morning', 'afternoon', 'evening'",
        example="morning"
    )

    @validator('services')
    def validate_services(cls, v):
        """Sanitize service names"""
        sanitized = []
        for service in v:
            if '<' in service or '>' in service or ';' in service:
                raise ValueError('Invalid service name format')
            sanitized.append(service.strip())
        return sanitized

    @validator('date_from')
    def validate_date_from(cls, v):
        """Cannot search for past dates"""
        if v and v < date.today():
            raise ValueError('Cannot search availability for past dates')
        return v or date.today()

    @model_validator(mode='after')
    def validate_date_range(self):
        """Validate date range is reasonable"""
        date_from = self.date_from or date.today()
        date_to = self.date_to or (date_from + timedelta(days=7))

        if date_to < date_from:
            raise ValueError('date_to must be after date_from')

        if (date_to - date_from).days > 30:
            raise ValueError('Date range cannot exceed 30 days')

        self.date_from = date_from
        self.date_to = date_to
        return self

    @validator('preferred_time')
    def validate_preferred_time(cls, v):
        """Validate preferred time value"""
        if v and v.lower() not in ['morning', 'afternoon', 'evening', 'any']:
            raise ValueError("preferred_time must be 'morning', 'afternoon', 'evening' or 'any'")
        return v.lower() if v else None

    class Config:
        json_schema_extra = {
            "example": {
                "services": ["Saç Kesimi"],
                "specialist_name": "Ayşe Hanım",
                "date_from": "2025-10-30",
                "date_to": "2025-11-06",
                "preferred_time": "morning"
            }
        }


class CheckAvailabilityResponse(BaseModel):
    """
    Response schema for availability check.

    LLM-friendly format with natural language summary.
    """

    success: bool = Field(..., description="Operation success status")
    message: str = Field(
        ...,
        description="Human-readable message for LLM to use in conversation"
    )
    available_slots: List[AvailableSlot] = Field(
        default_factory=list,
        description="List of available time slots"
    )
    total_slots: int = Field(
        0,
        description="Total number of available slots found"
    )
    suggestions: Optional[str] = Field(
        None,
        description="Alternative suggestions if no slots available"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Ayşe Hanım için 5 müsait slot bulundu. En yakın: 30 Ekim Perşembe 10:00",
                "available_slots": [
                    {
                        "start_time": "2025-10-30T10:00:00",
                        "end_time": "2025-10-30T11:00:00",
                        "specialist_id": "spec-001",
                        "specialist_name": "Ayşe Hanım",
                        "duration_minutes": 60
                    }
                ],
                "total_slots": 5,
                "suggestions": None
            }
        }


class CreateAppointmentRequest(BaseModel):
    """
    Request schema for Tool #4: createAppointment

    Security & Business Rules:
    - Customer ID or phone must be provided
    - Cannot book in the past
    - Selected slot must be from checkAvailability results
    """

    customer_id: Optional[str] = Field(
        None,
        description="Customer unique ID (if known)"
    )
    customer_phone: str = Field(
        ...,
        description="Customer phone number",
        example="05551234567"
    )
    selected_slot: AvailableSlot = Field(
        ...,
        description="Selected time slot from checkAvailability"
    )
    services: List[ServiceSelection] = Field(
        ...,
        description="Services to book",
        min_items=1
    )
    customer_notes: Optional[str] = Field(
        None,
        description="Customer notes or special requests",
        max_length=500
    )

    @validator('customer_phone')
    def validate_phone(cls, v):
        """Sanitize phone number"""
        cleaned = re.sub(r'\D', '', v)
        if not re.match(r'^(05\d{9}|5\d{9})$', cleaned):
            raise ValueError('Invalid phone number format')
        if len(cleaned) == 10 and cleaned.startswith('5'):
            cleaned = '0' + cleaned
        return cleaned

    @validator('customer_notes')
    def sanitize_notes(cls, v):
        """Prevent XSS in notes"""
        if v and ('<' in v or '>' in v):
            raise ValueError('Invalid characters in notes')
        return v.strip() if v else None

    @model_validator(mode='after')
    def validate_appointment_time(self):
        """Cannot book appointments in the past"""
        if self.selected_slot and self.selected_slot.start_time < datetime.utcnow():
            raise ValueError('Cannot book appointments in the past')
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "customer_phone": "05551234567",
                "selected_slot": {
                    "start_time": "2025-10-30T10:00:00",
                    "end_time": "2025-10-30T11:00:00",
                    "specialist_id": "spec-001",
                    "specialist_name": "Ayşe Hanım",
                    "duration_minutes": 60
                },
                "services": [
                    {
                        "service_name": "Saç Kesimi",
                        "specialist_name": "Ayşe Hanım"
                    }
                ],
                "customer_notes": "Önden kısa, arkadan uzun lütfen"
            }
        }


class CreateAppointmentResponse(BaseModel):
    """
    Response schema for appointment creation.

    Includes confirmation code and payment information if needed.
    """

    success: bool = Field(..., description="Operation success status")
    message: str = Field(
        ...,
        description="Human-readable confirmation message for LLM"
    )
    appointment_id: Optional[str] = Field(
        None,
        description="Unique appointment confirmation code"
    )
    appointment_details: Optional[dict] = Field(
        None,
        description="Full appointment details"
    )
    total_price: Optional[float] = Field(
        None,
        description="Total appointment price (TRY)"
    )
    requires_prepayment: bool = Field(
        False,
        description="Whether prepayment is required"
    )
    payment_link: Optional[str] = Field(
        None,
        description="Payment link if prepayment required"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Randevunuz başarıyla oluşturuldu. Randevu Kodu: APT-ABC12345. 30 Ekim Perşembe 10:00'da Ayşe Hanım ile görüşeceksiniz.",
                "appointment_id": "APT-ABC12345",
                "total_price": 350.0,
                "requires_prepayment": False,
                "payment_link": None
            }
        }


class CancelAppointmentRequest(BaseModel):
    """
    Request schema for Tool #5: cancelAppointment

    Security: Require either appointment ID or phone + verification
    """

    appointment_id: Optional[str] = Field(
        None,
        description="Appointment confirmation code"
    )
    customer_phone: Optional[str] = Field(
        None,
        description="Customer phone number for verification"
    )
    cancellation_reason: Optional[str] = Field(
        None,
        description="Reason for cancellation",
        max_length=200
    )

    @validator('customer_phone')
    def validate_phone(cls, v):
        """Sanitize phone number"""
        if v is None:
            return v
        cleaned = re.sub(r'\D', '', v)
        if not re.match(r'^(05\d{9}|5\d{9})$', cleaned):
            raise ValueError('Invalid phone number format')
        if len(cleaned) == 10 and cleaned.startswith('5'):
            cleaned = '0' + cleaned
        return cleaned

    @model_validator(mode='after')
    def require_identification(self):
        """Must provide either appointment_id or customer_phone"""
        if not self.appointment_id and not self.customer_phone:
            raise ValueError('Must provide either appointment_id or customer_phone')
        return self

    @validator('cancellation_reason')
    def sanitize_reason(cls, v):
        """Prevent XSS"""
        if v and ('<' in v or '>' in v):
            raise ValueError('Invalid characters in reason')
        return v.strip() if v else None

    class Config:
        json_schema_extra = {
            "example": {
                "appointment_id": "APT-ABC12345",
                "customer_phone": "05551234567",
                "cancellation_reason": "Acil bir durum çıktı"
            }
        }


class CancelAppointmentResponse(BaseModel):
    """Response schema for appointment cancellation"""

    success: bool = Field(..., description="Operation success status")
    message: str = Field(
        ...,
        description="Human-readable message for LLM"
    )
    cancelled_appointment_id: Optional[str] = Field(
        None,
        description="ID of cancelled appointment"
    )
    refund_info: Optional[str] = Field(
        None,
        description="Refund information if prepayment was made"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Randevunuz başarıyla iptal edildi. Randevu Kodu: APT-ABC12345",
                "cancelled_appointment_id": "APT-ABC12345",
                "refund_info": None
            }
        }
