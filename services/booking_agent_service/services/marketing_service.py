# services/booking_agent_service/services/marketing_service.py

"""
Marketing & Sales Service - Tools #6-7
Staff Engineer principle: Revenue optimization, personalization, data-driven suggestions.

Tools Implemented:
- Tool #6: getComplementaryServiceSuggestions - Upselling and cross-selling
- Tool #7: getActiveCampaignsForCustomer - Personalized campaigns
"""

from typing import List, Optional
from datetime import datetime, timedelta
from ..models.customer import Customer
from ..models.enums import CampaignType, CustomerTier
from ..repositories.customer_repository import customer_repository
from ..repositories.base import db
from ..schemas.marketing import (
    ServiceSuggestion,
    GetComplementaryServicesRequest,
    GetComplementaryServicesResponse,
    Campaign,
    GetActiveCampaignsRequest,
    GetActiveCampaignsResponse
)
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Complementary service rules (data-driven in production)
SERVICE_BUNDLES = {
    "Saç Boyama": [
        {
            "service_id": "srv-005",
            "service_name": "Keratin Bakımı",
            "reason": "Saç boyamanın ardından keratin bakımı, boyayı korur ve saçlarınızı daha sağlıklı gösterir.",
            "discount_percent": 20,
            "popularity": 85
        },
        {
            "service_id": "srv-001",
            "service_name": "Saç Kesimi",
            "reason": "Yeni boyayla birlikte şekil vermeniz saçlarınızı daha modern gösterecektir.",
            "discount_percent": 15,
            "popularity": 70
        }
    ],
    "Saç Kesimi": [
        {
            "service_id": "srv-002",
            "service_name": "Saç Boyama",
            "reason": "Yeni kesinizle birlikte renk değişikliği tamamen yeni bir görünüm kazandırır.",
            "discount_percent": 15,
            "popularity": 65
        },
        {
            "service_id": "srv-005",
            "service_name": "Keratin Bakımı",
            "reason": "Kesim sonrası keratin, saçlarınızı besler ve parlak tutar.",
            "discount_percent": 20,
            "popularity": 60
        }
    ],
    "Manikür": [
        {
            "service_id": "srv-004",
            "service_name": "Pedikür",
            "reason": "Manikür ve pedikür birlikte yapılınca hem zamandan hem paradan tasarruf edersiniz.",
            "discount_percent": 25,
            "popularity": 90
        }
    ],
    "Pedikür": [
        {
            "service_id": "srv-003",
            "service_name": "Manikür",
            "reason": "Pedikürle birlikte manikür yaptırmak çok daha uygun fiyata gelir.",
            "discount_percent": 25,
            "popularity": 90
        }
    ]
}


class MarketingService:
    """
    Marketing and sales business logic.

    Responsibilities:
    - Complementary service recommendations (upselling)
    - Campaign management (personalized offers)
    - Customer segmentation for targeting
    - Conversion optimization
    """

    def __init__(self):
        self.customer_repo = customer_repository
        self.services_db = db.get_services()
        self.campaigns_db = db.get_campaigns()

    def _calculate_bundle_price(self, original_price: float, discount_percent: float) -> float:
        """
        Calculate bundle price with discount.

        Args:
            original_price: Original service price
            discount_percent: Discount percentage

        Returns:
            Discounted price
        """
        return original_price * (1 - discount_percent / 100)

    def _build_conversation_script(self, suggestions: List[ServiceSuggestion]) -> str:
        """
        Build natural conversation script for LLM.

        This helps the agent present offers in a natural, non-pushy way.

        Args:
            suggestions: Service suggestions

        Returns:
            Natural language script
        """
        if not suggestions:
            return ""

        top_suggestion = suggestions[0]

        script = (
            f"Bu arada, müşterilerimizin %{top_suggestion.popularity_score}'i "
            f"{top_suggestion.service_name.lower()} da yaptırıyor. "
            f"{top_suggestion.suggestion_reason} "
        )

        if top_suggestion.discount_percent:
            script += (
                f"Bugün paket yaparsanız %{top_suggestion.discount_percent} indirimli, "
                f"{top_suggestion.bundle_price:.0f} TL. İlginizi çeker mi?"
            )
        else:
            script += f"İlginizi çeker mi?"

        return script

    def get_complementary_service_suggestions(
        self,
        request: GetComplementaryServicesRequest
    ) -> GetComplementaryServicesResponse:
        """
        Tool #6: getComplementaryServiceSuggestions

        Recommend complementary services for upselling.

        Algorithm:
        1. Lookup service bundles (data-driven rules)
        2. Get service details (price, duration)
        3. Calculate bundle pricing with discounts
        4. Rank by popularity/conversion rate
        5. Generate natural conversation script

        Args:
            request: Service suggestion request

        Returns:
            Service suggestions response

        Business Rules:
        - Maximum 3 suggestions (avoid overwhelming)
        - Personalized based on customer tier (future)
        - Bundle discounts 15-25%
        - Social proof (popularity score)
        """
        logger.info(
            "Complementary services requested",
            main_service=request.main_service,
            customer_id=request.customer_id
        )

        try:
            # Get bundle rules for this service
            bundle_rules = SERVICE_BUNDLES.get(request.main_service, [])

            if not bundle_rules:
                logger.info(f"No bundles defined for: {request.main_service}")
                return GetComplementaryServicesResponse(
                    success=True,
                    message="Bu hizmet için özel paket önerimiz bulunmuyor.",
                    suggestions=[],
                    total_savings=0.0
                )

            # Build suggestions
            suggestions = []
            total_savings = 0.0

            for rule in bundle_rules[:request.max_suggestions]:
                # Get service details
                service = self.services_db.get(rule["service_id"])
                if not service:
                    continue

                original_price = service["price"]
                discount_percent = rule["discount_percent"]
                bundle_price = self._calculate_bundle_price(original_price, discount_percent)
                savings = original_price - bundle_price

                suggestion = ServiceSuggestion(
                    service_id=service["service_id"],
                    service_name=service["name"],
                    category=service["category"],
                    description=service["description"],
                    price=original_price,
                    duration_minutes=service["duration_minutes"],
                    suggestion_reason=rule["reason"],
                    discount_percent=discount_percent,
                    bundle_price=bundle_price,
                    popularity_score=rule["popularity"],
                    customers_who_booked=None  # Would be calculated from real data
                )

                suggestions.append(suggestion)
                total_savings += savings

            # Generate conversation script
            conversation_script = self._build_conversation_script(suggestions)

            # Build message
            if suggestions:
                message = (
                    f"{request.main_service} ile birlikte {len(suggestions)} tamamlayıcı hizmet öneriyoruz. "
                    f"Paket halinde toplam {total_savings:.0f} TL tasarruf!"
                )

                logger.info(
                    "Suggestions generated",
                    main_service=request.main_service,
                    suggestions_count=len(suggestions),
                    total_savings=total_savings
                )

                return GetComplementaryServicesResponse(
                    success=True,
                    message=message,
                    suggestions=suggestions,
                    total_savings=total_savings,
                    conversation_script=conversation_script
                )
            else:
                return GetComplementaryServicesResponse(
                    success=True,
                    message="Bu hizmet için özel paket önerimiz bulunmuyor.",
                    suggestions=[],
                    total_savings=0.0
                )

        except Exception as e:
            logger.error("Error generating service suggestions", error=str(e))
            return GetComplementaryServicesResponse(
                success=False,
                message=f"Öneri oluşturma sırasında bir hata oluştu: {str(e)}",
                suggestions=[],
                total_savings=0.0
            )

    def get_active_campaigns_for_customer(
        self,
        request: GetActiveCampaignsRequest
    ) -> GetActiveCampaignsResponse:
        """
        Tool #7: getActiveCampaignsForCustomer

        Get personalized active campaigns for a customer.

        Algorithm:
        1. Lookup customer
        2. Check marketing consent (GDPR/KVKK)
        3. Generate applicable campaigns:
           - Birthday campaigns (birth month)
           - Loyalty campaigns (tier-based)
           - First-time discounts (new customers)
           - Seasonal campaigns (all)
        4. Calculate potential savings
        5. Generate promotional script

        Args:
            request: Campaign lookup request

        Returns:
            Active campaigns response

        Business Rules:
        - Respect marketing consent
        - Birthday campaigns: ±7 days from birthday
        - Tier-based discounts
        - Campaign stacking rules
        """
        logger.info(
            "Active campaigns requested",
            customer_id=request.customer_id
        )

        try:
            # Get customer
            customer = self.customer_repo.get_by_id(request.customer_id)
            if not customer:
                return GetActiveCampaignsResponse(
                    success=False,
                    message="Müşteri bulunamadı.",
                    campaigns=[]
                )

            # Check marketing consent (GDPR/KVKK compliance)
            if not customer.marketing_consent:
                logger.info(
                    "Customer has not given marketing consent",
                    customer_id=customer.customer_id
                )
                return GetActiveCampaignsResponse(
                    success=True,
                    message="Kampanya bilgisi göstermek için izninize ihtiyacımız var.",
                    campaigns=[]
                )

            campaigns = []
            total_potential_savings = 0.0

            # 1. Birthday Campaign
            if customer.birth_date:
                today = datetime.utcnow().date()
                birth_month = customer.birth_date.month
                birth_day = customer.birth_date.day

                # Check if birthday is within next 30 days
                this_year_birthday = customer.birth_date.replace(year=today.year)
                days_until_birthday = (this_year_birthday - today).days

                if -7 <= days_until_birthday <= 30:  # 7 days before to 30 days after
                    campaign = Campaign(
                        campaign_id="camp-birthday",
                        campaign_name="Doğum Günü Özel",
                        campaign_type=CampaignType.BIRTHDAY.value,
                        description="Doğum gününüz için özel %20 indirim",
                        discount_type="percentage",
                        discount_value=20,
                        discount_display="%20 indirim",
                        valid_from=datetime.utcnow() - timedelta(days=7),
                        valid_until=this_year_birthday + timedelta(days=30),
                        days_remaining=max(0, (this_year_birthday + timedelta(days=30) - today).days),
                        min_purchase=None,
                        applicable_services=None,
                        urgency_message=f"Doğum günü indirimi {days_until_birthday} gün sonra sona eriyor!" if days_until_birthday > 0 else "Son günler! Doğum günü indirimi yakında sona eriyor."
                    )
                    campaigns.append(campaign)
                    total_potential_savings += 100.0  # Estimated

            # 2. Loyalty Campaign (Tier-based)
            if customer.tier in [CustomerTier.GOLD, CustomerTier.PLATINUM, CustomerTier.VIP]:
                discount_map = {
                    CustomerTier.GOLD: 10,
                    CustomerTier.PLATINUM: 15,
                    CustomerTier.VIP: 20
                }

                discount = discount_map[customer.tier]

                campaign = Campaign(
                    campaign_id=f"camp-loyalty-{customer.tier.value}",
                    campaign_name=f"{customer.tier.value.upper()} Müşteri Ayrıcalığı",
                    campaign_type=CampaignType.LOYALTY.value,
                    description=f"{customer.tier.value.upper()} tier müşterilerimize özel indirim",
                    discount_type="percentage",
                    discount_value=discount,
                    discount_display=f"%{discount} indirim",
                    valid_from=datetime.utcnow() - timedelta(days=365),
                    valid_until=datetime.utcnow() + timedelta(days=365),
                    days_remaining=365,
                    min_purchase=None,
                    applicable_services=None,
                    urgency_message=None
                )
                campaigns.append(campaign)
                total_potential_savings += 50.0  # Estimated

            # 3. First-Time Customer Discount
            if customer.tier == CustomerTier.NEW and customer.total_appointments == 0:
                campaign = Campaign(
                    campaign_id="camp-first-time",
                    campaign_name="Hoş Geldin İndirimi",
                    campaign_type=CampaignType.FIRST_TIME.value,
                    description="İlk randevunuzda özel indirim",
                    discount_type="percentage",
                    discount_value=15,
                    discount_display="%15 indirim",
                    valid_from=customer.created_at,
                    valid_until=customer.created_at + timedelta(days=30),
                    days_remaining=(customer.created_at + timedelta(days=30) - datetime.utcnow()).days,
                    min_purchase=None,
                    applicable_services=None,
                    urgency_message="İlk randevu indirimi 30 gün geçerli!"
                )
                campaigns.append(campaign)
                total_potential_savings += 75.0

            # 4. Seasonal Campaign (All customers)
            # Example: Winter campaign
            today = datetime.utcnow()
            if today.month in [11, 12, 1, 2]:  # Winter months
                campaign = Campaign(
                    campaign_id="camp-seasonal-winter",
                    campaign_name="Kış Bakımı Kampanyası",
                    campaign_type=CampaignType.SEASONAL.value,
                    description="Kış aylarında cilt ve saç bakımı paketlerinde indirim",
                    discount_type="percentage",
                    discount_value=10,
                    discount_display="%10 indirim",
                    valid_from=datetime(today.year, 11, 1),
                    valid_until=datetime(today.year + 1, 2, 28),
                    days_remaining=(datetime(today.year + 1, 2, 28) - today).days,
                    min_purchase=200.0,
                    applicable_services=["Saç Bakımı", "Cilt Bakımı"],
                    urgency_message=None
                )
                campaigns.append(campaign)
                total_potential_savings += 30.0

            # Generate conversation script
            conversation_script = None
            if campaigns:
                top_campaign = campaigns[0]
                conversation_script = (
                    f"Bu arada {customer.name} Hanım, sizin için {len(campaigns)} aktif kampanyamız var. "
                    f"{top_campaign.campaign_name}: {top_campaign.description}. "
                )
                if top_campaign.urgency_message:
                    conversation_script += top_campaign.urgency_message + " "
                conversation_script += "Bu randevunuzda kullanmak ister misiniz?"

            # Build message
            if campaigns:
                message = (
                    f"{customer.name} Hanım için {len(campaigns)} aktif kampanya bulundu. "
                    f"Toplam {total_potential_savings:.0f} TL tasarruf fırsatı!"
                )

                logger.info(
                    "Campaigns generated",
                    customer_id=customer.customer_id,
                    campaigns_count=len(campaigns)
                )

                return GetActiveCampaignsResponse(
                    success=True,
                    message=message,
                    campaigns=campaigns,
                    total_potential_savings=total_potential_savings,
                    conversation_script=conversation_script
                )
            else:
                return GetActiveCampaignsResponse(
                    success=True,
                    message="Şu anda aktif kampanya bulunmuyor.",
                    campaigns=[],
                    total_potential_savings=0.0
                )

        except Exception as e:
            logger.error("Error getting campaigns", error=str(e))
            return GetActiveCampaignsResponse(
                success=False,
                message=f"Kampanya bilgisi alınırken bir hata oluştu: {str(e)}",
                campaigns=[]
            )


# Global service instance
marketing_service = MarketingService()
