# services/booking_agent_service/services/customer_service.py

"""
Customer Management Service - Tools #1-2
Staff Engineer principle: Clean business logic, LLM-friendly responses.

Tools Implemented:
- Tool #1: getCustomerInfoByPhone - Retrieve customer by phone number
- Tool #2: createOrUpdateCustomer - Create or update customer record
"""

from typing import Optional
from datetime import datetime
from ..models.customer import Customer
from ..models.enums import CustomerTier
from ..repositories.customer_repository import customer_repository
from ..repositories.booking_repository import booking_repository
from ..schemas.customer import (
    GetCustomerByPhoneRequest,
    CustomerCreateRequest,
    CustomerUpdateRequest,
    CustomerInfoResponse,
    CustomerOperationResponse
)
from ..utils.logger import get_logger
from ..utils.exceptions import ValidationError, NotFoundError

logger = get_logger(__name__)


class CustomerService:
    """
    Customer management business logic.

    Responsibilities:
    - Customer lookup and identification
    - Customer creation and updates
    - Customer data enrichment (appointments, preferences)
    - LLM-friendly response generation
    """

    def __init__(self):
        self.customer_repo = customer_repository
        self.booking_repo = booking_repository

    def _mask_phone_number(self, phone: str) -> str:
        """
        Mask phone number for privacy.

        Example: 05551234567 → 0555***4567

        Args:
            phone: Full phone number

        Returns:
            Masked phone number
        """
        if len(phone) >= 11:
            return f"{phone[:4]}***{phone[-4:]}"
        return phone

    def _mask_surname(self, surname: str) -> str:
        """
        Partially mask surname for privacy.

        Example: Yılmaz → Y***

        Args:
            surname: Full surname

        Returns:
            Masked surname
        """
        if len(surname) > 1:
            return f"{surname[0]}***"
        return surname

    def _build_customer_context(self, customer: Customer) -> str:
        """
        Build natural language context for LLM.

        This helps the LLM understand customer history and provide
        personalized service.

        Args:
            customer: Customer entity

        Returns:
            Natural language description
        """
        context_parts = []

        # Basic info
        context_parts.append(
            f"{customer.name} {customer.surname}, {customer.tier.value.upper()} tier müşteri"
        )

        # Appointment history
        if customer.total_appointments > 0:
            context_parts.append(
                f"{customer.total_appointments} randevusu var, "
                f"toplam {customer.total_spent:.0f} TL harcama yapmış"
            )
        else:
            context_parts.append("Yeni müşteri (henüz randevusu yok)")

        # Last visit
        if customer.last_visit:
            days_since = (datetime.utcnow() - customer.last_visit).days
            if days_since == 0:
                context_parts.append("Bugün randevusu var")
            elif days_since <= 7:
                context_parts.append(f"{days_since} gün önce geldi")
            elif days_since <= 30:
                context_parts.append(f"{days_since // 7} hafta önce geldi")
            else:
                context_parts.append(f"{days_since // 30} ay önce geldi")

        # Preferences
        if customer.preferred_specialists:
            specialists = ", ".join(customer.preferred_specialists[:2])
            context_parts.append(f"Tercih ettiği uzmanlar: {specialists}")

        if customer.preferred_services:
            services = ", ".join(customer.preferred_services[:2])
            context_parts.append(f"Sık yaptırdığı hizmetler: {services}")

        return ". ".join(context_parts) + "."

    def get_customer_info_by_phone(
        self,
        request: GetCustomerByPhoneRequest
    ) -> CustomerOperationResponse:
        """
        Tool #1: getCustomerInfoByPhone

        Retrieve customer information by phone number.
        Primary use case: Caller identification at start of conversation.

        Args:
            request: Phone number lookup request

        Returns:
            Customer operation response with info or not-found message

        Business Rules:
        - Returns last 3 appointments for context
        - Masks sensitive PII in response
        - Provides LLM-friendly description
        """
        logger.info(
            "Customer lookup by phone",
            phone=self._mask_phone_number(request.phone_number)
        )

        try:
            # Lookup customer
            customer = self.customer_repo.find_by_phone(request.phone_number)

            if not customer:
                # Customer not found - not an error, just new customer
                logger.info("Customer not found", phone=self._mask_phone_number(request.phone_number))
                return CustomerOperationResponse(
                    success=True,
                    message="Müşteri kaydı bulunamadı. Yeni müşteri olarak kaydedebiliriz.",
                    customer_id=None,
                    customer_info=None
                )

            # Get last 3 appointments for context
            last_appointments = self.booking_repo.get_last_n_appointments(
                customer.customer_id,
                n=3
            )

            last_3_appts = [
                {
                    "date": apt.start_time.strftime("%d %B %Y"),
                    "services": [s.name for s in apt.services],
                    "specialist": apt.services[0].specialist_name if apt.services else None,
                    "total": apt.total_price
                }
                for apt in last_appointments
            ]

            # Build response
            customer_info = CustomerInfoResponse(
                customer_id=customer.customer_id,
                phone_number=self._mask_phone_number(customer.phone_number),
                name=customer.name,
                surname=self._mask_surname(customer.surname),
                tier=customer.tier.value,
                total_appointments=customer.total_appointments,
                total_spent=customer.total_spent,
                loyalty_points=customer.loyalty_points,
                created_at=customer.created_at,
                last_visit=customer.last_visit,
                preferred_specialists=customer.preferred_specialists,
                preferred_services=customer.preferred_services,
                last_3_appointments=last_3_appts
            )

            # Build LLM-friendly message
            context_message = self._build_customer_context(customer)

            logger.audit(
                action="CUSTOMER_IDENTIFIED",
                customer_id=customer.customer_id,
                phone=self._mask_phone_number(request.phone_number)
            )

            return CustomerOperationResponse(
                success=True,
                message=f"Müşteri bulundu: {context_message}",
                customer_id=customer.customer_id,
                customer_info=customer_info
            )

        except Exception as e:
            logger.error("Error in customer lookup", error=str(e))
            return CustomerOperationResponse(
                success=False,
                message=f"Müşteri arama sırasında bir hata oluştu: {str(e)}",
                customer_id=None,
                customer_info=None
            )

    def create_or_update_customer(
        self,
        request: CustomerCreateRequest
    ) -> CustomerOperationResponse:
        """
        Tool #2: createOrUpdateCustomer

        Create a new customer or update existing customer information.

        Args:
            request: Customer creation/update request

        Returns:
            Customer operation response

        Business Rules:
        - If phone exists, updates existing customer
        - If phone is new, creates new customer
        - Validates all input fields
        - Logs for GDPR/KVKK compliance
        """
        logger.info(
            "Create or update customer",
            phone=self._mask_phone_number(request.phone_number),
            name=request.name
        )

        try:
            # Check if customer exists
            existing_customer = self.customer_repo.find_by_phone(request.phone_number)

            if existing_customer:
                # Update existing customer
                logger.info(
                    "Updating existing customer",
                    customer_id=existing_customer.customer_id
                )

                # Update fields
                existing_customer.name = request.name
                existing_customer.surname = request.surname
                if request.email:
                    existing_customer.email = request.email
                if request.birth_date:
                    existing_customer.birth_date = request.birth_date

                # Update consent flags
                existing_customer.sms_consent = request.sms_consent
                existing_customer.email_consent = request.email_consent
                existing_customer.marketing_consent = request.marketing_consent

                existing_customer.updated_at = datetime.utcnow()

                # Save
                self.customer_repo.update(existing_customer)

                logger.audit(
                    action="CUSTOMER_UPDATED",
                    customer_id=existing_customer.customer_id,
                    phone=self._mask_phone_number(request.phone_number)
                )

                return CustomerOperationResponse(
                    success=True,
                    message=f"Müşteri bilgileri güncellendi: {existing_customer.name} {existing_customer.surname}",
                    customer_id=existing_customer.customer_id,
                    customer_info=None
                )

            else:
                # Create new customer
                logger.info("Creating new customer")

                new_customer = Customer(
                    phone_number=request.phone_number,
                    name=request.name,
                    surname=request.surname,
                    email=request.email,
                    birth_date=request.birth_date,
                    sms_consent=request.sms_consent,
                    email_consent=request.email_consent,
                    marketing_consent=request.marketing_consent,
                    tier=CustomerTier.NEW,
                    total_appointments=0,
                    total_spent=0.0,
                    loyalty_points=0
                )

                # Save
                self.customer_repo.create(new_customer)

                logger.audit(
                    action="CUSTOMER_CREATED",
                    customer_id=new_customer.customer_id,
                    phone=self._mask_phone_number(request.phone_number)
                )

                return CustomerOperationResponse(
                    success=True,
                    message=f"Yeni müşteri kaydı oluşturuldu: {new_customer.name} {new_customer.surname}. Hoş geldiniz!",
                    customer_id=new_customer.customer_id,
                    customer_info=None
                )

        except ValidationError as e:
            logger.warning("Validation error in customer creation", error=e.message)
            return CustomerOperationResponse(
                success=False,
                message=f"Geçersiz müşteri bilgisi: {e.message}",
                customer_id=None,
                customer_info=None
            )

        except Exception as e:
            logger.error("Error in customer creation/update", error=str(e))
            return CustomerOperationResponse(
                success=False,
                message=f"Müşteri kaydı sırasında bir hata oluştu: {str(e)}",
                customer_id=None,
                customer_info=None
            )


# Global service instance
customer_service = CustomerService()
