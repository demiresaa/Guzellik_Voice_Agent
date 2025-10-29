# services/booking_agent_service/services/booking_service.py

"""
Booking Management Service - Tools #3-5
Staff Engineer principle: Complex algorithms, conflict detection, business rules.

Tools Implemented:
- Tool #3: checkAvailability - Find available time slots
- Tool #4: createAppointment - Create new appointment with validation
- Tool #5: cancelAppointment - Cancel appointment with business rules
"""

from typing import List, Optional
from datetime import datetime, date, time, timedelta
from ..models.booking import Appointment, Service
from ..models.customer import Customer
from ..models.enums import AppointmentStatus, PaymentStatus, ServiceCategory
from ..repositories.booking_repository import booking_repository
from ..repositories.customer_repository import customer_repository
from ..repositories.base import db
from ..schemas.booking import (
    AvailableSlot,
    CheckAvailabilityRequest,
    CheckAvailabilityResponse,
    CreateAppointmentRequest,
    CreateAppointmentResponse,
    CancelAppointmentRequest,
    CancelAppointmentResponse
)
from ..config import settings
from ..utils.logger import get_logger
from ..utils.exceptions import ValidationError, NotFoundError, ConflictError

logger = get_logger(__name__)

# Specialist working hours and info (in production, this would be in database)
SPECIALISTS = {
    "Ayşe Hanım": {
        "specialist_id": "spec-001",
        "role": "hair_stylist",
        "services": ["Saç Kesimi", "Saç Boyama", "Keratin Bakımı"],
        "working_hours": (9, 18),  # 9 AM to 6 PM
        "working_days": [0, 1, 2, 3, 4, 5]  # Monday-Saturday
    },
    "Ceyda Hanım": {
        "specialist_id": "spec-002",
        "role": "beautician",
        "services": ["Manikür", "Pedikür", "Cilt Bakımı"],
        "working_hours": (10, 19),
        "working_days": [0, 1, 2, 3, 4]  # Monday-Friday
    },
    "Fatma Hanım": {
        "specialist_id": "spec-003",
        "role": "hair_stylist",
        "services": ["Saç Kesimi", "Saç Boyama", "Makyaj"],
        "working_hours": (9, 17),
        "working_days": [1, 2, 3, 4, 5]  # Tuesday-Saturday
    }
}


class BookingService:
    """
    Booking management business logic.

    Responsibilities:
    - Availability checking (complex time-based algorithms)
    - Appointment creation with conflict detection
    - Cancellation with business rules
    - Service matching and recommendations
    """

    def __init__(self):
        self.booking_repo = booking_repository
        self.customer_repo = customer_repository
        self.services_db = db.get_services()

    def _get_service_details(self, service_name: str) -> Optional[dict]:
        """
        Get service details from database.

        Args:
            service_name: Service name to lookup

        Returns:
            Service details dict or None
        """
        for service in self.services_db.values():
            if service["name"].lower() == service_name.lower():
                return service
        return None

    def _find_specialist_for_service(self, service_name: str, preferred: Optional[str] = None) -> Optional[str]:
        """
        Find appropriate specialist for a service.

        Args:
            service_name: Service to book
            preferred: Preferred specialist name (optional)

        Returns:
            Specialist name or None
        """
        # If preferred specialist can do this service, return them
        if preferred and preferred in SPECIALISTS:
            if service_name in SPECIALISTS[preferred]["services"]:
                return preferred

        # Find any specialist who can do this service
        for specialist_name, specialist_info in SPECIALISTS.items():
            if service_name in specialist_info["services"]:
                return specialist_name

        return None

    def _format_date_turkish(self, dt: datetime) -> str:
        """
        Format date in Turkish.

        Args:
            dt: Datetime to format

        Returns:
            Turkish formatted string (e.g., "30 Ekim Perşembe")
        """
        turkish_months = [
            "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
        ]
        turkish_days = [
            "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"
        ]

        day = dt.day
        month = turkish_months[dt.month - 1]
        weekday = turkish_days[dt.weekday()]

        return f"{day} {month} {weekday}"

    def _is_specialist_working(self, specialist_name: str, target_date: date) -> bool:
        """
        Check if specialist is working on given date.

        Args:
            specialist_name: Specialist name
            target_date: Date to check

        Returns:
            True if working, False otherwise
        """
        if specialist_name not in SPECIALISTS:
            return False

        specialist_info = SPECIALISTS[specialist_name]
        weekday = target_date.weekday()

        return weekday in specialist_info["working_days"]

    def check_availability(
        self,
        request: CheckAvailabilityRequest
    ) -> CheckAvailabilityResponse:
        """
        Tool #3: checkAvailability

        Find available time slots for requested services.

        Algorithm:
        1. Identify which specialists can provide services
        2. For each day in date range:
           - Check if specialist is working
           - Get existing appointments
           - Calculate available slots (30-min intervals)
           - Filter by preferred time if specified
        3. Return sorted list of slots

        Args:
            request: Availability check request

        Returns:
            Available slots response

        Business Rules:
        - Minimum 30-minute slots
        - No past dates
        - Respect specialist working hours
        - Account for existing appointments
        """
        logger.info(
            "Availability check requested",
            services=request.services,
            specialist=request.specialist_name,
            date_from=request.date_from.isoformat(),
            date_to=request.date_to.isoformat()
        )

        try:
            available_slots = []

            # Calculate total duration needed
            total_duration = 0
            service_details = []

            for service_name in request.services:
                service = self._get_service_details(service_name)
                if service:
                    total_duration += service["duration_minutes"]
                    service_details.append(service)
                else:
                    logger.warning(f"Service not found: {service_name}")

            if not service_details:
                return CheckAvailabilityResponse(
                    success=False,
                    message=f"Belirtilen hizmetler bulunamadı: {', '.join(request.services)}",
                    available_slots=[],
                    total_slots=0,
                    suggestions="Lütfen geçerli bir hizmet adı belirtin."
                )

            # Find appropriate specialist(s)
            specialists_to_check = []

            if request.specialist_name:
                # Check if preferred specialist can do all services
                can_do_all = all(
                    service["name"] in SPECIALISTS.get(request.specialist_name, {}).get("services", [])
                    for service in service_details
                )
                if can_do_all:
                    specialists_to_check = [request.specialist_name]
                else:
                    return CheckAvailabilityResponse(
                        success=False,
                        message=f"{request.specialist_name} istenen hizmetleri sağlayamıyor.",
                        available_slots=[],
                        total_slots=0,
                        suggestions="Farklı bir uzman seçebilir veya hizmetleri ayrı randevulara bölebilirsiniz."
                    )
            else:
                # Find any specialist who can do first service (simplification)
                specialist = self._find_specialist_for_service(service_details[0]["name"])
                if specialist:
                    specialists_to_check = [specialist]

            if not specialists_to_check:
                return CheckAvailabilityResponse(
                    success=False,
                    message="Bu hizmetler için uygun uzman bulunamadı.",
                    available_slots=[],
                    total_slots=0
                )

            # Iterate through date range
            current_date = request.date_from
            while current_date <= request.date_to:
                for specialist_name in specialists_to_check:
                    # Check if specialist is working this day
                    if not self._is_specialist_working(specialist_name, current_date):
                        continue

                    # Get working hours
                    working_hours = SPECIALISTS[specialist_name]["working_hours"]

                    # Find available slots for this day
                    slots = self.booking_repo.find_available_slots(
                        specialist_name=specialist_name,
                        target_date=current_date,
                        duration_minutes=total_duration,
                        working_hours=working_hours
                    )

                    # Convert to schema objects
                    for slot in slots:
                        # Filter by preferred time if specified
                        if request.preferred_time:
                            hour = slot["start"].hour
                            if request.preferred_time == "morning" and not (9 <= hour < 12):
                                continue
                            elif request.preferred_time == "afternoon" and not (12 <= hour < 17):
                                continue
                            elif request.preferred_time == "evening" and not (17 <= hour < 20):
                                continue

                        available_slots.append(
                            AvailableSlot(
                                start_time=slot["start"],
                                end_time=slot["end"],
                                specialist_id=SPECIALISTS[specialist_name]["specialist_id"],
                                specialist_name=specialist_name,
                                duration_minutes=total_duration
                            )
                        )

                current_date += timedelta(days=1)

            # Sort by date/time
            available_slots.sort(key=lambda s: s.start_time)

            # Limit results to prevent overwhelming response
            MAX_SLOTS = 20
            if len(available_slots) > MAX_SLOTS:
                available_slots = available_slots[:MAX_SLOTS]

            # Build response message
            if available_slots:
                first_slot = available_slots[0]
                date_str = self._format_date_turkish(first_slot.start_time)
                time_str = first_slot.start_time.strftime("%H:%M")

                message = (
                    f"{first_slot.specialist_name} için {len(available_slots)} müsait slot bulundu. "
                    f"En yakın: {date_str} {time_str}"
                )

                logger.info(
                    "Available slots found",
                    total_slots=len(available_slots),
                    first_slot=first_slot.start_time.isoformat()
                )

                return CheckAvailabilityResponse(
                    success=True,
                    message=message,
                    available_slots=available_slots,
                    total_slots=len(available_slots)
                )
            else:
                # No slots available - provide suggestions
                suggestions = (
                    f"Belirtilen tarih aralığında müsait slot bulunamadı. "
                    f"Farklı bir tarih aralığı veya farklı bir uzman deneyebilirsiniz."
                )

                logger.info("No available slots found")

                return CheckAvailabilityResponse(
                    success=True,
                    message="Belirtilen kriterlerde müsait slot bulunamadı.",
                    available_slots=[],
                    total_slots=0,
                    suggestions=suggestions
                )

        except Exception as e:
            logger.error("Error in availability check", error=str(e))
            return CheckAvailabilityResponse(
                success=False,
                message=f"Müsaitlik kontrolü sırasında bir hata oluştu: {str(e)}",
                available_slots=[],
                total_slots=0
            )

    def create_appointment(
        self,
        request: CreateAppointmentRequest
    ) -> CreateAppointmentResponse:
        """
        Tool #4: createAppointment

        Create a new appointment with full validation and conflict checking.

        Args:
            request: Appointment creation request

        Returns:
            Appointment creation response

        Business Rules:
        - Customer must exist (or be created first)
        - Time slot must be available (no conflicts)
        - Cannot book in the past
        - Prepayment required for expensive services (>500 TRY)
        - Confirmation SMS sent automatically
        """
        logger.info(
            "Create appointment requested",
            customer_phone=request.customer_phone[-4:],  # Last 4 digits only
            slot_start=request.selected_slot.start_time.isoformat()
        )

        try:
            # 1. Validate customer exists
            customer = self.customer_repo.find_by_phone(request.customer_phone)
            if not customer:
                if request.customer_id:
                    customer = self.customer_repo.get_by_id(request.customer_id)

                if not customer:
                    return CreateAppointmentResponse(
                        success=False,
                        message="Müşteri kaydı bulunamadı. Lütfen önce müşteri kaydı oluşturun."
                    )

            # 2. Check time slot is still available (prevent race conditions)
            slot = request.selected_slot
            has_conflict = self.booking_repo.check_time_conflict(
                specialist_name=slot.specialist_name,
                start_time=slot.start_time,
                end_time=slot.end_time
            )

            if has_conflict:
                return CreateAppointmentResponse(
                    success=False,
                    message=f"Seçilen zaman dilimi ({slot.start_time.strftime('%H:%M')}) artık müsait değil. Lütfen başka bir slot seçin."
                )

            # 3. Build services list with details
            services = []
            total_price = 0.0

            for service_selection in request.services:
                service_details = self._get_service_details(service_selection.service_name)
                if not service_details:
                    logger.warning(f"Service not found: {service_selection.service_name}")
                    continue

                service = Service(
                    service_id=service_details["service_id"],
                    name=service_details["name"],
                    category=service_details["category"],
                    duration_minutes=service_details["duration_minutes"],
                    price=service_details["price"],
                    specialist_id=slot.specialist_id,
                    specialist_name=slot.specialist_name
                )
                services.append(service)
                total_price += service.price

            if not services:
                return CreateAppointmentResponse(
                    success=False,
                    message="Geçerli hizmet bulunamadı."
                )

            # 4. Create appointment
            appointment = Appointment(
                customer_id=customer.customer_id,
                customer_phone=customer.phone_number,
                start_time=slot.start_time,
                end_time=slot.end_time,
                services=services,
                status=AppointmentStatus.CONFIRMED,
                customer_notes=request.customer_notes
            )

            # 5. Check if prepayment required
            requires_prepayment = appointment.requires_prepayment()
            if requires_prepayment:
                appointment.payment_status = PaymentStatus.PENDING
            else:
                appointment.payment_status = PaymentStatus.NOT_REQUIRED

            # 6. Save appointment
            self.booking_repo.create(appointment)

            # 7. Build response
            date_str = self._format_date_turkish(appointment.start_time)
            time_str = appointment.start_time.strftime("%H:%M")

            message = (
                f"Randevunuz başarıyla oluşturuldu! "
                f"Randevu Kodu: {appointment.appointment_id}. "
                f"{date_str} {time_str}'da {slot.specialist_name} ile görüşeceksiniz. "
            )

            if requires_prepayment:
                message += f"Toplam tutar: {total_price:.0f} TL. Ön ödeme gereklidir."
            else:
                message += f"Toplam tutar: {total_price:.0f} TL."

            logger.audit(
                action="APPOINTMENT_CREATED",
                appointment_id=appointment.appointment_id,
                customer_id=customer.customer_id,
                total_price=total_price
            )

            return CreateAppointmentResponse(
                success=True,
                message=message,
                appointment_id=appointment.appointment_id,
                appointment_details=appointment.to_dict(),
                total_price=total_price,
                requires_prepayment=requires_prepayment,
                payment_link=None  # Would be generated by payment service
            )

        except ConflictError as e:
            logger.warning("Appointment conflict", error=e.message)
            return CreateAppointmentResponse(
                success=False,
                message=e.message
            )

        except Exception as e:
            logger.error("Error creating appointment", error=str(e))
            return CreateAppointmentResponse(
                success=False,
                message=f"Randevu oluşturma sırasında bir hata oluştu: {str(e)}"
            )

    def cancel_appointment(
        self,
        request: CancelAppointmentRequest
    ) -> CancelAppointmentResponse:
        """
        Tool #5: cancelAppointment

        Cancel an appointment with business rules validation.

        Args:
            request: Cancellation request

        Returns:
            Cancellation response

        Business Rules:
        - Must provide appointment_id or customer_phone
        - Cannot cancel within 24 hours (configurable)
        - Cannot cancel already completed/cancelled appointments
        - Refund initiated if prepayment was made
        - Cancellation SMS sent automatically
        """
        logger.info(
            "Cancel appointment requested",
            appointment_id=request.appointment_id,
            phone=request.customer_phone[-4:] if request.customer_phone else None
        )

        try:
            # 1. Find appointment
            appointment = None

            if request.appointment_id:
                appointment = self.booking_repo.get_by_id(request.appointment_id)

            elif request.customer_phone:
                # Find most recent upcoming appointment for this customer
                appointments = self.booking_repo.find_by_customer_phone(request.customer_phone)
                upcoming = [
                    apt for apt in appointments
                    if apt.status == AppointmentStatus.CONFIRMED and apt.start_time > datetime.utcnow()
                ]
                if upcoming:
                    appointment = upcoming[0]  # Most recent

            if not appointment:
                return CancelAppointmentResponse(
                    success=False,
                    message="Randevu bulunamadı. Lütfen randevu kodunuzu kontrol edin."
                )

            # 2. Verify customer (security check)
            if request.customer_phone:
                if appointment.customer_phone != request.customer_phone:
                    logger.warning(
                        "Cancel attempt with wrong phone",
                        appointment_id=appointment.appointment_id
                    )
                    return CancelAppointmentResponse(
                        success=False,
                        message="Bu randevu size ait değil."
                    )

            # 3. Try to cancel (business rules checked in repository)
            try:
                cancelled_appointment = self.booking_repo.cancel_appointment(
                    appointment.appointment_id,
                    reason=request.cancellation_reason
                )

                if not cancelled_appointment:
                    return CancelAppointmentResponse(
                        success=False,
                        message="Randevu iptal edilemedi."
                    )

                # 4. Handle refund if prepayment was made
                refund_info = None
                if appointment.payment_status in [PaymentStatus.PAID, PaymentStatus.PARTIAL]:
                    refund_info = (
                        f"Ödemeniz 3-5 iş günü içinde iade edilecektir. "
                        f"İade tutarı: {appointment.total_price:.0f} TL"
                    )

                logger.audit(
                    action="APPOINTMENT_CANCELLED",
                    appointment_id=appointment.appointment_id,
                    customer_id=appointment.customer_id,
                    reason=request.cancellation_reason
                )

                return CancelAppointmentResponse(
                    success=True,
                    message=f"Randevunuz başarıyla iptal edildi. Randevu Kodu: {appointment.appointment_id}",
                    cancelled_appointment_id=appointment.appointment_id,
                    refund_info=refund_info
                )

            except ValueError as e:
                # Business rule violation (e.g., too close to appointment time)
                return CancelAppointmentResponse(
                    success=False,
                    message=str(e)
                )

        except Exception as e:
            logger.error("Error cancelling appointment", error=str(e))
            return CancelAppointmentResponse(
                success=False,
                message=f"Randevu iptali sırasında bir hata oluştu: {str(e)}"
            )


# Global service instance
booking_service = BookingService()
