# services/booking_agent_service/api/routes/customer.py

"""
Customer Management API Routes - Tools #1-2
FastAPI endpoints with security, validation, and error handling.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from ...schemas.customer import (
    GetCustomerByPhoneRequest,
    CustomerCreateRequest,
    CustomerOperationResponse
)
from ...services.customer_service import customer_service
from ...security.auth import get_api_key
from ...utils.logger import get_logger
from ...utils.exceptions import ValidationError, NotFoundError

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/customer",
    tags=["Customer Management"],
    dependencies=[Depends(get_api_key)]  # All routes require authentication
)


@router.post(
    "/get-by-phone",
    response_model=CustomerOperationResponse,
    summary="Tool #1: Get Customer Info by Phone",
    description="Retrieve customer information by phone number for caller identification"
)
async def get_customer_by_phone(
    request: GetCustomerByPhoneRequest,
    api_key: Annotated[str, Depends(get_api_key)]
):
    """
    **Tool #1: getCustomerInfoByPhone**

    Lookup customer by phone number. Primary use case: caller identification.

    Returns:
    - Customer information with last 3 appointments
    - Natural language summary for LLM
    - Null if customer not found (new customer)

    Security:
    - Requires API key authentication
    - PII masking in response
    - Audit logging
    """
    try:
        logger.info("API: Get customer by phone", endpoint="/api/customer/get-by-phone")

        response = customer_service.get_customer_info_by_phone(request)

        return response

    except Exception as e:
        logger.error("API error in get customer by phone", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Failed to retrieve customer information",
                "details": str(e)
            }
        )


@router.post(
    "/create-or-update",
    response_model=CustomerOperationResponse,
    summary="Tool #2: Create or Update Customer",
    description="Create new customer record or update existing customer information"
)
async def create_or_update_customer(
    request: CustomerCreateRequest,
    api_key: Annotated[str, Depends(get_api_key)]
):
    """
    **Tool #2: createOrUpdateCustomer**

    Create or update customer record.

    Smart behavior:
    - If phone exists → Updates information
    - If phone is new → Creates new customer with NEW tier

    GDPR/KVKK:
    - Tracks consent flags
    - Audit logging
    - Right to be forgotten support (future)

    Security:
    - Requires API key authentication
    - Input validation via Pydantic
    - Phone number sanitization
    """
    try:
        logger.info(
            "API: Create or update customer",
            endpoint="/api/customer/create-or-update",
            name=request.name
        )

        response = customer_service.create_or_update_customer(request)

        return response

    except ValidationError as e:
        logger.warning("Validation error in create customer", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": e.message,
                "details": e.details
            }
        )

    except Exception as e:
        logger.error("API error in create customer", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Failed to create/update customer",
                "details": str(e)
            }
        )
