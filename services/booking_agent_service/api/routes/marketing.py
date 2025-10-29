# services/booking_agent_service/api/routes/marketing.py

"""
Marketing & Sales API Routes - Tools #6-7
FastAPI endpoints for revenue optimization.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from ...schemas.marketing import (
    GetComplementaryServicesRequest,
    GetComplementaryServicesResponse,
    GetActiveCampaignsRequest,
    GetActiveCampaignsResponse
)
from ...services.marketing_service import marketing_service
from ...security.auth import get_api_key
from ...utils.logger import get_logger
from ...utils.exceptions import ValidationError, NotFoundError

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/marketing",
    tags=["Marketing & Sales"],
    dependencies=[Depends(get_api_key)]
)


@router.post(
    "/suggestions",
    response_model=GetComplementaryServicesResponse,
    summary="Tool #6: Get Complementary Service Suggestions",
    description="Recommend complementary services for upselling (revenue optimization)"
)
async def get_complementary_suggestions(
    request: GetComplementaryServicesRequest,
    api_key: Annotated[str, Depends(get_api_key)]
):
    """
    **Tool #6: getComplementaryServiceSuggestions**

    Revenue optimization through intelligent upselling:
    - Data-driven service bundles
    - Discount calculations (15-25%)
    - Social proof (popularity scores)
    - Natural conversation scripts for LLM

    Example:
    - Main service: "Saç Boyama"
    - Suggestions: ["Keratin Bakımı" (20% off), "Saç Kesimi" (15% off)]

    Returns:
    - List of complementary services
    - Bundle pricing with discounts
    - Total savings calculation
    - Conversion-optimized script for LLM
    """
    try:
        logger.info(
            "API: Get complementary suggestions",
            endpoint="/api/marketing/suggestions",
            main_service=request.main_service
        )

        response = marketing_service.get_complementary_service_suggestions(request)

        return response

    except ValidationError as e:
        logger.warning("Validation error in get suggestions", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": e.message,
                "details": e.details
            }
        )

    except Exception as e:
        logger.error("API error in get suggestions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Failed to get service suggestions",
                "details": str(e)
            }
        )


@router.post(
    "/campaigns",
    response_model=GetActiveCampaignsResponse,
    summary="Tool #7: Get Active Campaigns for Customer",
    description="Get personalized active campaigns based on customer profile"
)
async def get_active_campaigns(
    request: GetActiveCampaignsRequest,
    api_key: Annotated[str, Depends(get_api_key)]
):
    """
    **Tool #7: getActiveCampaignsForCustomer**

    Personalized campaign targeting:
    - Birthday campaigns (±7 days from birthday)
    - Loyalty tier discounts (GOLD: 10%, PLATINUM: 15%, VIP: 20%)
    - First-time customer offers (15% off)
    - Seasonal campaigns (all customers)

    GDPR/KVKK Compliance:
    - Respects marketing consent
    - No campaigns shown if consent not given

    Returns:
    - List of applicable campaigns
    - Total potential savings
    - Promotional script for LLM
    - Urgency messages (scarcity principle)
    """
    try:
        logger.info(
            "API: Get active campaigns",
            endpoint="/api/marketing/campaigns",
            customer_id=request.customer_id
        )

        response = marketing_service.get_active_campaigns_for_customer(request)

        return response

    except NotFoundError as e:
        logger.warning("Customer not found in get campaigns", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "NotFoundError",
                "message": e.message,
                "details": e.details
            }
        )

    except ValidationError as e:
        logger.warning("Validation error in get campaigns", error=e.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": e.message,
                "details": e.details
            }
        )

    except Exception as e:
        logger.error("API error in get campaigns", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Failed to get campaigns",
                "details": str(e)
            }
        )
