# services/booking_agent_service/services/notification_service.py

"""
Notification & Payment Service - Tools #8-9
Staff Engineer principle: External service integration, rate limiting, compliance.

Tools Implemented:
- Tool #8: sendSmsNotification - Send SMS via external provider
- Tool #9: requestPrepayment - Generate payment link
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
from ..models.customer import Customer
from ..models.booking import Appointment
from ..models.enums import NotificationType
from ..repositories.customer_repository import customer_repository
from ..repositories.booking_repository import booking_repository
from ..repositories.base import db
from ..schemas.notification import (
    SendSmsRequest,
    SendSmsResponse,
    PaymentLink,
    RequestPrepaymentRequest,
    RequestPrepaymentResponse,
    NotificationHistory
)
from ..security.rate_limiter import rate_limiter
from ..config import settings
from ..utils.logger import get_logger
from ..utils.exceptions import RateLimitExceeded, ExternalServiceError, ValidationError

logger = get_logger(__name__)

# SMS Templates (in production, these would be in database/config)
SMS_TEMPLATES = {
    "confirmation": (
        "Randevunuz onaylandı! "
        "Kod: {appointment_id}. "
        "{date} {time}'da {specialist} ile görüşeceksiniz. "
        "Güzellik Merkezi"
    ),
    "reminder": (
        "Hatırlatma: Yarın {time}'da {specialist} ile randevunuz var. "
        "Kod: {appointment_id}. "
        "İptal için: 0555-XXX-XXXX"
    ),
    "cancellation": (
        "Randevunuz iptal edildi. "
        "Kod: {appointment_id}. "
        "Yeni randevu için: 0555-XXX-XXXX"
    ),
    "payment": (
        "Ödeme linkiniz: {payment_link}. "
        "Tutar: {amount} TL. "
        "{expiry_hours} saat içinde ödemenizi tamamlayın."
    ),
    "feedback": (
        "Hizmetimizden memnun kaldınız mı? "
        "Görüşlerinizi paylaşın: {feedback_link}"
    ),
    "promotional": (
        "{campaign_name}: {description}. "
        "{discount}. "
        "Detaylar: 0555-XXX-XXXX"
    ),
    "birthday": (
        "Doğum gününüz kutlu olsun {name}! "
        "Size özel %{discount} indirim hediyemiz. "
        "30 gün geçerli."
    )
}


class NotificationService:
    """
    Notification and payment business logic.

    Responsibilities:
    - SMS sending with templates
    - Rate limiting (SMS bombing prevention)
    - GDPR/KVKK consent checking
    - Payment link generation
    - Notification history tracking
    """

    def __init__(self):
        self.customer_repo = customer_repository
        self.booking_repo = booking_repository
        self.notifications_db = db.get_notifications()

    def _check_sms_consent(self, customer: Customer, message_type: str) -> bool:
        """
        Check if customer has given SMS consent.

        GDPR/KVKK compliance.

        Args:
            customer: Customer entity
            message_type: Type of message

        Returns:
            True if consent given or message is critical
        """
        # Critical messages (transactional) don't require consent
        critical_types = ["confirmation", "cancellation", "payment"]

        if message_type in critical_types:
            return True

        # Marketing messages require consent
        return customer.sms_consent and customer.marketing_consent

    async def _send_to_sms_provider(self, phone: str, message: str) -> Dict[str, Any]:
        """
        Send SMS via external provider.

        In production, this would call actual SMS API (Twilio, Vonage, etc.)

        Args:
            phone: Phone number
            message: Message content

        Returns:
            Provider response dict

        Raises:
            ExternalServiceError: If SMS provider fails
        """
        # Simulate external SMS provider call
        # In production:
        # response = requests.post(
        #     settings.SMS_PROVIDER_URL,
        #     headers={"Authorization": f"Bearer {settings.SMS_PROVIDER_API_KEY}"},
        #     json={"to": phone, "message": message}
        # )

        # Simulated response
        logger.info(
            "SMS sent (simulated)",
            phone=phone[-4:],  # Last 4 digits only
            message_length=len(message)
        )

        return {
            "sms_id": f"sms-{uuid.uuid4().hex[:8]}",
            "status": "sent",
            "cost": 0.15,  # Cost in TRY
            "delivered": True
        }

    def _save_notification_history(
        self,
        customer_id: str,
        customer_phone: str,
        notification_type: str,
        content: str,
        status: str,
        cost: Optional[float] = None
    ):
        """
        Save notification to history for audit trail.

        Args:
            customer_id: Customer ID
            customer_phone: Customer phone
            notification_type: Type of notification
            content: Message content
            status: Delivery status
            cost: Cost if applicable
        """
        history = NotificationHistory(
            notification_id=f"notif-{uuid.uuid4().hex[:8]}",
            customer_id=customer_id,
            customer_phone=customer_phone,
            notification_type=notification_type,
            channel="sms",
            content=content,
            status=status,
            sent_at=datetime.utcnow(),
            delivered_at=datetime.utcnow() if status == "delivered" else None,
            cost=cost
        )

        self.notifications_db[history.notification_id] = history.dict()

        logger.debug(
            "Notification history saved",
            notification_id=history.notification_id,
            type=notification_type
        )

    async def send_sms_notification(
        self,
        request: SendSmsRequest
    ) -> SendSmsResponse:
        """
        Tool #8: sendSmsNotification

        Send SMS notification to customer.

        Args:
            request: SMS send request

        Returns:
            SMS send response

        Business Rules:
        - Rate limiting: 10 SMS/hour per phone (bombing prevention)
        - GDPR/KVKK consent check for marketing messages
        - Template-based messages
        - Cost tracking
        - Delivery history
        """
        logger.info(
            "SMS send requested",
            phone=request.phone_number[-4:],
            message_type=request.message_type
        )

        try:
            # 1. Rate limiting check (SMS bombing prevention)
            try:
                await rate_limiter.check_phone_limit(
                    phone_number=request.phone_number,
                    max_requests=10,  # 10 SMS per hour
                    window_seconds=3600
                )
            except RateLimitExceeded as e:
                logger.warning(
                    "SMS rate limit exceeded",
                    phone=request.phone_number[-4:]
                )
                return SendSmsResponse(
                    success=False,
                    message=f"SMS gönderim limiti aşıldı. {e.message}",
                    error_code="RATE_LIMIT_EXCEEDED"
                )

            # 2. Get customer for consent check
            customer = None
            if request.customer_id:
                customer = self.customer_repo.get_by_id(request.customer_id)
            else:
                customer = self.customer_repo.find_by_phone(request.phone_number)

            # 3. Consent check (GDPR/KVKK)
            if customer and not request.force_send:
                if not self._check_sms_consent(customer, request.message_type):
                    logger.warning(
                        "SMS consent not given",
                        customer_id=customer.customer_id,
                        message_type=request.message_type
                    )
                    return SendSmsResponse(
                        success=False,
                        message="Müşteri SMS almak için izin vermemiş.",
                        error_code="CONSENT_NOT_GIVEN",
                        error_detail="GDPR/KVKK compliance: Customer has not given SMS consent"
                    )

            # 4. Build message from template
            template = SMS_TEMPLATES.get(request.message_type)
            if not template:
                return SendSmsResponse(
                    success=False,
                    message=f"Geçersiz mesaj tipi: {request.message_type}",
                    error_code="INVALID_MESSAGE_TYPE"
                )

            try:
                message = template.format(**request.template_data)
            except KeyError as e:
                return SendSmsResponse(
                    success=False,
                    message=f"Eksik template verisi: {e}",
                    error_code="MISSING_TEMPLATE_DATA"
                )

            # 5. Send via SMS provider
            try:
                provider_response = await self._send_to_sms_provider(
                    request.phone_number,
                    message
                )

                # 6. Save to history
                if customer:
                    self._save_notification_history(
                        customer_id=customer.customer_id,
                        customer_phone=request.phone_number,
                        notification_type=request.message_type,
                        content=message,
                        status="delivered" if provider_response["delivered"] else "failed",
                        cost=provider_response.get("cost")
                    )

                logger.audit(
                    action="SMS_SENT",
                    customer_id=customer.customer_id if customer else None,
                    phone=request.phone_number[-4:],
                    message_type=request.message_type,
                    cost=provider_response.get("cost")
                )

                return SendSmsResponse(
                    success=True,
                    message="SMS başarıyla gönderildi.",
                    sms_id=provider_response["sms_id"],
                    delivery_status=provider_response["status"],
                    cost=provider_response.get("cost")
                )

            except Exception as e:
                logger.error("SMS provider error", error=str(e))
                return SendSmsResponse(
                    success=False,
                    message="SMS gönderimi başarısız oldu.",
                    error_code="PROVIDER_ERROR",
                    error_detail=str(e)
                )

        except Exception as e:
            logger.error("Error in SMS sending", error=str(e))
            return SendSmsResponse(
                success=False,
                message=f"SMS gönderimi sırasında bir hata oluştu: {str(e)}",
                error_code="INTERNAL_ERROR"
            )

    async def request_prepayment(
        self,
        request: RequestPrepaymentRequest
    ) -> RequestPrepaymentResponse:
        """
        Tool #9: requestPrepayment

        Generate payment link for appointment prepayment.

        Args:
            request: Prepayment request

        Returns:
            Payment link response

        Business Rules:
        - Only for appointments above threshold (500 TRY)
        - Generates one-time secure token
        - Link expires in 24 hours (configurable)
        - SMS sent automatically with link
        - Payment tracked
        """
        logger.info(
            "Prepayment requested",
            appointment_id=request.appointment_id,
            phone=request.customer_phone[-4:]
        )

        try:
            # 1. Get appointment
            appointment = self.booking_repo.get_by_id(request.appointment_id)
            if not appointment:
                return RequestPrepaymentResponse(
                    success=False,
                    message="Randevu bulunamadı."
                )

            # 2. Verify customer
            if appointment.customer_phone != request.customer_phone:
                logger.warning(
                    "Prepayment request with wrong phone",
                    appointment_id=request.appointment_id
                )
                return RequestPrepaymentResponse(
                    success=False,
                    message="Bu randevu size ait değil."
                )

            # 3. Check if prepayment required
            if not appointment.requires_prepayment():
                return RequestPrepaymentResponse(
                    success=False,
                    message=f"Bu randevu için ön ödeme gerekmiyor. (Tutar: {appointment.total_price:.0f} TL)"
                )

            # 4. Calculate prepayment amount
            prepayment_amount = appointment.total_price * (request.prepayment_percentage / 100)

            # 5. Generate payment link (in production, this would call payment provider)
            # Simulate payment provider (Stripe, iyzico, etc.)
            payment_token = uuid.uuid4().hex
            payment_url = f"https://payment.guzelliksalonu.com/pay/{payment_token}"

            payment_link = PaymentLink(
                payment_id=f"pay-{uuid.uuid4().hex[:8]}",
                payment_url=payment_url,
                amount=prepayment_amount,
                currency="TRY",
                token=payment_token,
                expires_at=datetime.utcnow() + timedelta(hours=request.expiration_hours),
                is_expired=False,
                appointment_id=appointment.appointment_id,
                customer_phone=request.customer_phone
            )

            # 6. Send payment link via SMS
            sms_request = SendSmsRequest(
                phone_number=request.customer_phone,
                message_type="payment",
                template_data={
                    "payment_link": payment_url,
                    "amount": f"{prepayment_amount:.0f}",
                    "expiry_hours": request.expiration_hours
                },
                customer_id=appointment.customer_id,
                force_send=True  # Payment links are critical
            )

            sms_response = await self.send_sms_notification(sms_request)

            # 7. Payment instructions for LLM
            payment_instructions = (
                f"Ödeme linkini telefonunuza SMS olarak gönderdik. "
                f"Linke tıklayarak güvenli ödeme sayfasından kredi kartı veya banka kartı ile "
                f"ödemenizi yapabilirsiniz. Link {request.expiration_hours} saat geçerlidir."
            )

            logger.audit(
                action="PREPAYMENT_REQUESTED",
                appointment_id=appointment.appointment_id,
                payment_id=payment_link.payment_id,
                amount=prepayment_amount
            )

            return RequestPrepaymentResponse(
                success=True,
                message=(
                    f"Ön ödeme linki oluşturuldu ve SMS ile gönderildi. "
                    f"Toplam tutarın %{request.prepayment_percentage}'si olan {prepayment_amount:.0f} TL'yi "
                    f"{request.expiration_hours} saat içinde ödemeniz gerekiyor."
                ),
                payment_link=payment_link,
                payment_instructions=payment_instructions,
                sms_sent=sms_response.success
            )

        except Exception as e:
            logger.error("Error in prepayment request", error=str(e))
            return RequestPrepaymentResponse(
                success=False,
                message=f"Ön ödeme linki oluşturma sırasında bir hata oluştu: {str(e)}"
            )


# Global service instance
notification_service = NotificationService()
