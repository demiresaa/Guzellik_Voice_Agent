# services/booking_agent_service/schemas/customer.py

"""
Pydantic schemas for Customer Management API.
Staff Engineer principle: Strict validation, clear documentation, security.
"""

from pydantic import BaseModel, Field, validator, EmailStr
from datetime import datetime
from typing import Optional, List
import re


class CustomerCreateRequest(BaseModel):
    """
    Request schema for creating a new customer.

    Security:
    - Input validation on all fields
    - Phone number sanitization
    - XSS prevention on text fields
    """

    phone_number: str = Field(
        ...,
        description="Customer phone number (Turkish format)",
        example="05551234567",
        min_length=10,
        max_length=15
    )
    name: str = Field(
        ...,
        description="Customer first name",
        example="Ayşe",
        min_length=2,
        max_length=50
    )
    surname: str = Field(
        ...,
        description="Customer last name",
        example="Yılmaz",
        min_length=2,
        max_length=50
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Customer email address",
        example="ayse@example.com"
    )
    birth_date: Optional[datetime] = Field(
        None,
        description="Customer birth date (for birthday campaigns)"
    )

    # Marketing consent (GDPR/KVKK compliance)
    sms_consent: bool = Field(
        default=False,
        description="Customer consent for SMS notifications"
    )
    email_consent: bool = Field(
        default=False,
        description="Customer consent for email notifications"
    )
    marketing_consent: bool = Field(
        default=False,
        description="Customer consent for marketing communications"
    )

    @validator('phone_number')
    def validate_phone_number(cls, v):
        """
        Validate and sanitize phone number.

        Security: Prevent SQL injection via phone number field
        """
        # Remove all non-digit characters
        cleaned = re.sub(r'\D', '', v)

        # Turkish mobile numbers start with 05 and have 11 digits
        if not re.match(r'^(05\d{9}|5\d{9})$', cleaned):
            raise ValueError('Invalid Turkish phone number format. Expected: 05XXXXXXXXX')

        # Normalize to 11 digits (05XXXXXXXXX)
        if len(cleaned) == 10 and cleaned.startswith('5'):
            cleaned = '0' + cleaned

        return cleaned

    @validator('name', 'surname')
    def validate_name(cls, v):
        """
        Validate and sanitize name fields.

        Security: Prevent XSS and code injection
        """
        # Remove any HTML/script tags
        if '<' in v or '>' in v or ';' in v:
            raise ValueError('Invalid characters in name')

        # Only allow letters, spaces, Turkish characters
        if not re.match(r'^[a-zA-ZğüşöçİĞÜŞÖÇ\s\-\']+$', v):
            raise ValueError('Name can only contain letters, spaces and hyphens')

        return v.strip().title()

    class Config:
        json_schema_extra = {
            "example": {
                "phone_number": "05551234567",
                "name": "Ayşe",
                "surname": "Yılmaz",
                "email": "ayse@example.com",
                "sms_consent": True,
                "email_consent": False,
                "marketing_consent": True
            }
        }


class CustomerUpdateRequest(BaseModel):
    """Request schema for updating customer information"""

    name: Optional[str] = Field(None, min_length=2, max_length=50)
    surname: Optional[str] = Field(None, min_length=2, max_length=50)
    email: Optional[EmailStr] = None
    birth_date: Optional[datetime] = None
    sms_consent: Optional[bool] = None
    email_consent: Optional[bool] = None
    marketing_consent: Optional[bool] = None

    @validator('name', 'surname')
    def validate_name(cls, v):
        """Same validation as create"""
        if v is None:
            return v
        if '<' in v or '>' in v or ';' in v:
            raise ValueError('Invalid characters in name')
        if not re.match(r'^[a-zA-ZğüşöçİĞÜŞÖÇ\s\-\']+$', v):
            raise ValueError('Name can only contain letters, spaces and hyphens')
        return v.strip().title()


class CustomerInfoResponse(BaseModel):
    """
    Response schema for customer information.

    Note: Excludes sensitive PII for security
    """

    customer_id: str = Field(..., description="Unique customer identifier")
    phone_number: str = Field(..., description="Customer phone number (masked)")
    name: str = Field(..., description="Customer first name")
    surname: str = Field(..., description="Customer last name")

    # Business data
    tier: str = Field(..., description="Customer loyalty tier")
    total_appointments: int = Field(..., description="Total number of appointments")
    total_spent: float = Field(..., description="Total amount spent (TRY)")
    loyalty_points: int = Field(..., description="Available loyalty points")

    # Dates
    created_at: datetime = Field(..., description="Account creation date")
    last_visit: Optional[datetime] = Field(None, description="Last appointment date")

    # Preferences
    preferred_specialists: List[str] = Field(
        default_factory=list,
        description="List of preferred specialist names"
    )
    preferred_services: List[str] = Field(
        default_factory=list,
        description="List of frequently used services"
    )

    # Recent appointments (for context)
    last_3_appointments: List[dict] = Field(
        default_factory=list,
        description="Last 3 appointments for conversation context"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "cust-123e4567",
                "phone_number": "0555***4567",  # Masked
                "name": "Ayşe",
                "surname": "Y***",  # Partially masked
                "tier": "gold",
                "total_appointments": 18,
                "total_spent": 4500.0,
                "loyalty_points": 450,
                "created_at": "2024-01-15T10:00:00Z",
                "last_visit": "2025-10-20T14:30:00Z",
                "preferred_specialists": ["Ceyda Hanım", "Ayşe Hanım"],
                "preferred_services": ["Saç Kesimi", "Manikür"],
                "last_3_appointments": []
            }
        }


class GetCustomerByPhoneRequest(BaseModel):
    """Request schema for Tool #1: getCustomerInfoByPhone"""

    phone_number: str = Field(
        ...,
        description="Phone number to lookup",
        example="05551234567"
    )

    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Sanitize phone number"""
        cleaned = re.sub(r'\D', '', v)
        if not re.match(r'^(05\d{9}|5\d{9})$', cleaned):
            raise ValueError('Invalid phone number format')
        if len(cleaned) == 10 and cleaned.startswith('5'):
            cleaned = '0' + cleaned
        return cleaned


class CustomerOperationResponse(BaseModel):
    """Generic response for customer operations"""

    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Human-readable message for LLM")
    customer_id: Optional[str] = Field(None, description="Customer ID if applicable")
    customer_info: Optional[CustomerInfoResponse] = Field(
        None,
        description="Customer information if retrieved"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Müşteri başarıyla bulundu. Ayşe Yılmaz, Gold tier müşteri, 18 randevusu var.",
                "customer_id": "cust-123e4567",
                "customer_info": {
                    "customer_id": "cust-123e4567",
                    "phone_number": "0555***4567",
                    "name": "Ayşe",
                    "surname": "Y***",
                    "tier": "gold",
                    "total_appointments": 18,
                    "total_spent": 4500.0,
                    "loyalty_points": 450,
                    "created_at": "2024-01-15T10:00:00Z",
                    "last_visit": "2025-10-20T14:30:00Z",
                    "preferred_specialists": ["Ceyda Hanım"],
                    "preferred_services": ["Saç Kesimi", "Manikür"],
                    "last_3_appointments": []
                }
            }
        }
