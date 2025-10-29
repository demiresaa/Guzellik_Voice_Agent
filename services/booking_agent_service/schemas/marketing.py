# services/booking_agent_service/schemas/marketing.py

"""
Pydantic schemas for Marketing & Sales Tools.
Staff Engineer principle: Revenue optimization, personalization, compliance.
"""

from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from typing import Optional, List
from enum import Enum


class ServiceSuggestion(BaseModel):
    """
    Complementary service suggestion.

    Business logic: Upselling and cross-selling opportunities.
    """

    service_id: str = Field(..., description="Unique service identifier")
    service_name: str = Field(..., description="Service display name")
    category: str = Field(..., description="Service category")
    description: str = Field(..., description="Service description for customer")
    price: float = Field(..., description="Service price (TRY)", ge=0)
    duration_minutes: int = Field(..., description="Service duration", gt=0)

    # Suggestion context
    suggestion_reason: str = Field(
        ...,
        description="Why this service is suggested (for LLM to explain to customer)"
    )
    discount_percent: Optional[float] = Field(
        None,
        description="Discount percentage if bundled",
        ge=0,
        le=100
    )
    bundle_price: Optional[float] = Field(
        None,
        description="Special bundle price if both services booked together"
    )

    # Popularity/Social proof
    popularity_score: Optional[int] = Field(
        None,
        description="How popular this service is (1-100)",
        ge=1,
        le=100
    )
    customers_who_booked: Optional[int] = Field(
        None,
        description="Number of customers who booked this combo"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "service_id": "srv-002",
                "service_name": "Keratin Bakımı",
                "category": "hair",
                "description": "Saçlarınızı yumuşatır ve parlaklık kazandırır",
                "price": 450.0,
                "duration_minutes": 90,
                "suggestion_reason": "Saç boyamanın ardından keratin bakımı, boyayı korur ve saçlarınızı daha sağlıklı gösterir.",
                "discount_percent": 20,
                "bundle_price": 360.0,
                "popularity_score": 85,
                "customers_who_booked": 143
            }
        }


class GetComplementaryServicesRequest(BaseModel):
    """
    Request schema for Tool #6: getComplementaryServiceSuggestions

    Security: Validate main service to prevent enumeration attacks
    """

    main_service: str = Field(
        ...,
        description="Main service that customer is booking",
        example="Saç Boyama",
        min_length=2,
        max_length=100
    )
    customer_id: Optional[str] = Field(
        None,
        description="Customer ID for personalized suggestions"
    )
    max_suggestions: int = Field(
        default=3,
        description="Maximum number of suggestions to return",
        ge=1,
        le=10
    )

    @validator('main_service')
    def sanitize_service(cls, v):
        """Prevent XSS and injection"""
        if '<' in v or '>' in v or ';' in v or '--' in v:
            raise ValueError('Invalid characters in service name')
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "main_service": "Saç Boyama",
                "customer_id": "cust-123",
                "max_suggestions": 3
            }
        }


class GetComplementaryServicesResponse(BaseModel):
    """
    Response schema for complementary service suggestions.

    LLM-friendly with natural language talking points.
    """

    success: bool = Field(..., description="Operation success status")
    message: str = Field(
        ...,
        description="Natural language summary for LLM to use in conversation"
    )
    suggestions: List[ServiceSuggestion] = Field(
        default_factory=list,
        description="List of suggested services"
    )
    total_savings: Optional[float] = Field(
        None,
        description="Total savings if all suggestions accepted (TRY)"
    )
    conversation_script: Optional[str] = Field(
        None,
        description="Suggested script for LLM to present offers naturally"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Saç boyamanın yanında 3 tamamlayıcı hizmet öneriyoruz. Paket halinde %20 indirimli!",
                "suggestions": [
                    {
                        "service_id": "srv-002",
                        "service_name": "Keratin Bakımı",
                        "category": "hair",
                        "description": "Saçlarınızı yumuşatır ve parlaklık kazandırır",
                        "price": 450.0,
                        "duration_minutes": 90,
                        "suggestion_reason": "Boyayı korur ve saçlarınızı sağlıklı gösterir",
                        "discount_percent": 20,
                        "bundle_price": 360.0,
                        "popularity_score": 85,
                        "customers_who_booked": 143
                    }
                ],
                "total_savings": 90.0,
                "conversation_script": "Bu arada, müşterilerimizin %80'i saç boyama sonrası keratin bakımı yaptırıyor. Hem boyayı koruyor hem de saçlarınız çok daha parlak oluyor. Bugün paket yaparsanız %20 indirimli, 360 TL yerine 288 TL. İlginizi çeker mi?"
            }
        }


class Campaign(BaseModel):
    """
    Active marketing campaign.

    Compliance: GDPR/KVKK - only show if customer has marketing consent.
    """

    campaign_id: str = Field(..., description="Unique campaign identifier")
    campaign_name: str = Field(..., description="Campaign display name")
    campaign_type: str = Field(
        ...,
        description="Campaign type: birthday, loyalty, seasonal, etc."
    )
    description: str = Field(..., description="Campaign description")

    # Discount details
    discount_type: str = Field(
        ...,
        description="Discount type: percentage, fixed_amount, free_service"
    )
    discount_value: float = Field(..., description="Discount value", ge=0)
    discount_display: str = Field(
        ...,
        description="Human-readable discount (e.g., '%20 indirim', '50 TL hediye')"
    )

    # Validity
    valid_from: datetime = Field(..., description="Campaign start date")
    valid_until: datetime = Field(..., description="Campaign end date")
    days_remaining: Optional[int] = Field(
        None,
        description="Days remaining until campaign expires"
    )

    # Conditions
    min_purchase: Optional[float] = Field(
        None,
        description="Minimum purchase amount to qualify (TRY)"
    )
    applicable_services: Optional[List[str]] = Field(
        None,
        description="Services this campaign applies to (None = all services)"
    )

    # Marketing copy
    urgency_message: Optional[str] = Field(
        None,
        description="Urgency message to encourage action"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "camp-001",
                "campaign_name": "Doğum Günü Özel",
                "campaign_type": "birthday",
                "description": "Doğum gününüze özel indirim",
                "discount_type": "percentage",
                "discount_value": 20,
                "discount_display": "%20 indirim",
                "valid_from": "2025-10-25T00:00:00",
                "valid_until": "2025-10-31T23:59:59",
                "days_remaining": 5,
                "min_purchase": None,
                "applicable_services": None,
                "urgency_message": "Son 5 gün! Doğum günü indirimi yakında sona eriyor."
            }
        }


class GetActiveCampaignsRequest(BaseModel):
    """
    Request schema for Tool #7: getActiveCampaignsForCustomer

    Security: Validate customer_id to prevent data leakage
    """

    customer_id: str = Field(
        ...,
        description="Customer unique identifier",
        min_length=5,
        max_length=50
    )
    include_expired: bool = Field(
        default=False,
        description="Include recently expired campaigns (for context)"
    )

    @validator('customer_id')
    def sanitize_customer_id(cls, v):
        """Prevent injection attacks"""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Invalid customer_id format')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "cust-123e4567",
                "include_expired": False
            }
        }


class GetActiveCampaignsResponse(BaseModel):
    """
    Response schema for active campaigns.

    LLM-friendly with promotional talking points.
    """

    success: bool = Field(..., description="Operation success status")
    message: str = Field(
        ...,
        description="Natural language summary for LLM"
    )
    campaigns: List[Campaign] = Field(
        default_factory=list,
        description="List of active campaigns for this customer"
    )
    total_potential_savings: Optional[float] = Field(
        None,
        description="Total potential savings if all campaigns used (TRY)"
    )
    conversation_script: Optional[str] = Field(
        None,
        description="Suggested script for LLM to present campaigns naturally"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Ayşe Hanım için 2 aktif kampanya bulundu. Toplam %20 + 50 TL tasarruf fırsatı!",
                "campaigns": [
                    {
                        "campaign_id": "camp-001",
                        "campaign_name": "Doğum Günü Özel",
                        "campaign_type": "birthday",
                        "description": "Doğum gününüze özel %20 indirim",
                        "discount_type": "percentage",
                        "discount_value": 20,
                        "discount_display": "%20 indirim",
                        "valid_from": "2025-10-25T00:00:00",
                        "valid_until": "2025-10-31T23:59:59",
                        "days_remaining": 5,
                        "urgency_message": "Son 5 gün!"
                    }
                ],
                "total_potential_savings": 120.0,
                "conversation_script": "Bu arada Ayşe Hanım, doğum gününüz yaklaşmış! Sizin için özel %20 indirim kampanyamız var. 31 Ekim'e kadar geçerli. Bu randevunuzda kullanmak ister misiniz?"
            }
        }
