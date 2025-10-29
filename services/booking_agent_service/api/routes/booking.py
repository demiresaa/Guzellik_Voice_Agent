# services/booking_agent_service/api/routes/booking.py

"""
Booking Management API Routes - Tools #3-5
FastAPI endpoints with complex validation and business rules.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from ...schemas.booking import (
    CheckAvailabilityRequest,
    CheckAvailabilityResponse,
    CreateAppointmentRequest,
    CreateAppointmentResponse,
    CancelAppointmentRequest,
    CancelAppointmentResponse
)
from ...services.booking_service import booking_service
from ...security.auth import get_api_key
from ...utils.logger import get_logger
from ...utils.exceptions import ValidationError, ConflictError

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/booking",
    tags=["Booking Management"],
    dependencies=[Depends(get_api_key)]
)


@router.post(
    "/check-availability",
    response_model=CheckAvailabilityResponse,
    summary="Tool #3: Check Availability",
    description="Find available time slots for requested services"
)
async def check_availability(
    request: CheckAvailabilityRequest,
    api_key: Annotated[str, Depends(get_api_key)]
):
    """
    **Tool #3: checkAvailability**

    Complex availability algorithm:
    1. Match services to specialists
    2. Check specialist working hours
    3. Scan date range for conflicts
    4. Generate 30-minute time slots
    5. Filter by preferred time

    Returns:
    - List of available slots
    - Natural language summary
    - Suggestions if no slots available

    Performance:
    - Optimized for salon operations
    - Max 20 slots returned to prevent overwhelming
    """
    try:
        logger.info(
            "API: Check availability",
            endpoint="/api/booking/check-availability",
            services=request.services
        )

        response = booking_service.check_availability(request)

        return response

    except ValidationError as e:
        logger.warning("Validation error in check availability", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": e.message,
                "details": e.details
            }
        )

    except Exception as e:
        logger.error("API error in check availability", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Failed to check availability",
                "details": str(e)
            }
        )


@router.post(
    "/create",
    response_model=CreateAppointmentResponse,
    summary="Tool #4: Create Appointment",
    description="Create new appointment with conflict detection"
)
async def create_appointment(
    request: CreateAppointmentRequest,
    api_key: Annotated[str, Depends(get_api_key)]
):
    """
    **Tool #4: createAppointment**

    Critical business logic:
    - Customer existence verification
    - Race condition prevention (double-booking)
    - Time conflict detection
    - Prepayment threshold check (>500 TRY)
    - Automatic confirmation

    Security:
    - Customer verification
    - Atomic operation
    - Audit trail

    Returns:
    - Appointment confirmation code
    - Total price
    - Payment link if prepayment required
    """
    try:
        logger.info(
            "API: Create appointment",
            endpoint="/api/booking/create",
            customer_phone=request.customer_phone[-4:]
        )

        response = booking_service.create_appointment(request)

        return response

    except ConflictError as e:
        logger.warning("Conflict in create appointment", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "ConflictError",
                "message": e.message,
                "details": e.details
            }
        )

    except ValidationError as e:
        logger.warning("Validation error in create appointment", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": e.message,
                "details": e.details
            }
        )

    except Exception as e:
        logger.error("API error in create appointment", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Failed to create appointment",
                "details": str(e)
            }
        )


@router.post(
    "/cancel",
    response_model=CancelAppointmentResponse,
    summary="Tool #5: Cancel Appointment",
    description="Cancel appointment with business rules validation"
)
async def cancel_appointment(
    request: CancelAppointmentRequest,
    api_key: Annotated[str, Depends(get_api_key)]
):
    """
    **Tool #5: cancelAppointment**

    Business rules enforced:
    - 24-hour cancellation window (configurable)
    - Customer verification (security)
    - Status validation (can't cancel completed)
    - Refund processing if prepaid

    Returns:
    - Cancellation confirmation
    - Refund information if applicable
    """
    try:
        logger.info(
            "API: Cancel appointment",
            endpoint="/api/booking/cancel",
            appointment_id=request.appointment_id
        )

        response = booking_service.cancel_appointment(request)

        return response

    except ConflictError as e:
        logger.warning("Conflict in cancel appointment", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "ConflictError",
                "message": e.message,
                "details": e.details
            }
        )

    except ValidationError as e:
        logger.warning("Validation error in cancel appointment", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": e.message,
                "details": e.details
            }
        )

    except Exception as e:
        logger.error("API error in cancel appointment", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Failed to cancel appointment",
                "details": str(e)
            }
        )
