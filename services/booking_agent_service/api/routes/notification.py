# services/booking_agent_service/api/routes/notification.py

"""
Notification & Payment API Routes - Tools #8-9
FastAPI endpoints for external service integration.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from ...schemas.notification import (
    SendSmsRequest,
    SendSmsResponse,
    RequestPrepaymentRequest,
    RequestPrepaymentResponse
)
from ...services.notification_service import notification_service
from ...security.auth import get_api_key
from ...utils.logger import get_logger
from ...utils.exceptions import ValidationError, RateLimitExceeded

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/notification",
    tags=["Notifications & Payment"],
    dependencies=[Depends(get_api_key)]
)


@router.post(
    "/send-sms",
    response_model=SendSmsResponse,
    summary="Tool #8: Send SMS Notification",
    description="Send SMS notification via external provider (Twilio, Vonage, etc.)"
)
async def send_sms(
    request: SendSmsRequest,
    api_key: Annotated[str, Depends(get_api_key)]
):
    """
    **Tool #8: sendSmsNotification**

    SMS sending with enterprise features:
    - Template-based messages (7 types)
    - Rate limiting (10 SMS/hour per phone - SMS bombing prevention)
    - GDPR/KVKK consent checking
    - Delivery tracking
    - Cost tracking for accounting

    Message Types:
    - confirmation: Appointment confirmed
    - reminder: Appointment reminder (24h before)
    - cancellation: Appointment cancelled
    - payment: Payment link
    - feedback: Feedback request
    - promotional: Marketing campaign
    - birthday: Birthday wishes

    Security:
    - Rate limiting per phone number
    - Consent verification for marketing messages
    - Audit logging (compliance)
    - SMS bombing prevention

    Returns:
    - Delivery status
    - SMS ID for tracking
    - Cost (for accounting)
    """
    try:
        logger.info(
            "API: Send SMS",
            endpoint="/api/notification/send-sms",
            message_type=request.message_type
        )

        response = await notification_service.send_sms_notification(request)

        return response

    except RateLimitExceeded as e:
        logger.warning("Rate limit exceeded in send SMS", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RateLimitExceeded",
                "message": e.message,
                "details": e.details
            },
            headers={"Retry-After": str(e.details.get("retry_after", 60))}
        )

    except ValidationError as e:
        logger.warning("Validation error in send SMS", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": e.message,
                "details": e.details
            }
        )

    except Exception as e:
        logger.error("API error in send SMS", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Failed to send SMS",
                "details": str(e)
            }
        )


@router.post(
    "/prepayment",
    response_model=RequestPrepaymentResponse,
    summary="Tool #9: Request Prepayment",
    description="Generate secure payment link for appointment prepayment"
)
async def request_prepayment(
    request: RequestPrepaymentRequest,
    api_key: Annotated[str, Depends(get_api_key)]
):
    """
    **Tool #9: requestPrepayment**

    Payment link generation for prepayments:
    - Secure one-time tokens
    - Configurable expiration (default: 24 hours)
    - Automatic SMS delivery
    - Payment tracking

    Business Rules:
    - Only for appointments above threshold (500 TRY)
    - Configurable prepayment percentage (default: 50%)
    - Link expires after X hours
    - Customer verification (security)

    Integration:
    - Supports Stripe, iyzico, PayTR, etc.
    - Webhook support for payment confirmation (future)
    - Refund processing (future)

    Security:
    - One-time use tokens
    - Time-limited links
    - Customer phone verification
    - Payment status tracking

    Returns:
    - Payment link URL
    - Payment token
    - Expiration time
    - SMS delivery status
    """
    try:
        logger.info(
            "API: Request prepayment",
            endpoint="/api/notification/prepayment",
            appointment_id=request.appointment_id
        )

        response = await notification_service.request_prepayment(request)

        return response

    except ValidationError as e:
        logger.warning("Validation error in request prepayment", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": e.message,
                "details": e.details
            }
        )

    except Exception as e:
        logger.error("API error in request prepayment", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Failed to request prepayment",
                "details": str(e)
            }
        )
