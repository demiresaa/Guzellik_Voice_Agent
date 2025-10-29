# services/booking_agent_service/repositories/booking_repository.py

"""
Booking Repository for appointment data operations.
Staff Engineer principle: Complex queries, conflict detection, time-based operations.
"""

from typing import Optional, List
from datetime import datetime, date, timedelta
from .base import BaseRepository, db
from ..models.booking import Appointment
from ..models.enums import AppointmentStatus
from ..utils.logger import get_logger
from ..utils.exceptions import ConflictError

logger = get_logger(__name__)


class BookingRepository(BaseRepository[Appointment]):
    """
    Repository for Appointment entity operations.

    Provides specialized queries for booking management:
    - Availability checking (complex time-based queries)
    - Conflict detection
    - Customer appointment history
    - Specialist schedules
    - Date range queries
    """

    def __init__(self):
        """Initialize with shared database storage"""
        super().__init__()
        self._storage = db.get_appointments()

    def _get_entity_id(self, entity: Appointment) -> str:
        """Get appointment ID from entity"""
        return entity.appointment_id

    def find_by_customer_id(self, customer_id: str) -> List[Appointment]:
        """
        Find all appointments for a customer.

        Args:
            customer_id: Customer ID

        Returns:
            List of appointments
        """
        results = []
        for appointment in self._storage.values():
            if appointment.customer_id == customer_id:
                results.append(appointment)

        # Sort by date (newest first)
        results.sort(key=lambda a: a.start_time, reverse=True)
        return results

    def find_by_customer_phone(self, phone_number: str) -> List[Appointment]:
        """
        Find all appointments for a customer by phone.

        Args:
            phone_number: Customer phone number

        Returns:
            List of appointments
        """
        results = []
        for appointment in self._storage.values():
            if appointment.customer_phone == phone_number:
                results.append(appointment)

        results.sort(key=lambda a: a.start_time, reverse=True)
        return results

    def get_last_n_appointments(
        self,
        customer_id: str,
        n: int = 3
    ) -> List[Appointment]:
        """
        Get last N appointments for a customer.

        Used for conversation context ("Your last appointment was...").

        Args:
            customer_id: Customer ID
            n: Number of appointments to return

        Returns:
            List of last N appointments
        """
        appointments = self.find_by_customer_id(customer_id)
        return appointments[:n]

    def find_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        status: Optional[AppointmentStatus] = None
    ) -> List[Appointment]:
        """
        Find appointments in date range.

        Args:
            start_date: Range start
            end_date: Range end
            status: Optional status filter

        Returns:
            List of appointments in range
        """
        results = []
        for appointment in self._storage.values():
            if start_date <= appointment.start_time <= end_date:
                if status is None or appointment.status == status:
                    results.append(appointment)

        results.sort(key=lambda a: a.start_time)
        return results

    def find_by_specialist_and_date(
        self,
        specialist_name: str,
        target_date: date
    ) -> List[Appointment]:
        """
        Find all appointments for a specialist on a specific date.

        Critical for availability checking.

        Args:
            specialist_name: Specialist name
            target_date: Target date

        Returns:
            List of appointments
        """
        results = []
        for appointment in self._storage.values():
            # Only consider confirmed appointments
            if appointment.status != AppointmentStatus.CONFIRMED:
                continue

            # Check if appointment is on target date
            if appointment.start_time.date() != target_date:
                continue

            # Check if any service is with this specialist
            for service in appointment.services:
                if service.specialist_name == specialist_name:
                    results.append(appointment)
                    break

        results.sort(key=lambda a: a.start_time)
        return results

    def check_time_conflict(
        self,
        specialist_name: str,
        start_time: datetime,
        end_time: datetime,
        exclude_appointment_id: Optional[str] = None
    ) -> bool:
        """
        Check if time slot conflicts with existing appointments.

        Critical for preventing double-booking.

        Args:
            specialist_name: Specialist to check
            start_time: Proposed start time
            end_time: Proposed end time
            exclude_appointment_id: Appointment ID to exclude (for rescheduling)

        Returns:
            True if conflict exists, False otherwise
        """
        target_date = start_time.date()
        existing_appointments = self.find_by_specialist_and_date(
            specialist_name,
            target_date
        )

        for appointment in existing_appointments:
            # Skip excluded appointment (for rescheduling)
            if exclude_appointment_id and appointment.appointment_id == exclude_appointment_id:
                continue

            # Check for time overlap
            # Conflict if: (start1 < end2) AND (end1 > start2)
            if (appointment.start_time < end_time and
                appointment.end_time > start_time):
                logger.debug(
                    "Time conflict detected",
                    specialist=specialist_name,
                    proposed_start=start_time.isoformat(),
                    proposed_end=end_time.isoformat(),
                    conflict_appointment=appointment.appointment_id
                )
                return True

        return False

    def find_available_slots(
        self,
        specialist_name: str,
        target_date: date,
        duration_minutes: int,
        working_hours: tuple[int, int] = (9, 18)  # 9 AM to 6 PM
    ) -> List[dict]:
        """
        Find available time slots for a specialist on a given date.

        This is the core availability algorithm.

        Args:
            specialist_name: Specialist name
            target_date: Date to check
            duration_minutes: Required duration
            working_hours: Tuple of (start_hour, end_hour)

        Returns:
            List of available slots [{"start": datetime, "end": datetime}, ...]
        """
        # Get existing appointments for this specialist on this date
        existing_appointments = self.find_by_specialist_and_date(
            specialist_name,
            target_date
        )

        # Working hours
        start_hour, end_hour = working_hours
        day_start = datetime.combine(target_date, datetime.min.time()).replace(hour=start_hour)
        day_end = datetime.combine(target_date, datetime.min.time()).replace(hour=end_hour)

        # Generate all possible slots (30-minute intervals)
        available_slots = []
        current_time = day_start

        while current_time + timedelta(minutes=duration_minutes) <= day_end:
            slot_end = current_time + timedelta(minutes=duration_minutes)

            # Check if this slot conflicts with any appointment
            has_conflict = False
            for appointment in existing_appointments:
                if (current_time < appointment.end_time and
                    slot_end > appointment.start_time):
                    has_conflict = True
                    break

            if not has_conflict:
                available_slots.append({
                    "start": current_time,
                    "end": slot_end
                })

            # Move to next 30-minute interval
            current_time += timedelta(minutes=30)

        logger.debug(
            "Available slots calculated",
            specialist=specialist_name,
            date=target_date.isoformat(),
            total_slots=len(available_slots)
        )

        return available_slots

    def find_upcoming_appointments(
        self,
        days: int = 7,
        status: Optional[AppointmentStatus] = None
    ) -> List[Appointment]:
        """
        Find upcoming appointments in next N days.

        Useful for reminder sending.

        Args:
            days: Number of days ahead
            status: Optional status filter

        Returns:
            List of upcoming appointments
        """
        now = datetime.utcnow()
        end_date = now + timedelta(days=days)

        return self.find_by_date_range(now, end_date, status)

    def find_appointments_for_reminder(
        self,
        hours_before: int = 24
    ) -> List[Appointment]:
        """
        Find appointments that need reminder sent.

        Args:
            hours_before: Hours before appointment to send reminder

        Returns:
            List of appointments needing reminder
        """
        now = datetime.utcnow()
        reminder_window_start = now + timedelta(hours=hours_before - 1)
        reminder_window_end = now + timedelta(hours=hours_before)

        results = []
        for appointment in self._storage.values():
            if appointment.status != AppointmentStatus.CONFIRMED:
                continue

            if appointment.reminder_sent:
                continue

            if reminder_window_start <= appointment.start_time <= reminder_window_end:
                results.append(appointment)

        return results

    def get_booking_stats(self, date_range: Optional[tuple[date, date]] = None) -> dict:
        """
        Get booking statistics.

        Args:
            date_range: Optional (start_date, end_date) tuple

        Returns:
            Statistics dictionary
        """
        appointments = self.list_all()

        if date_range:
            start_date, end_date = date_range
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            appointments = [
                a for a in appointments
                if start_dt <= a.start_time <= end_dt
            ]

        status_counts = {}
        total_revenue = 0.0
        service_counts = {}

        for appointment in appointments:
            # Status distribution
            status = appointment.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

            # Revenue (only confirmed/completed)
            if appointment.status in [AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED]:
                total_revenue += appointment.total_price

            # Service popularity
            for service in appointment.services:
                svc_name = service.name
                service_counts[svc_name] = service_counts.get(svc_name, 0) + 1

        return {
            "total_appointments": len(appointments),
            "status_distribution": status_counts,
            "total_revenue": total_revenue,
            "average_revenue": total_revenue / len(appointments) if appointments else 0.0,
            "service_popularity": service_counts
        }

    def cancel_appointment(
        self,
        appointment_id: str,
        reason: Optional[str] = None
    ) -> Optional[Appointment]:
        """
        Cancel an appointment.

        Args:
            appointment_id: Appointment ID
            reason: Cancellation reason

        Returns:
            Cancelled appointment or None if not found

        Raises:
            ConflictError: If appointment cannot be cancelled
        """
        appointment = self.get_by_id(appointment_id)
        if not appointment:
            return None

        try:
            appointment.cancel(reason)
            self.update(appointment)
            logger.audit(
                action="APPOINTMENT_CANCELLED",
                appointment_id=appointment_id,
                reason=reason
            )
            return appointment
        except ValueError as e:
            raise ConflictError(
                message=str(e),
                details={"appointment_id": appointment_id}
            )


# Global repository instance
booking_repository = BookingRepository()
