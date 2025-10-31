# services/booking_agent_service/schemas/notification.py

"""
Pydantic schemas for Notification & Payment Tools.
Staff Engineer principle: External service integration, security, compliance.
"""

from pydantic import BaseModel, Field, validator, model_validator
from datetime import datetime
from typing import Optional, Dict, Any
import re


class SendSmsRequest(BaseModel):
    """
    Request schema for Tool #8: sendSmsNotification

    Security:
    - Rate limiting per phone number (prevent SMS bombing)
    - Phone number validation
    - Message content sanitization
    - GDPR/KVKK compliance check
    """

    phone_number: str = Field(
        ...,
        description="Recipient phone number",
        example="05551234567"
    )
    message_type: str = Field(
        ...,
        description="Message type: confirmation, reminder, cancellation, payment, feedback, promotional",
        example="confirmation"
    )
    template_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Data to fill SMS template (appointment details, etc.)"
    )
    customer_id: Optional[str] = Field(
        None,
        description="Customer ID for consent verification"
    )
    force_send: bool = Field(
        default=False,
        description="Force send even without explicit consent (for critical messages only)"
    )

    @validator('phone_number')
    def validate_phone(cls, v):
        """Sanitize and validate phone number"""
        cleaned = re.sub(r'\D', '', v)
        if not re.match(r'^(05\d{9}|5\d{9})$', cleaned):
            raise ValueError('Invalid Turkish phone number format')
        if len(cleaned) == 10 and cleaned.startswith('5'):
            cleaned = '0' + cleaned
        return cleaned

    @validator('message_type')
    def validate_message_type(cls, v):
        """Validate message type"""
        allowed_types = [
            'confirmation',
            'reminder',
            'cancellation',
            'payment',
            'feedback',
            'promotional',
            'birthday'
        ]
        if v.lower() not in allowed_types:
            raise ValueError(f'message_type must be one of {allowed_types}')
        return v.lower()

    @model_validator(mode='after')
    def validate_promotional_consent(self):
        """
        Promotional messages require explicit customer_id and consent check.

        Security: GDPR/KVKK compliance - no marketing without consent.
        """
        if self.message_type in ['promotional', 'birthday'] and not self.customer_id and not self.force_send:
            raise ValueError(
                'Promotional messages require customer_id for consent verification'
            )

        return self

    class Config:
        json_schema_extra = {
            "example": {
                "phone_number": "05551234567",
                "message_type": "confirmation",
                "template_data": {
                    "appointment_id": "APT-ABC12345",
                    "date": "30 Ekim Perşembe",
                    "time": "10:00",
                    "specialist": "Ayşe Hanım",
                    "service": "Saç Kesimi"
                },
                "customer_id": "cust-123",
                "force_send": False
            }
        }


class SendSmsResponse(BaseModel):
    """
    Response schema for SMS sending.

    Includes delivery tracking information.
    """

    success: bool = Field(..., description="SMS send success status")
    message: str = Field(
        ...,
        description="Human-readable result message for LLM"
    )
    sms_id: Optional[str] = Field(
        None,
        description="SMS provider's message ID (for tracking)"
    )
    delivery_status: Optional[str] = Field(
        None,
        description="Delivery status: sent, pending, failed"
    )
    cost: Optional[float] = Field(
        None,
        description="SMS cost (TRY) - for accounting"
    )
    error_code: Optional[str] = Field(
        None,
        description="Error code if sending failed"
    )
    error_detail: Optional[str] = Field(
        None,
        description="Detailed error message if failed"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Randevu onay mesajı başarıyla gönderildi.",
                "sms_id": "sms-xyz789",
                "delivery_status": "sent",
                "cost": 0.15,
                "error_code": None,
                "error_detail": None
            }
        }


class PaymentLink(BaseModel):
    """
    Payment link details.

    Security: Use one-time tokens, expiration times.
    """

    payment_id: str = Field(..., description="Unique payment request ID")
    payment_url: str = Field(..., description="Payment link URL")
    amount: float = Field(..., description="Payment amount (TRY)", gt=0)
    currency: str = Field(default="TRY", description="Currency code")

    # Security
    token: str = Field(..., description="One-time payment token")
    expires_at: datetime = Field(..., description="Link expiration time")
    is_expired: bool = Field(default=False, description="Whether link is expired")

    # Metadata
    appointment_id: str = Field(..., description="Associated appointment ID")
    customer_phone: str = Field(..., description="Customer phone number")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def check_expiration(self) -> bool:
        """Check if payment link is expired"""
        self.is_expired = datetime.utcnow() > self.expires_at
        return self.is_expired

    class Config:
        json_schema_extra = {
            "example": {
                "payment_id": "pay-abc123",
                "payment_url": "https://payment.example.com/pay/xyz789",
                "amount": 250.0,
                "currency": "TRY",
                "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "expires_at": "2025-10-30T18:00:00",
                "is_expired": False,
                "appointment_id": "APT-ABC12345",
                "customer_phone": "05551234567",
                "created_at": "2025-10-30T12:00:00"
            }
        }


class RequestPrepaymentRequest(BaseModel):
    """
    Request schema for Tool #9: requestPrepayment

    Security:
    - Validate appointment exists
    - Check appointment amount threshold
    - Verify customer identity
    """

    appointment_id: str = Field(
        ...,
        description="Appointment ID requiring prepayment",
        min_length=5,
        max_length=50
    )
    customer_phone: str = Field(
        ...,
        description="Customer phone number for verification",
        example="05551234567"
    )
    prepayment_percentage: float = Field(
        default=50.0,
        description="Percentage of total to charge as prepayment",
        ge=10,
        le=100
    )
    expiration_hours: int = Field(
        default=24,
        description="Hours until payment link expires",
        ge=1,
        le=72
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

    @validator('appointment_id')
    def sanitize_appointment_id(cls, v):
        """Prevent injection attacks"""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Invalid appointment_id format')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "appointment_id": "APT-ABC12345",
                "customer_phone": "05551234567",
                "prepayment_percentage": 50.0,
                "expiration_hours": 24
            }
        }


class RequestPrepaymentResponse(BaseModel):
    """
    Response schema for prepayment request.

    LLM-friendly with instructions for customer.
    """

    success: bool = Field(..., description="Operation success status")
    message: str = Field(
        ...,
        description="Human-readable message for LLM to communicate to customer"
    )
    payment_link: Optional[PaymentLink] = Field(
        None,
        description="Payment link details if request successful"
    )
    payment_instructions: Optional[str] = Field(
        None,
        description="Instructions for LLM to explain payment process to customer"
    )
    sms_sent: bool = Field(
        default=False,
        description="Whether payment link was sent via SMS"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Ön ödeme linki oluşturuldu ve SMS ile gönderildi. Toplam tutarın %50'si olan 250 TL'yi 24 saat içinde ödemeniz gerekiyor.",
                "payment_link": {
                    "payment_id": "pay-abc123",
                    "payment_url": "https://payment.example.com/pay/xyz789",
                    "amount": 250.0,
                    "currency": "TRY",
                    "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                    "expires_at": "2025-10-31T12:00:00",
                    "is_expired": False,
                    "appointment_id": "APT-ABC12345",
                    "customer_phone": "05551234567"
                },
                "payment_instructions": "Ödeme linkini telefonunuza SMS olarak gönderdik. Linke tıklayarak güvenli ödeme sayfasından kredi kartı veya banka kartı ile ödemenizi yapabilirsiniz. Link 24 saat geçerlidir.",
                "sms_sent": True
            }
        }


class NotificationHistory(BaseModel):
    """
    Notification history record for audit trail.

    Compliance: Track all customer communications.
    """

    notification_id: str = Field(..., description="Unique notification ID")
    customer_id: str = Field(..., description="Customer ID")
    customer_phone: str = Field(..., description="Customer phone number")
    notification_type: str = Field(..., description="Type of notification")
    channel: str = Field(..., description="Channel: sms, email, push")
    content: str = Field(..., description="Message content")
    status: str = Field(..., description="Delivery status")
    sent_at: datetime = Field(..., description="Send timestamp")
    delivered_at: Optional[datetime] = Field(None, description="Delivery timestamp")
    cost: Optional[float] = Field(None, description="Cost (TRY)")

    class Config:
        json_schema_extra = {
            "example": {
                "notification_id": "notif-001",
                "customer_id": "cust-123",
                "customer_phone": "05551234567",
                "notification_type": "confirmation",
                "channel": "sms",
                "content": "Randevunuz onaylandı. APT-ABC12345, 30 Ekim 10:00...",
                "status": "delivered",
                "sent_at": "2025-10-30T12:00:00",
                "delivered_at": "2025-10-30T12:00:05",
                "cost": 0.15
            }
        }
